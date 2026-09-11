"""Pydantic data models for NOVA UI V1 event system, avatar states, and command gateway."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AvatarState(str, Enum):
    """Core expressive visual states for the NOVA female AI avatar."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    SPEAKING = "speaking"
    SUCCESS = "success"
    CONFUSED = "confused"
    ERROR = "error"
    OFFLINE = "offline"


class UIEventType(str, Enum):
    """Event types broadcasted from the Python backend to the desktop UI."""

    # Lifecycle & Connection
    NOVA_STARTED = "nova_started"
    NOVA_READY = "nova_ready"
    BACKEND_STATUS = "backend_status"
    HEARTBEAT = "heartbeat"

    # Voice & Speech
    VOICE_LISTENING_STARTED = "voice_listening_started"
    VOICE_TRANSCRIPT_PARTIAL = "voice_transcript_partial"
    VOICE_TRANSCRIPT_FINAL = "voice_transcript_final"
    VOICE_LISTENING_STOPPED = "voice_listening_stopped"
    SPEAKING_STARTED = "speaking_started"
    SPEAKING_FINISHED = "speaking_finished"
    SPEECH_INTERRUPTED = "speech_interrupted"

    # Command Execution & Intent
    COMMAND_RECEIVED = "command_received"
    COMMAND_UNDERSTOOD = "command_understood"
    COMMAND_COMPLETED = "command_completed"
    COMMAND_FAILED = "command_failed"

    # Task Agent Multi-Step Execution
    TASK_PLANNED = "task_planned"
    TASK_STARTED = "task_started"
    TASK_STEP_STARTED = "task_step_started"
    TASK_STEP_COMPLETED = "task_step_completed"
    TASK_STEP_FAILED = "task_step_failed"
    TASK_REPLANNING = "task_replanning"
    TASK_COMPLETED = "task_completed"
    TASK_CANCELLED = "task_cancelled"

    # Screen Observation & Verification
    SCREEN_OBSERVE_STARTED = "screen_observe_started"
    SCREEN_OBSERVE_COMPLETED = "screen_observe_completed"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_COMPLETED = "verification_completed"

    # Privacy & Activity
    PRIVACY_STATE_CHANGED = "privacy_state_changed"
    ACTIVITY_LOG = "activity_log"
    NOVA_ERROR = "nova_error"


class PrivacyState(BaseModel):
    """Live hardware and sensor observation indicators for the privacy bar."""

    microphone_active: bool = False
    screen_observation_active: bool = False
    screen_recording_active: bool = False
    camera_active: bool = False
    task_executing: bool = False


class TaskStepItem(BaseModel):
    """Status item for a single step within an active multi-step autonomous plan."""

    step_index: int
    capability_name: str
    description: str
    status: str = "pending"  # "pending", "running", "completed", "failed", "cancelled"
    error: str | None = None


class UIEvent(BaseModel):
    """Structured event envelope streamed to UI clients."""

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    event_type: UIEventType
    timestamp: float = Field(default_factory=time.time)
    avatar_state: AvatarState = AvatarState.IDLE
    message: str = ""
    task_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    privacy: PrivacyState | None = None


class CommandRequest(BaseModel):
    """Inbound user command payload submitted from the UI."""

    command_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    text: str
    source: str = "ui"  # "ui", "voice_mic_btn", "chat_input"
    session_id: str | None = None


class CommandResponse(BaseModel):
    """Immediate acknowledgement returned to the UI upon command enqueue."""

    command_id: str
    accepted: bool
    status: str
    message: str = ""
