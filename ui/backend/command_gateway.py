"""Command gateway providing a single controlled entry point for UI user interactions."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable

from core.logger import get_logger
from ui.backend.event_bridge import event_bridge
from ui.backend.models import AvatarState, CommandRequest, CommandResponse, UIEventType

logger = get_logger(__name__)


class CommandGateway:
    """Manages command dispatch from the UI into NOVA's core turn execution queue."""

    def __init__(self, nova_app: Any = None) -> None:
        self.nova_app: Any = nova_app
        self._last_command_id: str | None = None
        self._lock: threading.RLock = threading.RLock()

    def bind_app(self, nova_app: Any) -> None:
        """Bind active NovaApplication instance."""
        with self._lock:
            self.nova_app = nova_app
            if hasattr(nova_app, "event_bus"):
                event_bridge.event_bus = nova_app.event_bus
                event_bridge._wire_event_bus()

    def submit_command(self, request: CommandRequest) -> CommandResponse:
        """Submit a user text or UI voice command into NOVA's processing queue."""
        raw_text = request.text.strip()
        if not raw_text:
            return CommandResponse(
                command_id=request.command_id,
                accepted=False,
                status="rejected",
                message="Cannot submit empty command.",
            )

        with self._lock:
            self._last_command_id = request.command_id

        logger.info("UI CommandGateway received command [%s]: '%s'", request.command_id, raw_text)

        # Notify UI of command reception
        event_bridge.emit_custom_event(
            event_type=UIEventType.COMMAND_RECEIVED,
            avatar_state=AvatarState.THINKING,
            message=f"Received: {raw_text}",
            data={"command_id": request.command_id, "text": raw_text, "source": request.source},
        )

        if self.nova_app is not None and hasattr(self.nova_app, "_turn_queue"):
            from main import TurnRequest
            self.nova_app._turn_queue.put(TurnRequest(source=request.source, text=raw_text))
            return CommandResponse(
                command_id=request.command_id,
                accepted=True,
                status="queued",
                message="Command queued for processing.",
            )
        else:
            # Standalone / headless mock execution for UI testing
            threading.Thread(
                target=self._simulate_mock_processing,
                args=(request,),
                daemon=True,
            ).start()
            return CommandResponse(
                command_id=request.command_id,
                accepted=True,
                status="processing",
                message="Processing command in standalone UI mode.",
            )

    def cancel_active_tasks(self) -> dict[str, Any]:
        """Trigger immediate cancellation of active autonomous tasks and computer actions."""
        logger.info("UI CommandGateway requested immediate task cancellation.")
        if self.nova_app is not None:
            if hasattr(self.nova_app, "task_executor"):
                self.nova_app.task_executor.cancel_task()
            if hasattr(self.nova_app, "computer_agent"):
                self.nova_app.computer_agent.stop_active_task()
            if hasattr(self.nova_app, "desktop_manager"):
                self.nova_app.desktop_manager.stop_active_task()
            if hasattr(self.nova_app, "browser_manager"):
                if hasattr(self.nova_app.browser_manager, "stop_active_task"):
                    self.nova_app.browser_manager.stop_active_task()

        event_bridge.emit_custom_event(
            event_type=UIEventType.TASK_CANCELLED,
            avatar_state=AvatarState.IDLE,
            message="Active task cancelled by user.",
        )
        return {"success": True, "message": "Cancelled active tasks."}

    def trigger_voice_listening(self) -> dict[str, Any]:
        """Trigger manual voice listening start."""
        event_bridge.emit_custom_event(
            event_type=UIEventType.VOICE_LISTENING_STARTED,
            avatar_state=AvatarState.LISTENING,
            message="Microphone active. Listening...",
        )
        return {"success": True, "listening": True}

    def _simulate_mock_processing(self, request: CommandRequest) -> None:
        """Fallback mock processor when running frontend without full audio hardware loop."""
        time.sleep(0.4)
        event_bridge.emit_custom_event(
            event_type=UIEventType.COMMAND_UNDERSTOOD,
            avatar_state=AvatarState.PLANNING,
            message=f"Understanding: {request.text}",
        )
        time.sleep(0.5)
        event_bridge.emit_custom_event(
            event_type=UIEventType.TASK_STEP_STARTED,
            avatar_state=AvatarState.EXECUTING,
            message=f"Executing: {request.text}",
        )
        time.sleep(0.6)
        event_bridge.emit_custom_event(
            event_type=UIEventType.SPEAKING_STARTED,
            avatar_state=AvatarState.SPEAKING,
            message=f"Completed {request.text} successfully.",
        )
        time.sleep(0.8)
        event_bridge.emit_custom_event(
            event_type=UIEventType.COMMAND_COMPLETED,
            avatar_state=AvatarState.SUCCESS,
            message=f"Task complete.",
        )
        time.sleep(1.0)
        event_bridge.emit_custom_event(
            event_type=UIEventType.BACKEND_STATUS,
            avatar_state=AvatarState.IDLE,
            message="Ready.",
        )

    def get_system_status(self) -> dict[str, Any]:
        """Query real status from bound NovaApplication subsystems."""
        app = self.nova_app
        if app is None:
            return {
                "core": {"status": "standalone_ui", "version": "v3.5"},
                "providers": {
                    "primary": "Gemini",
                    "active_model": "gemini-2.5-flash",
                    "fallback_available": True,
                    "available_providers": ["gemini", "groq", "cerebras"],
                },
                "voice": {
                    "available": True,
                    "vad_engine": "Silero VAD",
                    "stt_model": "Faster-Whisper",
                    "tts_voice": "af_heart (Kokoro)",
                    "is_listening": False,
                },
                "memory": {
                    "available": True,
                    "stored_entries_count": 0,
                },
                "mac_control": {
                    "available": True,
                    "accessibility_granted": True,
                },
            }

        active_provider = "Gemini"
        active_model = "gemini-2.5-flash"
        available_providers = ["gemini"]
        if getattr(app, "provider_manager", None) is not None:
            try:
                available_providers = [
                    p.value if hasattr(p, "value") else str(p)
                    for p in app.provider_manager.list_available_providers()
                ]
                if hasattr(app.provider_manager, "primary_provider"):
                    active_provider = app.provider_manager.primary_provider.provider_name
            except Exception:
                pass

        stored_entries = 0
        if getattr(app, "memory_manager", None) is not None:
            try:
                stored_entries = len(app.memory_manager.get_all_facts())
            except Exception:
                pass

        voice_avail = getattr(app, "voice_available", False)
        is_listening = False
        if voice_avail and getattr(app, "voice_manager", None) is not None:
            is_listening = getattr(app.voice_manager, "is_listening", False)

        return {
            "core": {
                "status": "online",
                "version": "v3.5",
                "active_project": getattr(getattr(app, "activity", None), "current_project", None) or "None",
            },
            "providers": {
                "primary": active_provider,
                "active_model": active_model,
                "fallback_available": len(available_providers) > 1,
                "available_providers": available_providers,
            },
            "voice": {
                "available": voice_avail,
                "vad_engine": "Silero VAD",
                "stt_model": "Faster-Whisper (small.en)",
                "tts_voice": "af_heart (Kokoro)",
                "is_listening": is_listening,
            },
            "memory": {
                "available": getattr(app, "memory_manager", None) is not None,
                "stored_entries_count": stored_entries,
            },
            "mac_control": {
                "available": getattr(app, "mac_control_manager", None) is not None,
                "accessibility_granted": True,
            },
        }


# Global singleton gateway
command_gateway = CommandGateway()
