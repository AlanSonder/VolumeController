import ctypes
import ctypes.wintypes
from typing import Callable, Optional

from logger import setup_logger

logger = setup_logger("WindowListener")

# Win32 API 常量
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

# 定义回调函数类型
WinEventProcType = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,
    ctypes.c_uint,
    ctypes.wintypes.HWND,
    ctypes.c_long,
    ctypes.c_long,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD
)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class WindowListener:
    def __init__(self):
        self._hook_handle: Optional[int] = None
        self._callback: Optional[Callable[[int, str], None]] = None
        self._last_foreground_pid: Optional[int] = None

    def start(self, callback: Callable[[int, str], None]) -> bool:
        """启动前台窗口切换监听"""
        self._callback = callback
        
        # 创建回调函数对象并保存为实例变量
        self._win_event_proc = WinEventProcType(self._win_event_proc_func)
        
        # 设置事件钩子
        self._hook_handle = user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND,
            EVENT_SYSTEM_FOREGROUND,
            0,
            self._win_event_proc,
            0,
            0,
            WINEVENT_OUTOFCONTEXT
        )
        
        if not self._hook_handle:
            logger.error("设置窗口事件钩子失败")
            return False
        
        logger.info("前台窗口切换监听器已启动")
        return True

    def _win_event_proc_func(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
        """窗口事件回调函数"""
        if event == EVENT_SYSTEM_FOREGROUND:
            self._on_foreground_change(hwnd)

    def stop(self) -> None:
        """停止监听"""
        if self._hook_handle:
            user32.UnhookWinEvent(self._hook_handle)
            self._hook_handle = None
            logger.info("前台窗口切换监听器已停止")

    def _on_foreground_change(self, hwnd: int) -> None:
        """处理前台窗口切换事件"""
        try:
            # 获取窗口对应的进程ID
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            if pid.value == 0:
                return
            
            # 避免重复处理
            if pid.value == self._last_foreground_pid:
                return
            
            self._last_foreground_pid = pid.value
            
            # 获取进程名
            process_name = self._get_process_name_by_pid(pid.value)
            if process_name:
                logger.info("前台窗口切换: %s (PID: %d)", process_name, pid.value)
                if self._callback:
                    self._callback(pid.value, process_name)
        
        except Exception as e:
            logger.error("处理前台窗口切换事件失败: %s", e)

    @staticmethod
    def _get_process_name_by_pid(pid: int) -> Optional[str]:
        """通过PID获取进程名"""
        try:
            import psutil
            proc = psutil.Process(pid)
            return proc.name()
        except (ImportError, psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None