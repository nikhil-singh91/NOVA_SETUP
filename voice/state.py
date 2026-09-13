"""Canonical Voice State, Events, and Data Models for NOVA Voice V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class VoiceState(str, Enum):
    """Canonical voice lifecycle and turn states.

    Attributes:
        IDLE: Subsystem is initialized but not actively recording.
        LISTENING: Microphone is actively streaming and VAD is listening for user speech.
        PROCESSING: Speech has been captured and is being transcribed / analyzed by NOVA core.
        SPEAKING: Text-to-speech output is currently playing through the speakers.
        MUTED: Audio capture is temporarily suspended.
        ERROR: Subsystem encountered an unrecoverable hardware or software fault.
    """

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    MUTED = "muted"
    ERROR = "error"


class VADState(str, Enum):
    """Voice Activity Detector internal state."""

    SILENCE = "silence"
    SPEECH_START = "speech_start"
    IN_SPEECH = "in_speech"
    SPEECH_FINALIZED = "speech_finalized"


@dataclass(frozen=True)
class VoiceStateEvent:
    """Event emitted whenever the voice state transitions."""

    old_state: VoiceState
    new_state: VoiceState
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioChunk:
    """A raw or preprocessed slice of microphone audio data."""

    data: bytes
    rms: float
    peak: float
    is_speech: bool = False
    timestamp: float = 0.0


class QualityDecision(str, Enum):
    """Categorical classification of transcript quality gate evaluation."""

    ACCEPTED = "accepted"
    UNCERTAIN = "uncertain"
    REJECTED_NOISE = "rejected_noise"
    REJECTED_HALLUCINATION = "rejected_hallucination"
    REJECTED_EMPTY = "rejected_empty"


@dataclass
class QualityCheckResult:
    """Detailed outcome of a TranscriptQualityGate evaluation."""

    accepted: bool
    decision: QualityDecision
    confidence: float
    transcript: str
    reason: str
    is_command_candidate: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptionResult:
    """The structured output of a speech transcription operation."""

    text: str
    confidence: float = 1.0
    language: str = "en"
    duration_seconds: float = 0.0
    speech_duration: float = 0.0
    no_speech_prob: float = 0.0
    avg_logprob: float = 0.0
    compression_ratio: float = 1.0
    is_final: bool = True
    provider_name: str = "faster_whisper"
    error: str | None = None
    quality: QualityCheckResult | None = None
    raw_text: str = ""
    normalized_text: str = ""
    interpreted_text: str = ""
    alternatives: list[str] = field(default_factory=list)
    word_tokens: list[dict[str, Any]] = field(default_factory=list)
    audio_event: str = "none"
    is_isolated_audio_event: bool = False

    def __post_init__(self) -> None:
        if not self.raw_text:
            self.raw_text = self.text
        if not self.normalized_text:
            self.normalized_text = self.text

    @property
    def success(self) -> bool:
        """Return True if transcription succeeded and text is non-empty."""
        return self.error is None and bool(self.text and self.text.strip())


@dataclass
class SpeechOutputResult:
    """The structured output of a speech synthesis / playback operation."""

    success: bool
    text: str
    duration_seconds: float = 0.0
    engine_name: str = "edge_tts"
    error: str | None = None

