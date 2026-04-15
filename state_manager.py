from typing import Dict, Optional, Set, Tuple
import threading
import time

from logger import setup_logger
from volume_controller import AudioSessionInfo, VolumeController

logger = setup_logger("StateManager")


class StateManager:
    def __init__(self, config_manager):
        self._config = config_manager
        self._volume_ctrl = VolumeController()
        self._session_cache: Dict[int, AudioSessionInfo] = {}
        self._foreground_pid: Optional[int] = None
        self._foreground_name: Optional[str] = None
        self._muted_pids: Set[int] = set()
        self._lock = threading.RLock()
        self._last_sync_time = 0

    def update_foreground(self, pid: int, name: str) -> None:
        """更新前台进程信息"""
        with self._lock:
            self._foreground_pid = pid
            self._foreground_name = name
            logger.info("前台进程更新: %s (PID: %d)", name, pid)
            # 前台进程变化时，重新评估所有音频会话
            self._evaluate_all_sessions()

    def add_session(self, process_name: str, pid: int, is_created: bool) -> None:
        """添加音频会话"""
        with self._lock:
            # 刷新会话缓存
            self._refresh_session_cache()
            # 评估新会话
            if pid in self._session_cache:
                session = self._session_cache[pid]
                self._evaluate_session(session)

    def remove_session(self, pid: int) -> None:
        """移除音频会话"""
        with self._lock:
            if pid in self._session_cache:
                del self._session_cache[pid]
            if pid in self._muted_pids:
                self._muted_pids.remove(pid)
            logger.info("音频会话移除: PID=%d", pid)

    def _refresh_session_cache(self) -> None:
        """刷新会话缓存"""
        try:
            sessions = self._volume_ctrl.get_all_sessions()
            new_cache = {session.pid: session for session in sessions}
            
            # 检测会话变化
            old_pids = set(self._session_cache.keys())
            new_pids = set(new_cache.keys())
            
            added_pids = new_pids - old_pids
            removed_pids = old_pids - new_pids
            
            for pid in added_pids:
                logger.debug("会话缓存添加: %s (PID: %d)", new_cache[pid].process_name, pid)
            
            for pid in removed_pids:
                logger.debug("会话缓存移除: PID=%d", pid)
                if pid in self._muted_pids:
                    self._muted_pids.remove(pid)
            
            self._session_cache = new_cache
        except Exception as e:
            logger.error("刷新会话缓存失败: %s", e)

    def _evaluate_all_sessions(self) -> None:
        """评估所有音频会话的静音状态"""
        with self._lock:
            self._refresh_session_cache()
            for session in self._session_cache.values():
                self._evaluate_session(session)

    def _evaluate_session(self, session: AudioSessionInfo) -> None:
        """评估单个音频会话的静音状态"""
        if not self._config.enabled:
            return
        
        is_foreground = session.pid == self._foreground_pid
        is_foreground_app = session.process_name == self._foreground_name
        is_whitelisted = self._config.is_whitelisted(session.process_name)
        
        logger.debug(
            "评估会话: %s (PID: %d), 前台: %s, 前台应用: %s, 白名单: %s, 当前静音: %s",
            session.process_name,
            session.pid,
            is_foreground,
            is_foreground_app,
            is_whitelisted,
            session.is_muted
        )
        
        if is_foreground or is_foreground_app or is_whitelisted:
            # 需要取消静音
            if session.is_muted:
                if self._volume_ctrl.unmute_process(session):
                    if session.pid in self._muted_pids:
                        self._muted_pids.remove(session.pid)
                    logger.info("取消静音: %s (PID: %d)", session.process_name, session.pid)
        else:
            # 需要静音
            if not session.is_muted:
                if self._volume_ctrl.mute_process(session):
                    self._muted_pids.add(session.pid)
                    logger.info("静音: %s (PID: %d)", session.process_name, session.pid)

    def sync(self) -> None:
        """同步状态（兜底机制）"""
        current_time = time.time()
        if current_time - self._last_sync_time >= 10:  # 每10秒同步一次
            self._last_sync_time = current_time
            logger.debug("执行兜底同步")
            self._evaluate_all_sessions()

    def restore_all(self) -> None:
        """恢复所有被静音的会话"""
        with self._lock:
            for session in self._session_cache.values():
                if session.pid in self._muted_pids:
                    self._volume_ctrl.unmute_process(session)
            self._muted_pids.clear()
            logger.info("已恢复所有静音的音频会话")

    def get_muted_pids(self) -> Set[int]:
        """获取被静音的PID集合"""
        with self._lock:
            return set(self._muted_pids)

    def get_session_count(self) -> int:
        """获取当前会话数量"""
        with self._lock:
            return len(self._session_cache)