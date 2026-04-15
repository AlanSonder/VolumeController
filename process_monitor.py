import ctypes
import ctypes.wintypes
from typing import Optional

import psutil

from logger import setup_logger

logger = setup_logger("VolumeController")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


class ProcessMonitor:
    def __init__(self):
        self._last_foreground_pid: Optional[int] = None

    def get_foreground_process(self) -> Optional[tuple[int, str]]:
        try:
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            if pid.value == 0:
                return None

            process_name = self._get_process_name_by_pid(pid.value)
            if process_name is None:
                return None

            if self._last_foreground_pid != pid.value:
                self._last_foreground_pid = pid.value
                logger.info("前台进程切换: %s (PID: %d)", process_name, pid.value)

            return (pid.value, process_name)

        except Exception as e:
            logger.error("获取前台进程失败: %s", e)
            return None

    @staticmethod
    def _get_process_name_by_pid(pid: int) -> Optional[str]:
        try:
            proc = psutil.Process(pid)
            return proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    def is_process_in_foreground(self, pid: int) -> bool:
        fg = self.get_foreground_process()
        if fg is None:
            return False
        return fg[0] == pid

    def get_all_audio_processes(self) -> dict[int, str]:
        result = {}
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                info = proc.info
                if info["pid"] and info["name"]:
                    result[info["pid"]] = info["name"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return result
