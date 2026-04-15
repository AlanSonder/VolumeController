import pythoncom
import threading
from typing import Callable, Dict, Optional, Set
import time

from pycaw.pycaw import AudioUtilities

from logger import setup_logger

logger = setup_logger("AudioListener")


class AudioListener:
    def __init__(self):
        self._callback: Optional[Callable[[str, int, bool], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._com_initialized = False
        self._known_sessions: Set[int] = set()

    def start(self, callback: Callable[[str, int, bool], None]) -> bool:
        """启动音频会话监听"""
        self._callback = callback
        self._running = True
        
        # 在单独的线程中运行，避免阻塞主线程
        self._thread = threading.Thread(target=self._run, daemon=True, name="AudioListenerThread")
        self._thread.start()
        
        logger.info("音频会话监听器已启动")
        return True

    def stop(self) -> None:
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("音频会话监听器已停止")

    def _run(self) -> None:
        """监听线程主函数"""
        try:
            self._ensure_com()
            
            # 初始化已知会话
            self._known_sessions = self._get_current_session_pids()
            logger.info("初始化音频会话: %d 个", len(self._known_sessions))
            
            # 循环检测会话变化
            while self._running:
                current_sessions = self._get_current_session_pids()
                
                # 检测新会话
                new_sessions = current_sessions - self._known_sessions
                for pid in new_sessions:
                    process_name = self._get_process_name_by_pid(pid)
                    if process_name:
                        logger.info("音频会话创建: %s (PID: %d)", process_name, pid)
                        if self._callback:
                            self._callback(process_name, pid, True)
                
                # 检测会话结束
                ended_sessions = self._known_sessions - current_sessions
                for pid in ended_sessions:
                    logger.info("音频会话结束: PID=%d", pid)
                
                # 更新已知会话
                self._known_sessions = current_sessions
                
                # 短暂睡眠，避免CPU占用过高
                time.sleep(1)  # 每秒检测一次
                
        except Exception as e:
            logger.error("音频会话监听器运行失败: %s", e)

    def _ensure_com(self) -> None:
        """确保COM已初始化"""
        if not self._com_initialized:
            try:
                pythoncom.CoInitialize()
                self._com_initialized = True
            except Exception as e:
                logger.error("COM初始化失败: %s", e)

    def _get_current_session_pids(self) -> Set[int]:
        """获取当前所有音频会话的PID"""
        pids = set()
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process:
                    pids.add(session.ProcessId)
        except Exception as e:
            logger.error("获取音频会话失败: %s", e)
        return pids

    @staticmethod
    def _get_process_name_by_pid(pid: int) -> Optional[str]:
        """通过PID获取进程名"""
        try:
            import psutil
            proc = psutil.Process(pid)
            return proc.name()
        except (ImportError, psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None