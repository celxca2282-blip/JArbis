# app_state.py
"""
Состояние ассистента для GUI и движка.
"""

from dataclasses import dataclass, field
from enum import Enum


class AssistantStatus(str, Enum):
    """Статусы голосового ассистента для статус-орба."""

    IDLE = "idle"
    WAKE = "wake"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class AppStateSnapshot:
    """Снимок состояния для отображения в GUI."""

    status: AssistantStatus = AssistantStatus.IDLE
    is_running: bool = False
    last_stt_raw: str = ""
    last_stt_normalized: str = ""
    last_response: str = ""
    scenario_progress: str = ""
    event_log: list[str] = field(default_factory=list)
    tts_muted: bool = False

    def append_event(self, message: str, limit: int = 50) -> None:
        self.event_log.append(message)
        if len(self.event_log) > limit:
            self.event_log = self.event_log[-limit:]
