import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from PIL import Image, ImageDraw

from app_paths import get_app_dir, get_resource_path
from logger import setup_logger

logger = setup_logger("VolumeController")


def create_tray_icon_image(enabled: bool = True) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if enabled:
        color = (0, 180, 0, 255)
    else:
        color = (180, 0, 0, 255)

    draw.ellipse([8, 8, 56, 56], fill=color, outline=(255, 255, 255, 200), width=2)

    speaker_x, speaker_y = 18, 22
    draw.rectangle([speaker_x, speaker_y, speaker_x + 8, speaker_y + 20], fill="white")
    draw.polygon(
        [
            (speaker_x + 8, speaker_y),
            (speaker_x + 20, speaker_y - 8),
            (speaker_x + 20, speaker_y + 28),
            (speaker_x + 8, speaker_y + 20),
        ],
        fill="white",
    )

    if enabled:
        for i, offset in enumerate([4, 8, 12]):
            cx = speaker_x + 22 + offset
            cy = speaker_y + 10
            r = 4 + i * 2
            draw.arc(
                [cx - r, cy - r, cx + r, cy + r],
                start=-60,
                end=60,
                fill="white",
                width=2,
            )
    else:
        draw.line(
            [(speaker_x + 6, speaker_y - 4), (speaker_x + 30, speaker_y + 24)],
            fill=(255, 60, 60, 255),
            width=3,
        )

    return img


class SettingsWindow:
    def __init__(
        self,
        config_manager,
        on_config_changed: Optional[Callable] = None,
    ):
        self._config = config_manager
        self._on_config_changed = on_config_changed
        self._window: Optional[tk.Tk] = None
        self._whitelist_frame: Optional[ttk.Frame] = None
        self._whitelist_listbox: Optional[tk.Listbox] = None
        self._add_entry: Optional[ttk.Entry] = None
        self._enabled_var: Optional[tk.BooleanVar] = None
        self._auto_start_var: Optional[tk.BooleanVar] = None
        self._interval_var: Optional[tk.IntVar] = None
        self._running_processes_var: Optional[tk.StringVar] = None

    def show(self) -> None:
        if self._window is not None:
            try:
                self._window.lift()
                self._window.focus_force()
                return
            except tk.TclError:
                self._window = None

        self._window = tk.Tk()
        self._window.title("VolumeController - 设置")
        self._window.geometry("620x580")
        self._window.resizable(True, True)
        self._window.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            self._window.iconbitmap(self._get_icon_path())
        except Exception:
            pass

        self._build_ui()
        self._window.mainloop()

    def _get_icon_path(self) -> str:
        return get_resource_path("icon.ico")

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self._window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text="  常规设置  ")
        self._build_general_tab(general_frame)

        whitelist_frame = ttk.Frame(notebook, padding=10)
        notebook.add(whitelist_frame, text="  白名单管理  ")
        self._build_whitelist_tab(whitelist_frame)

        import_export_frame = ttk.Frame(notebook, padding=10)
        notebook.add(import_export_frame, text="  导入/导出  ")
        self._build_import_export_tab(import_export_frame)

    def _build_general_tab(self, parent: ttk.Frame) -> None:
        enabled_frame = ttk.LabelFrame(parent, text="功能控制", padding=10)
        enabled_frame.pack(fill=tk.X, pady=(0, 10))

        self._enabled_var = tk.BooleanVar(value=self._config.enabled)
        ttk.Checkbutton(
            enabled_frame,
            text="启用自动静音功能",
            variable=self._enabled_var,
            command=self._on_enabled_changed,
        ).pack(anchor=tk.W)

        self._auto_start_var = tk.BooleanVar(value=self._config.auto_start)
        ttk.Checkbutton(
            enabled_frame,
            text="开机自动启动",
            variable=self._auto_start_var,
            command=self._on_auto_start_changed,
        ).pack(anchor=tk.W, pady=(5, 0))

        interval_frame = ttk.LabelFrame(parent, text="检测间隔", padding=10)
        interval_frame.pack(fill=tk.X, pady=(0, 10))

        interval_inner = ttk.Frame(interval_frame)
        interval_inner.pack(fill=tk.X)

        ttk.Label(interval_inner, text="检测间隔:").pack(side=tk.LEFT)
        self._interval_var = tk.IntVar(value=self._config.check_interval_ms)
        spinbox = ttk.Spinbox(
            interval_inner,
            from_=200,
            to=3000,
            increment=100,
            textvariable=self._interval_var,
            width=8,
        )
        spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_inner, text="毫秒 (推荐 300-1000)").pack(side=tk.LEFT)

        ttk.Button(
            interval_frame,
            text="应用间隔设置",
            command=self._on_interval_changed,
        ).pack(anchor=tk.W, pady=(5, 0))

        status_frame = ttk.LabelFrame(parent, text="当前状态", padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True)

        self._status_label = ttk.Label(
            status_frame,
            text=self._get_status_text(),
            wraplength=500,
            justify=tk.LEFT,
        )
        self._status_label.pack(anchor=tk.W)

    def _build_whitelist_tab(self, parent: ttk.Frame) -> None:
        add_frame = ttk.LabelFrame(parent, text="添加应用到白名单", padding=10)
        add_frame.pack(fill=tk.X, pady=(0, 10))

        entry_row = ttk.Frame(add_frame)
        entry_row.pack(fill=tk.X)

        ttk.Label(entry_row, text="进程名:").pack(side=tk.LEFT)
        self._add_entry = ttk.Entry(entry_row, width=30)
        self._add_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_row, text="添加", command=self._add_to_whitelist).pack(side=tk.LEFT, padx=2)

        from_proc_frame = ttk.Frame(add_frame)
        from_proc_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(from_proc_frame, text="从运行中添加:").pack(side=tk.LEFT)
        self._running_processes_var = tk.StringVar()
        self._process_combo = ttk.Combobox(
            from_proc_frame,
            textvariable=self._running_processes_var,
            width=30,
            state="readonly",
        )
        self._process_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(
            from_proc_frame,
            text="刷新列表",
            command=self._refresh_process_list,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            from_proc_frame,
            text="添加选中",
            command=self._add_selected_process,
        ).pack(side=tk.LEFT, padx=2)

        list_frame = ttk.LabelFrame(parent, text="白名单列表", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        list_inner = ttk.Frame(list_frame)
        list_inner.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_inner, orient=tk.VERTICAL)
        self._whitelist_listbox = tk.Listbox(
            list_inner,
            yscrollcommand=scrollbar.set,
            selectmode=tk.EXTENDED,
            font=("Consolas", 10),
        )
        scrollbar.config(command=self._whitelist_listbox.yview)
        self._whitelist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(btn_frame, text="移除选中", command=self._remove_from_whitelist).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="清空白名单", command=self._clear_whitelist).pack(
            side=tk.LEFT, padx=2
        )

        self._refresh_whitelist_list()
        self._refresh_process_list()

    def _build_import_export_tab(self, parent: ttk.Frame) -> None:
        export_frame = ttk.LabelFrame(parent, text="导出配置", padding=10)
        export_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            export_frame,
            text="将当前配置（白名单和设置）导出为JSON文件，方便备份或迁移。",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Button(export_frame, text="导出配置...", command=self._export_config).pack(
            anchor=tk.W
        )

        import_frame = ttk.LabelFrame(parent, text="导入配置", padding=10)
        import_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            import_frame,
            text="从JSON文件导入配置。当前配置将被替换，原配置会自动备份。",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Button(import_frame, text="导入配置...", command=self._import_config).pack(
            anchor=tk.W
        )

        info_frame = ttk.LabelFrame(parent, text="配置文件位置", padding=10)
        info_frame.pack(fill=tk.X)

        config_path = self._config._config_path
        ttk.Label(
            info_frame,
            text=f"配置文件: {config_path}",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

    def _get_status_text(self) -> str:
        status = "已启用" if self._config.enabled else "已禁用"
        auto = "已开启" if self._config.auto_start else "已关闭"
        return (
            f"自动静音功能: {status}\n"
            f"开机自启动: {auto}\n"
            f"检测间隔: {self._config.check_interval_ms}ms\n"
            f"白名单应用数: {len(self._config.whitelist)}"
        )

    def _refresh_whitelist_list(self) -> None:
        if self._whitelist_listbox is None:
            return
        self._whitelist_listbox.delete(0, tk.END)
        for name in sorted(self._config.whitelist):
            self._whitelist_listbox.insert(tk.END, name)

    def _refresh_process_list(self) -> None:
        try:
            import psutil

            processes = set()
            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info.get("name")
                    if name:
                        processes.add(name)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            sorted_procs = sorted(processes)
            if self._process_combo:
                self._process_combo["values"] = sorted_procs
        except Exception as e:
            logger.error("刷新进程列表失败: %s", e)

    def _add_to_whitelist(self) -> None:
        if self._add_entry is None:
            return
        name = self._add_entry.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入进程名称", parent=self._window)
            return
        if self._config.add_to_whitelist(name):
            self._add_entry.delete(0, tk.END)
            self._refresh_whitelist_list()
            self._notify_changed()
        else:
            messagebox.showinfo("提示", f"'{name}' 已在白名单中", parent=self._window)

    def _add_selected_process(self) -> None:
        if self._running_processes_var is None:
            return
        name = self._running_processes_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请先选择一个进程", parent=self._window)
            return
        if self._config.add_to_whitelist(name):
            self._refresh_whitelist_list()
            self._notify_changed()
        else:
            messagebox.showinfo("提示", f"'{name}' 已在白名单中", parent=self._window)

    def _remove_from_whitelist(self) -> None:
        if self._whitelist_listbox is None:
            return
        selections = self._whitelist_listbox.curselection()
        if not selections:
            messagebox.showwarning("提示", "请先选择要移除的项目", parent=self._window)
            return
        for idx in reversed(selections):
            name = self._whitelist_listbox.get(idx)
            self._config.remove_from_whitelist(name)
        self._refresh_whitelist_list()
        self._notify_changed()

    def _clear_whitelist(self) -> None:
        if messagebox.askyesno("确认", "确定要清空白名单吗？", parent=self._window):
            self._config.whitelist = []
            self._refresh_whitelist_list()
            self._notify_changed()

    def _on_enabled_changed(self) -> None:
        if self._enabled_var is not None:
            self._config.enabled = self._enabled_var.get()
            self._status_label.config(text=self._get_status_text())
            self._notify_changed()

    def _on_auto_start_changed(self) -> None:
        if self._auto_start_var is not None:
            self._config.auto_start = self._auto_start_var.get()
            self._update_auto_start_registry()
            self._status_label.config(text=self._get_status_text())
            self._notify_changed()

    def _on_interval_changed(self) -> None:
        if self._interval_var is not None:
            value = self._interval_var.get()
            if value < 200:
                value = 200
            elif value > 3000:
                value = 3000
            self._config.set_setting("check_interval_ms", value)
            self._interval_var.set(value)
            self._notify_changed()

    def _update_auto_start_registry(self) -> None:
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "VolumeController"
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0])

            if self._config.auto_start:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
                logger.info("已添加开机自启动注册表项")
            else:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, app_name)
                    logger.info("已移除开机自启动注册表项")
                except FileNotFoundError:
                    pass
        except Exception as e:
            logger.error("更新注册表失败: %s", e)
            if self._window:
                messagebox.showerror("错误", f"更新注册表失败: {e}", parent=self._window)

    def _export_config(self) -> None:
        if self._window is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self._window,
            title="导出配置",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialfile="volume_controller_config.json",
        )
        if path:
            if self._config.export_config(path):
                messagebox.showinfo("成功", f"配置已导出至:\n{path}", parent=self._window)
            else:
                messagebox.showerror("失败", "配置导出失败", parent=self._window)

    def _import_config(self) -> None:
        if self._window is None:
            return
        path = filedialog.askopenfilename(
            parent=self._window,
            title="导入配置",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
        )
        if path:
            if messagebox.askyesno(
                "确认",
                "导入配置将替换当前设置，是否继续？",
                parent=self._window,
            ):
                if self._config.import_config(path):
                    self._refresh_whitelist_list()
                    self._notify_changed()
                    messagebox.showinfo("成功", "配置导入成功", parent=self._window)
                else:
                    messagebox.showerror("失败", "配置导入失败，请检查文件格式", parent=self._window)

    def _notify_changed(self) -> None:
        if self._on_config_changed:
            self._on_config_changed()

    def _on_close(self) -> None:
        if self._window:
            self._window.destroy()
            self._window = None


class TrayIcon:
    def __init__(
        self,
        config_manager,
        on_settings: Callable,
        on_toggle: Callable,
        on_exit: Callable,
    ):
        self._config = config_manager
        self._on_settings = on_settings
        self._on_toggle = on_toggle
        self._on_exit = on_exit
        self._icon = None

    def run(self) -> None:
        try:
            import pystray

            icon_image = create_tray_icon_image(self._config.enabled)
            menu = pystray.Menu(
                pystray.MenuItem(
                    lambda text: ("禁用自动静音" if self._config.enabled else "启用自动静音"),
                    self._toggle,
                    default=True,
                ),
                pystray.MenuItem("设置", self._open_settings),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._exit),
            )

            self._icon = pystray.Icon(
                "VolumeController",
                icon_image,
                "VolumeController - 自动静音",
                menu,
            )
            self._icon.run()
        except Exception as e:
            logger.error("系统托盘启动失败: %s", e)

    def update_icon(self, enabled: bool) -> None:
        if self._icon:
            try:
                self._icon.icon = create_tray_icon_image(enabled)
                self._icon.title = (
                    f"VolumeController - {'已启用' if enabled else '已禁用'}"
                )
            except Exception as e:
                logger.error("更新托盘图标失败: %s", e)

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _toggle(self, icon, item) -> None:
        self._on_toggle()

    def _open_settings(self, icon, item) -> None:
        self._on_settings()

    def _exit(self, icon, item) -> None:
        self._on_exit()
