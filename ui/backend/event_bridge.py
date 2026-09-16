"""Event bridge translating NOVA internal EventBus events to sanitized UI event streams."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from core.event_bus import EventBus, NovaEvent
from core.logger import get_logger

from ui.backend.models import AvatarState, PrivacyState, UIEvent, UIEventType

logger = get_logger(__name__)


class EventBridge:
    """Subscribes to NOVA's internal EventBus and broadcasts sanitized events to UI clients."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus: EventBus = event_bus or EventBus()
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._current_avatar_state: AvatarState = AvatarState.IDLE
        self._privacy_state: PrivacyState = PrivacyState()
        self._activity_history: list[dict[str, Any]] = []
        self._lock: threading.RLock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wire_event_bus()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the async event loop for thread-safe websocket queue dispatch."""
        self._loop = loop

    @property
    def current_avatar_state(self) -> AvatarState:
        with self._lock:
            return self._current_avatar_state

    @property
    def privacy_state(self) -> PrivacyState:
        with self._lock:
            return self._privacy_state.model_copy()

    @property
    def activity_history(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._activity_history[-50:])

    def set_avatar_state(self, state: AvatarState, message: str = "") -> None:
        """Manually transition avatar state and broadcast to UI."""
        with self._lock:
            self._current_avatar_state = state
        self.emit_custom_event(
            event_type=UIEventType.BACKEND_STATUS,
            avatar_state=state,
            message=message,
        )

    def register_client(self, queue: asyncio.Queue[str]) -> None:
        """Register an active WebSocket client queue."""
        with self._lock:
            self._subscribers.add(queue)
        logger.debug("UI client connected. Total subscribers: %d", len(self._subscribers))

    def unregister_client(self, queue: asyncio.Queue[str]) -> None:
        """Remove a disconnected WebSocket client queue."""
        with self._lock:
            self._subscribers.discard(queue)
        logger.debug("UI client disconnected. Total subscribers: %d", len(self._subscribers))

    def emit_event(self, event: UIEvent) -> None:
        """Sanitize and broadcast a UIEvent to all connected subscribers."""
        # Sanitize event data
        clean_data = self._sanitize_dict(event.data)
        event.data = clean_data
        event.privacy = self.privacy_state

        with self._lock:
            self._current_avatar_state = event.avatar_state
            # Store in activity history if informative
            if event.message:
                self._activity_history.append({
                    "timestamp": event.timestamp,
                    "event_type": event.event_type.value,
                    "avatar_state": event.avatar_state.value,
                    "message": event.message,
                })
                if len(self._activity_history) > 100:
                    self._activity_history.pop(0)

        payload_json = event.model_dump_json()

        with self._lock:
            subscribers = list(self._subscribers)

        for q in subscribers:
            if self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(q.put_nowait, payload_json)
            else:
                try:
                    q.put_nowait(payload_json)
                except Exception:
                    pass

    def emit_custom_event(
        self,
        event_type: UIEventType,
        avatar_state: AvatarState = AvatarState.IDLE,
        message: str = "",
        task_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Convenience method to construct and broadcast a UIEvent."""
        evt = UIEvent(
            event_type=event_type,
            avatar_state=avatar_state,
            message=message,
            task_id=task_id,
            data=data or {},
            privacy=self.privacy_state,
        )
        self.emit_event(evt)

    _SENSITIVE_KEYWORDS: tuple[str, ...] = (
        "api_key",
        "secret",
        "token",
        "password",
        "auth",
        "credential",
        "cookie",
        "authorization",
        "bearer",
        "private_key",
        "raw_frame",
        "screenshot",
        "audio_buffer",
        "screen_buffer",
        "image_buffer",
    )

    def _sanitize_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        """Strip API keys, tokens, credentials, and raw buffers from event payloads."""
        clean: dict[str, Any] = {}
        for k, v in d.items():
            k_lower = k.lower()
            if any(secret_kw in k_lower for secret_kw in self._SENSITIVE_KEYWORDS):
                clean[k] = "******"
            elif isinstance(v, dict):
                clean[k] = self._sanitize_dict(v)
            elif isinstance(v, list):
                clean[k] = [
                    self._sanitize_dict(item) if isinstance(item, dict) else item
                    for item in v
                ]
            elif isinstance(v, (bytes, bytearray)):
                clean[k] = f"<{len(v)} bytes stripped>"
            elif isinstance(v, str) and (
                v.startswith("data:image/") or v.startswith("data:audio/")
            ):
                clean[k] = "<raw media buffer stripped>"
            elif isinstance(v, str) and len(v) > 2000:
                clean[k] = v[:2000] + "... [truncated]"
            else:
                clean[k] = v
        return clean

    def _wire_event_bus(self) -> None:
        """Subscribe to all standard NovaEvent topics."""
        event_map: dict[NovaEvent, tuple[UIEventType, AvatarState, str]] = {
            NovaEvent.APPLICATION_STARTED: (
                UIEventType.NOVA_STARTED,
                AvatarState.IDLE,
                "NOVA initialized and ready.",
            ),
            NovaEvent.LISTENING_STARTED: (
                UIEventType.VOICE_LISTENING_STARTED,
                AvatarState.LISTENING,
                "Listening for voice input...",
            ),
            NovaEvent.LISTENING_FINISHED: (
                UIEventType.VOICE_LISTENING_STOPPED,
                AvatarState.THINKING,
                "Processing speech...",
            ),
            NovaEvent.THINKING_STARTED: (
                UIEventType.COMMAND_UNDERSTOOD,
                AvatarState.THINKING,
                "Understanding command...",
            ),
            NovaEvent.SPEAKING_STARTED: (
                UIEventType.SPEAKING_STARTED,
                AvatarState.SPEAKING,
                "Speaking response...",
            ),
            NovaEvent.SPEAKING_FINISHED: (
                UIEventType.SPEAKING_FINISHED,
                AvatarState.IDLE,
                "Finished speaking.",
            ),
            NovaEvent.COMMAND_EXECUTED: (
                UIEventType.COMMAND_COMPLETED,
                AvatarState.SUCCESS,
                "Command executed successfully.",
            ),
            NovaEvent.BROWSER_ACTION_STARTED: (
                UIEventType.TASK_STEP_STARTED,
                AvatarState.EXECUTING,
                "Executing browser action...",
            ),
            NovaEvent.BROWSER_ACTION_COMPLETED: (
                UIEventType.TASK_STEP_COMPLETED,
                AvatarState.SUCCESS,
                "Browser action completed.",
            ),
            NovaEvent.DESKTOP_ACTION_STARTED: (
                UIEventType.TASK_STEP_STARTED,
                AvatarState.EXECUTING,
                "Executing desktop action...",
            ),
            NovaEvent.DESKTOP_ACTION_COMPLETED: (
                UIEventType.TASK_STEP_COMPLETED,
                AvatarState.SUCCESS,
                "Desktop action completed.",
            ),
            # Task Lifecycle Telemetry Mappings (Phase B)
            NovaEvent.TASK_CREATED: (
                UIEventType.TASK_STARTED,
                AvatarState.PLANNING,
                "Task initialized.",
            ),
            NovaEvent.TASK_UNDERSTANDING: (
                UIEventType.COMMAND_UNDERSTOOD,
                AvatarState.THINKING,
                "Understanding task...",
            ),
            NovaEvent.TASK_PLANNING: (
                UIEventType.TASK_PLANNED,
                AvatarState.PLANNING,
                "Formulating execution plan...",
            ),
            NovaEvent.TASK_OBSERVING: (
                UIEventType.SCREEN_OBSERVE_STARTED,
                AvatarState.EXECUTING,
                "Observing environment...",
            ),
            NovaEvent.TASK_STEP_STARTED: (
                UIEventType.TASK_STEP_STARTED,
                AvatarState.EXECUTING,
                "Step execution started.",
            ),
            NovaEvent.TASK_ACTION_STARTED: (
                UIEventType.TASK_STEP_STARTED,
                AvatarState.EXECUTING,
                "Executing action...",
            ),
            NovaEvent.TASK_ACTION_COMPLETED: (
                UIEventType.TASK_STEP_COMPLETED,
                AvatarState.EXECUTING,
                "Action execution completed.",
            ),
            NovaEvent.TASK_VERIFICATION_STARTED: (
                UIEventType.VERIFICATION_STARTED,
                AvatarState.VERIFYING,
                "Verifying step outcome...",
            ),
            NovaEvent.TASK_VERIFICATION_COMPLETED: (
                UIEventType.VERIFICATION_COMPLETED,
                AvatarState.VERIFYING,
                "Step verification completed.",
            ),
            NovaEvent.TASK_RECOVERY_STARTED: (
                UIEventType.TASK_STEP_STARTED,
                AvatarState.EXECUTING,
                "Attempting recovery action...",
            ),
            NovaEvent.TASK_REPLANNING: (
                UIEventType.TASK_REPLANNING,
                AvatarState.PLANNING,
                "Dynamically replanning steps...",
            ),
            NovaEvent.TASK_WAITING_USER: (
                UIEventType.BACKEND_STATUS,
                AvatarState.CONFUSED,
                "Waiting for user confirmation.",
            ),
            NovaEvent.TASK_PAUSED: (
                UIEventType.BACKEND_STATUS,
                AvatarState.IDLE,
                "Task execution paused.",
            ),
            NovaEvent.TASK_RESUMED: (
                UIEventType.BACKEND_STATUS,
                AvatarState.EXECUTING,
                "Task execution resumed.",
            ),
            NovaEvent.TASK_COMPLETED: (
                UIEventType.TASK_COMPLETED,
                AvatarState.SUCCESS,
                "Task completed successfully.",
            ),
            NovaEvent.TASK_FAILED: (
                UIEventType.TASK_STEP_FAILED,
                AvatarState.ERROR,
                "Task execution failed.",
            ),
            NovaEvent.TASK_CANCELLED: (
                UIEventType.TASK_CANCELLED,
                AvatarState.IDLE,
                "Task execution cancelled.",
            ),
        }

        for nova_evt, (ui_evt_type, av_state, default_msg) in event_map.items():
            def _create_handler(
                u_type=ui_evt_type, a_state=av_state, d_msg=default_msg, n_evt=nova_evt
            ):
                def _handler(name: str, payload: dict[str, Any]) -> None:
                    # Update privacy state tracking for task execution
                    if n_evt in (
                        NovaEvent.TASK_CREATED,
                        NovaEvent.TASK_STEP_STARTED,
                        NovaEvent.TASK_ACTION_STARTED,
                    ):
                        with self._lock:
                            self._privacy_state.task_executing = True
                    elif n_evt in (
                        NovaEvent.TASK_COMPLETED,
                        NovaEvent.TASK_FAILED,
                        NovaEvent.TASK_CANCELLED,
                    ):
                        with self._lock:
                            self._privacy_state.task_executing = False

                    msg = payload.get("message") or d_msg
                    self.emit_custom_event(
                        event_type=u_type,
                        avatar_state=a_state,
                        message=msg,
                        task_id=payload.get("task_id"),
                        data=payload,
                    )

                return _handler

            self.event_bus.subscribe(nova_evt, _create_handler())


# Global singleton bridge
event_bridge = EventBridge()
