import os
import sys
import threading
import time

from config_manager import ConfigManager
from gui import SettingsWindow, TrayIcon
from logger import setup_logger
from process_monitor import ProcessMonitor
from volume_controller import VolumeController

logger = setup_logger("VolumeController")


class VolumeControllerApp:
    def __init__(self):
        self._config = ConfigManager()
        self._volume_ctrl = VolumeController()
        self._process_monitor = ProcessMonitor()
        self._tray_icon: TrayIcon | None = None
        self._settings_window: SettingsWindow | None = None
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        logger.info("=" * 60)
        logger.info("VolumeController 启动中...")
        logger.info("Python %s", sys.version)
        logger.info("工作目录: %s", os.getcwd())
        logger.info("=" * 60)

        self._running = True

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="MonitorThread"
        )
        self._monitor_thread.start()
        logger.info("监控线程已启动")

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
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号")
            self._exit()

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                if not self._config.enabled:
                    self._restore_all_muted()
                    time.sleep(self._config.check_interval_ms / 1000.0)
                    continue

                self._check_and_control()
                time.sleep(self._config.check_interval_ms / 1000.0)

            except Exception as e:
                logger.error("监控循环异常: %s", e, exc_info=True)
                time.sleep(2)

    def _check_and_control(self) -> None:
        fg_info = self._process_monitor.get_foreground_process()
        if fg_info is None:
            return

        fg_pid, fg_name = fg_info
        sessions = self._volume_ctrl.get_all_sessions()

        active_pids = set[int]()

        for session in sessions:
            active_pids.add(session.pid)

            is_foreground = session.pid == fg_pid
            is_whitelisted = self._config.is_whitelisted(session.process_name)

            if is_foreground or is_whitelisted:
                if self._volume_ctrl.was_muted_by_us(session.pid):
                    self._volume_ctrl.unmute_process(session)
                    logger.info(
                        "恢复前台应用音量: %s (PID: %d)",
                        session.process_name,
                        session.pid,
                    )
            else:
                if not session.is_muted:
                    self._volume_ctrl.mute_process(session)
                    logger.info(
                        "静音后台应用: %s (PID: %d)",
                        session.process_name,
                        session.pid,
                    )

        self._volume_ctrl.cleanup_stale_entries(active_pids)

    def _restore_all_muted(self) -> None:
        muted_pids = self._volume_ctrl.get_muted_pids()
        if not muted_pids:
            return

        sessions = self._volume_ctrl.get_all_sessions()
        for session in sessions:
            if self._volume_ctrl.was_muted_by_us(session.pid):
                self._volume_ctrl.unmute_process(session)
                logger.info("恢复音量: %s (PID: %d)", session.process_name, session.pid)

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
