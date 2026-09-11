"""NOVA Voice V2: High-reliability, modular, human-like voice interaction system."""

from __future__ import annotations

from voice.diagnostics import VoiceDiagnostics
from voice.manager import VoiceManager
from voice.microphone import MicrophoneManager
from voice.quality import TranscriptQualityGate
from voice.speaker import SpeakerManager
from voice.state import QualityCheckResult, QualityDecision, SpeechOutputResult, TranscriptionResult, VADState, VoiceState
from voice.transcriber import TranscriptionManager
from voice.vad import VoiceActivityDetector

__all__ = [
    "VoiceManager",
    "VoiceState",
    "VADState",
    "TranscriptionResult",
    "SpeechOutputResult",
    "QualityDecision",
    "QualityCheckResult",
    "TranscriptQualityGate",
    "MicrophoneManager",
    "VoiceActivityDetector",
    "TranscriptionManager",
    "SpeakerManager",
    "VoiceDiagnostics",
]

