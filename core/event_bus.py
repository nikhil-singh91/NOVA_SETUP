"""Application-wide publish/subscribe event bus for NOVA."""

from __future__ import annotations

import threading
from enum import Enum
from typing import Any, Callable

from core.logger import get_logger

logger = get_logger(__name__)

EventHandler = Callable[[str, dict[str, Any]], None]


class NovaEvent(str, Enum):
    """Observational events NOVA emits for UI and plugins."""

    APPLICATION_STARTED = "application_started"
    APPLICATION_SHUTDOWN = "application_shutdown"
    WAKE_WORD_DETECTED = "wake_word_detected"
    LISTENING_STARTED = "listening_started"
    LISTENING_PARTIAL = "listening_partial"
    LISTENING_FINISHED = "listening_finished"
    THINKING_STARTED = "thinking_started"
    RESPONSE_GENERATED = "response_generated"
    SPEAKING_STARTED = "speaking_started"
    SPEAKING_FINISHED = "speaking_finished"
    SPEECH_INTERRUPTED = "speech_interrupted"
    STATE_CHANGED = "state_changed"
    HEALTH_UPDATE = "health_update"
    COMMAND_EXECUTED = "command_executed"
    BROWSER_ACTION_STARTED = "browser_action_started"
    BROWSER_ACTION_COMPLETED = "browser_action_completed"
    BROWSER_ACTION_FAILED = "browser_action_failed"
    BROWSER_ACTION_CANCELLED = "browser_action_cancelled"
    BROWSER_TASK_STARTED = "browser_task_started"
    BROWSER_TASK_STEP_COMPLETED = "browser_task_step_completed"
    BROWSER_TASK_COMPLETED = "browser_task_completed"
    BROWSER_TASK_CANCELLED = "browser_task_cancelled"
    BROWSER_PAGE_EXTRACTED = "browser_page_extracted"
    DESKTOP_ACTION_STARTED = "desktop_action_started"
    DESKTOP_ACTION_COMPLETED = "desktop_action_completed"
    DESKTOP_ACTION_FAILED = "desktop_action_failed"
    DESKTOP_ACTION_CANCELLED = "desktop_action_cancelled"
    CAMERA_CAPTURE_STARTED = "camera_capture_started"
    CAMERA_CAPTURE_COMPLETED = "camera_capture_completed"
    CAMERA_CAPTURE_FAILED = "camera_capture_failed"


class EventBus:
    """Thread-safe publish/subscribe mechanism."""

    def __init__(self) -> None:
        self._lock: threading.RLock = threading.RLock()
        self._subscribers: dict[NovaEvent, list[EventHandler]] = {}

    def subscribe(self, event: NovaEvent, handler: EventHandler) -> None:
        with self._lock:
            self._subscribers.setdefault(event, []).append(handler)

    def unsubscribe(self, event: NovaEvent, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._subscribers.get(event)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def publish(self, event: NovaEvent, **payload: Any) -> None:
        with self._lock:
            handlers = tuple(self._subscribers.get(event, ()))

        for handler in handlers:
            try:
                handler(event.value, payload)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Event subscriber failed for '%s': %s", event.value, exc, exc_info=True
                )


__all__ = ["EventBus", "EventHandler", "NovaEvent"]
