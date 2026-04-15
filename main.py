import os
import sys
import threading
import time

from config_manager import ConfigManager
from gui import SettingsWindow, TrayIcon
from logger import setup_logger
from window_listener import WindowListener
from audio_listener import AudioListener
from state_manager import StateManager

logger = setup_logger("VolumeController")


class VolumeControllerApp:
    def __init__(self):
        self._config = ConfigManager()
        self._state_manager = StateManager(self._config)
        self._window_listener = WindowListener()
        self._audio_listener = AudioListener()
        self._tray_icon: TrayIcon | None = None
        self._settings_window: SettingsWindow | None = None
        self._running = False
        self._sync_thread: threading.Thread | None = None

    def start(self) -> None:
        logger.info("=" * 60)
        logger.info("VolumeController 启动中...")
        logger.info("Python %s", sys.version)
        logger.info("工作目录: %s", os.getcwd())
        logger.info("=" * 60)

        self._running = True

        # 启动前台窗口监听器
        if not self._window_listener.start(self._on_foreground_change):
            logger.error("启动前台窗口监听器失败")

        # 启动音频会话监听器
        if not self._audio_listener.start(self._on_audio_session_change):
            logger.error("启动音频会话监听器失败")

        # 启动兜底同步线程
        self._sync_thread = threading.Thread(
            target=self._sync_loop, daemon=True, name="SyncThread"
        )
        self._sync_thread.start()
        logger.info("兜底同步线程已启动")

        self._tray_icon = TrayIcon(
            config_manager=self._config,
            on_settings=self._open_settings,
            on_toggle=self._toggle_enabled,
            on_exit=self._exit,
        )

        tray_thread = threading.Thread(
            target=self._tray_icon.run, daemon=True, name="TrayThread"
        )
        tray_thread.start()
        logger.info("系统托盘已启动")

        try:
            import ctypes
            user32 = ctypes.windll.user32
            while self._running:
                # 处理Windows消息
                msg = ctypes.wintypes.MSG()
                while user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                # 短暂睡眠
                import time
                time.sleep(0.01)
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号")
            self._exit()

    def _on_foreground_change(self, pid: int, name: str) -> None:
        """处理前台窗口切换事件"""
        self._state_manager.update_foreground(pid, name)

    def _on_audio_session_change(self, process_name: str, pid: int, is_created: bool) -> None:
        """处理音频会话变化事件"""
        if is_created:
            self._state_manager.add_session(process_name, pid, is_created)

    def _sync_loop(self) -> None:
        """兜底同步循环"""
        while self._running:
            try:
                if self._config.enabled:
                    self._state_manager.sync()
                time.sleep(1)  # 每秒检查一次是否需要同步
            except Exception as e:
                logger.error("同步循环异常: %s", e, exc_info=True)
                time.sleep(2)

    def _restore_all_muted(self) -> None:
        self._state_manager.restore_all()

    def _open_settings(self) -> None:
        def _show():
            if self._settings_window is None:
                self._settings_window = SettingsWindow(
                    config_manager=self._config,
                    on_config_changed=self._on_config_changed,
                )
            self._settings_window.show()

        thread = threading.Thread(target=_show, daemon=True)
        thread.start()

    def _toggle_enabled(self) -> None:
        self._config.enabled = not self._config.enabled
        status = "启用" if self._config.enabled else "禁用"
        logger.info("自动静音功能已%s", status)

        if self._tray_icon:
            self._tray_icon.update_icon(self._config.enabled)

    def _on_config_changed(self) -> None:
        if self._tray_icon:
            self._tray_icon.update_icon(self._config.enabled)
        self._config.reload()

    def _exit(self) -> None:
        logger.info("正在退出 VolumeController...")
        self._running = False

        # 停止监听器
        self._window_listener.stop()
        self._audio_listener.stop()

        # 恢复所有静音
        self._restore_all_muted()

        if self._tray_icon:
            self._tray_icon.stop()

        logger.info("VolumeController 已退出")
        sys.exit(0)


def check_windows_version() -> bool:
    try:
        version = sys.getwindowsversion()
        if version.major < 10:
            logger.warning(
                "当前系统版本不支持: Windows %d.%d (需要 Windows 10+)",
                version.major,
                version.minor,
            )
            return False
        logger.info(
            "系统版本: Windows %d.%d Build %d",
            version.major,
            version.minor,
            version.build,
        )
        return True
    except AttributeError:
        return True


def main() -> None:
    if not check_windows_version():
        print("错误: 此程序需要 Windows 10 或更高版本")
        sys.exit(1)

    try:
        app = VolumeControllerApp()
        app.start()
    except Exception as e:
        logger.critical("程序发生致命错误: %s", e, exc_info=True)
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"VolumeController 发生致命错误:\n{e}\n\n请查看日志文件获取详细信息。",
                "VolumeController - 错误",
                0x10,
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
