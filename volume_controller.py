import pythoncom

from pycaw.pycaw import AudioUtilities

from logger import setup_logger

logger = setup_logger("VolumeController")


class AudioSessionInfo:
    __slots__ = ("pid", "process_name", "volume_interface", "is_muted", "volume_level")

    def __init__(
        self,
        pid: int,
        process_name: str,
        volume_interface,
        is_muted: bool,
        volume_level: float,
    ):
        self.pid = pid
        self.process_name = process_name
        self.volume_interface = volume_interface
        self.is_muted = is_muted
        self.volume_level = volume_level


class VolumeController:
    def __init__(self):
        self._previous_states: dict[int, tuple[bool, float]] = {}
        self._com_initialized = False

    def _ensure_com(self) -> None:
        if not self._com_initialized:
            try:
                pythoncom.CoInitialize()
                self._com_initialized = True
            except Exception as e:
                logger.error("COM初始化失败: %s", e)

    def get_all_sessions(self) -> list[AudioSessionInfo]:
        sessions = []
        try:
            self._ensure_com()
            audio_sessions = AudioUtilities.GetAllSessions()

            for session in audio_sessions:
                try:
                    if session.Process is None:
                        continue

                    pid = session.ProcessId
                    if pid == 0:
                        continue

                    process_name = session.Process.name()
                    if not process_name:
                        continue

                    volume = session.SimpleAudioVolume
                    if volume is None:
                        continue

                    is_muted = volume.GetMute()
                    volume_level = volume.GetMasterVolume()

                    sessions.append(
                        AudioSessionInfo(
                            pid=pid,
                            process_name=process_name,
                            volume_interface=volume,
                            is_muted=is_muted,
                            volume_level=volume_level,
                        )
                    )
                except Exception as e:
                    logger.debug("处理音频会话时出错: %s", e)
                    continue

        except Exception as e:
            logger.error("获取音频会话失败: %s", e)

        return sessions

    def mute_process(self, session: AudioSessionInfo) -> bool:
        if session.is_muted:
            return True

        try:
            self._previous_states[session.pid] = (session.is_muted, session.volume_level)
            session.volume_interface.SetMute(True, None)
            logger.debug("已静音: %s (PID: %d)", session.process_name, session.pid)
            return True
        except Exception as e:
            logger.error("静音失败 %s (PID: %d): %s", session.process_name, session.pid, e)
            return False

    def was_muted_by_us(self, pid: int) -> bool:
        return pid in self._previous_states

    def get_muted_pids(self) -> set[int]:
        return set(self._previous_states.keys())

    def unmute_process(self, session: AudioSessionInfo) -> bool:
        try:
            session.volume_interface.SetMute(False, None)
            if session.pid in self._previous_states:
                del self._previous_states[session.pid]
            logger.info("已取消静音: %s (PID: %d)", session.process_name, session.pid)
            return True
        except Exception as e:
            logger.error("取消静音失败 %s (PID: %d): %s", session.process_name, session.pid, e)
            return False

    def cleanup_stale_entries(self, active_pids: set[int]) -> None:
        stale = [pid for pid in self._previous_states if pid not in active_pids]
        for pid in stale:
            del self._previous_states[pid]
