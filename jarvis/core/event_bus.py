# event_bus.py
"""
Потокобезопасная шина событий между AssistantEngine и GUI.
"""

import threading
from dataclasses import dataclass, field
from enum import Enum
from queue import Empty, Queue
from typing import Any


class EventType(str, Enum):
    """Типы событий ассистента."""

    STATUS_CHANGED = "status_changed"
    STT_RAW = "stt_raw"
    STT_NORMALIZED = "stt_normalized"
    RESPONSE = "response"
    ERROR = "error"
    LOG_LINE = "log_line"
    MIC_LEVEL = "mic_level"
    APP_LAUNCHED = "app_launched"
    SCENARIO_STEP_STARTED = "scenario_step_started"
    SCENARIO_COMPLETED = "scenario_completed"
    ENGINE_STARTED = "engine_started"
    ENGINE_STOPPED = "engine_stopped"


@dataclass
class Event:
    """Событие для GUI."""

    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Очередь событий с единственным экземпляром на приложение."""

    _instance: "EventBus | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._queue: Queue[Event] = Queue()

    @classmethod
    def instance(cls) -> "EventBus":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Сбрасывает singleton (для тестов)."""
        with cls._lock:
            cls._instance = None

    def publish(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        try:
            self._queue.put(Event(type=event_type, data=data or {}))
        except Exception:
            pass

    def poll_all(self) -> list[Event]:
        events: list[Event] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except Empty:
                break
        return events
