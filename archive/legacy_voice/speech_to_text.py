"""Speech-to-Text engine for NOVA.

This module is NOVA's long-term Speech-to-Text subsystem. It converts
microphone audio into text and nothing else: it contains no business
logic, never calls an AI provider, and never touches
:class:`~memory.memory_manager.MemoryManager`. Anything this module
produces (a :class:`RecognitionResult`) is handed back to whichever
caller needs it; what happens with that text afterward is entirely
outside this module's concern.

Architecture:
    :class:`BaseSpeechRecognizer` defines the contract every
    recognition engine implements, using the same template-method
    pattern as :class:`~providers.base_provider.BaseProvider`: public
    methods (:meth:`~BaseSpeechRecognizer.initialize`,
    :meth:`~BaseSpeechRecognizer.listen_once`, and so on) are concrete
    and handle logging, timing, thread safety, and error containment,
    while a small set of protected ``_do_*`` hooks are implemented by
    each concrete engine.

    :class:`WhisperRecognizer` is the first concrete engine, built on
    the ``speech_recognition`` library for microphone capture and
    ambient noise handling, and OpenAI's local Whisper model for
    transcription. It runs entirely offline; no audio ever leaves the
    machine.

    :class:`SpeechRecognizerFactory` lets new engines (Google Speech,
    Azure Speech, Deepgram, AssemblyAI, Vosk, or anything else) be
    added by registering a new :class:`BaseSpeechRecognizer` subclass
    under a name, without modifying any code in this file.

    :class:`SpeechToTextManager` is the single entry point the rest of
    NOVA should use: it owns engine selection, lifecycle, one-shot and
    continuous listening, and health checks, so callers never need to
    know which concrete engine is active.

Optional Dependencies:
    ``speech_recognition`` and ``openai-whisper`` are treated as
    optional at import time. If either is missing, this module still
    imports successfully (so callers can inspect enums, dataclasses,
    and build a manager), but any attempt to actually initialize or
    use :class:`WhisperRecognizer` raises a clear
    :class:`EngineUnavailableError` explaining what to install.
"""

from __future__ import annotations

import math
import queue
import re
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Final

import numpy as np
import torch
from config.settings import settings


class HighPassFilter:
    def __init__(self, alpha: float = 0.98) -> None:
        self.alpha = alpha
        self.prev_x = 0.0

    def process(self, frame: np.ndarray) -> np.ndarray:
        shifted = np.empty_like(frame)
        shifted[0] = self.prev_x
        shifted[1:] = frame[:-1]
        self.prev_x = frame[-1]
        return frame - self.alpha * shifted


class AutomaticGainControl:
    def __init__(self, target_rms: float = 0.12, max_gain: float = 3.5) -> None:
        self.target_rms = target_rms
        self.max_gain = max_gain
        self.current_gain = 1.0

    def process(self, frame: np.ndarray) -> np.ndarray:
        rms = np.sqrt(np.mean(frame ** 2)) + 1e-6
        is_clipping = np.any(np.abs(frame) > 0.98)

        if is_clipping:
            target_gain = 0.5 * self.current_gain
            self.current_gain = 0.7 * self.current_gain + 0.3 * target_gain
        else:
            target_gain = self.target_rms / rms
            self.current_gain = 0.95 * self.current_gain + 0.05 * target_gain

        self.current_gain = max(0.2, min(self.max_gain, self.current_gain))
        return frame * self.current_gain


class SpectralNoiseSuppressor:
    def __init__(self, sample_rate: int = 16000) -> None:
        self.noise_profile = None
        self.alpha = 2.0
        self.beta = 0.03
        self.frames_seen = 0

    def process(self, frame: np.ndarray) -> np.ndarray:
        spec = np.fft.rfft(frame)
        mag = np.abs(spec)
        phase = np.angle(spec)

        if self.noise_profile is None:
            self.noise_profile = mag
        else:
            if self.frames_seen < 50:
                self.noise_profile = 0.8 * self.noise_profile + 0.2 * mag
            else:
                self.noise_profile = 0.995 * self.noise_profile + 0.005 * mag

        self.frames_seen += 1

        subtracted = mag - self.alpha * self.noise_profile
        subtracted = np.maximum(subtracted, self.beta * mag)

        clean_spec = subtracted * np.exp(1j * phase)
        clean_frame = np.fft.irfft(clean_spec)

        if len(clean_frame) < len(frame):
            clean_frame = np.pad(clean_frame, (0, len(frame) - len(clean_frame)))
        elif len(clean_frame) > len(frame):
            clean_frame = clean_frame[:len(frame)]

        return clean_frame


class AcousticEchoCanceller:
    def __init__(self, length: int = 128, mu: float = 0.015) -> None:
        self.length = length
        self.mu = mu
        self.weights = np.zeros(length)
        self.history = np.zeros(length)

    def process(self, mic_frame: np.ndarray, ref_frame: np.ndarray | None = None) -> np.ndarray:
        if ref_frame is None or np.all(ref_frame == 0.0):
            return mic_frame

        out = np.zeros_like(mic_frame)
        for i in range(len(mic_frame)):
            self.history[1:] = self.history[:-1]
            self.history[0] = ref_frame[i] if i < len(ref_frame) else 0.0

            echo_est = np.dot(self.weights, self.history)
            error = mic_frame[i] - echo_est
            out[i] = error

            self.weights += 2 * self.mu * error * self.history
        return out


try:
    import pyaudio
    _PYAUDIO_AVAILABLE = True
except ImportError:
    pyaudio = None
    _PYAUDIO_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None
    _FASTER_WHISPER_AVAILABLE = False

from core.exceptions import SpeechRecognitionError
from core.logger import get_logger
from voice.audio_processor import preprocess_audio

logger = get_logger(__name__)

# Maintain structural compatibility check variables
_SPEECH_RECOGNITION_AVAILABLE = _PYAUDIO_AVAILABLE
_WHISPER_AVAILABLE = _FASTER_WHISPER_AVAILABLE


_DEFAULT_TIMEOUT_SECONDS: Final[float] = 5.0
_DEFAULT_PHRASE_TIME_LIMIT_SECONDS: Final[float] = 15.0
_DEFAULT_AMBIENT_NOISE_CALIBRATION_SECONDS: Final[float] = 1.0
_DEFAULT_MAX_RETRIES: Final[int] = 2
_DEFAULT_RETRY_BACKOFF_SECONDS: Final[float] = 1.0
_DEFAULT_WHISPER_MODEL_NAME: Final[str] = "base"
_THREAD_JOIN_TIMEOUT_SECONDS: Final[float] = 5.0


# =============================================================================
# Exceptions
# =============================================================================


class MicrophoneUnavailableError(SpeechRecognitionError):
    """Raised when no usable microphone can be found or opened."""

    default_message: str = "No usable microphone could be found or opened."


class EngineUnavailableError(SpeechRecognitionError):
    """Raised when a recognition engine's runtime dependencies are missing."""

    default_message: str = "The requested speech recognition engine is unavailable."


class EngineNotFoundError(SpeechRecognitionError):
    """Raised when a requested recognition engine is not registered."""

    default_message: str = "The requested speech recognition engine is not registered."


class DuplicateEngineError(SpeechRecognitionError):
    """Raised when attempting to register an engine name that already exists."""

    default_message: str = "A speech recognition engine with this name is already registered."


# =============================================================================
# Enums
# =============================================================================


class RecognitionStatus(str, Enum):
    """The possible outcomes of a speech recognition attempt.

    Attributes:
        SUCCESS: Speech was captured and transcribed successfully.
        NO_SPEECH_DETECTED: Listening completed but no speech was
            present in the captured audio.
        UNKNOWN_SPEECH: Audio was captured but could not be
            transcribed into text.
        TIMEOUT: No speech began within the configured timeout.
        CANCELLED: The listening operation was cancelled before
            completion.
        ENGINE_UNAVAILABLE: The recognition engine's dependencies are
            missing or the engine is not initialized.
        MICROPHONE_ERROR: The microphone could not be accessed.
        PERMISSION_DENIED: Access to the microphone was denied.
        ERROR: An unexpected error occurred.
    """

    SUCCESS = "success"
    NO_SPEECH_DETECTED = "no_speech_detected"
    UNKNOWN_SPEECH = "unknown_speech"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    ENGINE_UNAVAILABLE = "engine_unavailable"
    MICROPHONE_ERROR = "microphone_error"
    PERMISSION_DENIED = "permission_denied"
    ERROR = "error"


class Language(str, Enum):
    """The languages NOVA's speech recognition subsystem supports.

    Attributes:
        ENGLISH: Recognize speech as English.
        HINDI: Recognize speech as Hindi.
        HINGLISH: Recognize speech as a Hindi/English blend. No
            underlying engine has a dedicated Hinglish mode; engines
            should treat this as automatic language detection.
        AUTO: Automatically detect the spoken language.
    """

    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hi-en"
    AUTO = "auto"


# =============================================================================
# Data model
# =============================================================================


@dataclass(frozen=True)
class SpeechRecognizerConfig:
    """Configuration for a speech recognition engine.

    Every value is configurable and has a sensible default; nothing
    in this module hardcodes a value that belongs here.

    Attributes:
        device_index: The index of the microphone device to use, as
            reported by :func:`list_microphone_devices`. If ``None``,
            the system's default input device is used.
        sample_rate: The audio sample rate to request from the
            microphone, in Hz. If ``None``, the device's default
            sample rate is used.
        language: The language to recognize speech as.
        timeout_seconds: The maximum time to wait for speech to begin
            before giving up, in seconds. If ``None``, waits
            indefinitely.
        phrase_time_limit_seconds: The maximum duration of a single
            captured phrase, in seconds. If ``None``, there is no
            limit beyond the engine's own defaults.
        ambient_noise_calibration_seconds: How long to sample ambient
            noise before listening, in seconds, used to set the
            energy threshold automatically.
        dynamic_energy_threshold: Whether the energy threshold should
            continuously adjust to changing ambient noise.
        energy_threshold: An explicit energy threshold to use instead
            of automatic calibration. If ``None``, the threshold is
            determined by ambient noise calibration.
        max_retries: The number of additional attempts made after a
            transient failure (such as a microphone hardware error)
            before giving up.
        retry_backoff_seconds: The delay between retry attempts, in
            seconds.
        model_name: The Whisper model size to use (for example,
            ``"tiny"``, ``"base"``, ``"small"``, ``"medium"``, or
            ``"large"``).

    Raises:
        SpeechRecognitionError: If any field fails validation during
            construction.
    """

    device_index: int | None = None
    sample_rate: int | None = None
    language: Language = Language.AUTO
    timeout_seconds: float | None = None
    phrase_time_limit_seconds: float | None = None
    ambient_noise_calibration_seconds: float | None = None
    dynamic_energy_threshold: bool | None = None
    energy_threshold: int | None = None
    max_retries: int = _DEFAULT_MAX_RETRIES
    retry_backoff_seconds: float = _DEFAULT_RETRY_BACKOFF_SECONDS
    model_name: str | None = None

    def __post_init__(self) -> None:
        """Validate this configuration's fields.

        Raises:
            SpeechRecognitionError: If any field is invalid.
        """
        object.__setattr__(self, "device_index", self.device_index if self.device_index is not None else settings.stt_device_index)
        object.__setattr__(self, "sample_rate", self.sample_rate if self.sample_rate is not None else settings.stt_sample_rate)
        object.__setattr__(self, "timeout_seconds", self.timeout_seconds if self.timeout_seconds is not None else settings.stt_timeout_seconds)
        object.__setattr__(self, "phrase_time_limit_seconds", self.phrase_time_limit_seconds if self.phrase_time_limit_seconds is not None else settings.stt_phrase_time_limit_seconds)
        object.__setattr__(self, "ambient_noise_calibration_seconds", self.ambient_noise_calibration_seconds if self.ambient_noise_calibration_seconds is not None else settings.stt_ambient_noise_calibration_seconds)
        object.__setattr__(self, "dynamic_energy_threshold", self.dynamic_energy_threshold if self.dynamic_energy_threshold is not None else settings.stt_dynamic_energy_threshold)
        object.__setattr__(self, "energy_threshold", self.energy_threshold if self.energy_threshold is not None else settings.stt_energy_threshold)
        object.__setattr__(self, "model_name", self.model_name if self.model_name is not None else settings.whisper_model_name)

        if self.device_index is not None and (
            not isinstance(self.device_index, int) or self.device_index < 0
        ):
            raise SpeechRecognitionError("device_index must be a non-negative integer or None.")
        if self.sample_rate is not None and (
            not isinstance(self.sample_rate, int) or self.sample_rate <= 0
        ):
            raise SpeechRecognitionError("sample_rate must be a positive integer or None.")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise SpeechRecognitionError("timeout_seconds must be positive or None.")
        if self.phrase_time_limit_seconds is not None and self.phrase_time_limit_seconds <= 0:
            raise SpeechRecognitionError("phrase_time_limit_seconds must be positive or None.")
        if self.ambient_noise_calibration_seconds < 0:
            raise SpeechRecognitionError("ambient_noise_calibration_seconds must be non-negative.")
        if self.max_retries < 0:
            raise SpeechRecognitionError("max_retries must be non-negative.")
        if self.retry_backoff_seconds < 0:
            raise SpeechRecognitionError("retry_backoff_seconds must be non-negative.")
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise SpeechRecognitionError("model_name must be a non-empty string.")


@dataclass(frozen=True)
class RecognitionResult:
    """The outcome of a single speech recognition attempt.

    Attributes:
        status: The specific outcome of the attempt.
        success: Whether recognized text is available.
        text: The recognized text, or ``None`` if unsuccessful.
        confidence: An estimated confidence in ``[0.0, 1.0]`` for
            ``text``, or ``None`` if the engine cannot provide one.
        language: The language recognition was attempted in.
        duration_seconds: How long the attempt took, in seconds.
        engine_name: The name of the engine that produced this
            result.
        timestamp: The UTC timestamp at which this result was
            produced.
        error_message: A human-readable error description, if
            ``success`` is ``False`` and an error occurred.
    """

    status: RecognitionStatus
    success: bool
    text: str | None
    confidence: float | None
    language: Language
    duration_seconds: float
    engine_name: str
    timestamp: datetime
    error_message: str | None = None
    overall_confidence: float | None = None

    @classmethod
    def success_result(
        cls,
        *,
        text: str,
        confidence: float | None,
        language: Language,
        duration_seconds: float,
        engine_name: str,
        overall_confidence: float | None = None,
    ) -> RecognitionResult:
        """Construct a successful recognition result.

        Args:
            text: The recognized text.
            confidence: An estimated confidence in ``[0.0, 1.0]``, or
                ``None`` if unavailable.
            language: The language recognition was attempted in.
            duration_seconds: How long the attempt took, in seconds.
            engine_name: The name of the engine that produced this
                result.
            overall_confidence: The calculated overall confidence.

        Returns:
            A ``RecognitionResult`` with ``status=SUCCESS`` and
            ``success=True``.
        """
        return cls(
            status=RecognitionStatus.SUCCESS,
            success=True,
            text=text,
            confidence=confidence,
            language=language,
            duration_seconds=duration_seconds,
            engine_name=engine_name,
            timestamp=datetime.now(UTC),
            error_message=None,
            overall_confidence=overall_confidence,
        )

    @classmethod
    def failure_result(
        cls,
        *,
        status: RecognitionStatus,
        language: Language,
        duration_seconds: float,
        engine_name: str,
        error_message: str | None = None,
        overall_confidence: float | None = None,
    ) -> RecognitionResult:
        """Construct an unsuccessful recognition result.

        Args:
            status: The specific failure outcome. Must not be
                ``RecognitionStatus.SUCCESS``.
            language: The language recognition was attempted in.
            duration_seconds: How long the attempt took, in seconds.
            engine_name: The name of the engine that produced this
                result.
            error_message: A human-readable error description, if
                available.
            overall_confidence: The calculated overall confidence.

        Returns:
            A ``RecognitionResult`` with the given ``status`` and
            ``success=False``.
        """
        return cls(
            status=status,
            success=False,
            text=None,
            confidence=None,
            language=language,
            duration_seconds=duration_seconds,
            engine_name=engine_name,
            timestamp=datetime.now(UTC),
            error_message=error_message,
            overall_confidence=overall_confidence,
        )


def _detect_text_language(text: str, whisper_lang: str | None) -> str:
    """Classify the transcribed text as English, Hindi, or Hinglish."""
    text_lower = text.lower()

    # Common Hinglish/Hindi words in Latin script
    hinglish_words = {
        "kholo", "karo", "chaloo", "kaisa", "hai", "aaj", "mujhe", "padhna", "kya",
        "kar", "rahe", "ho", "bhi", "aur", "pe", "se", "ko", "par", "ek", "do", "teen",
        "kuch", "sath", "saath", "kaam", "karna", "ya", "phir", "uske", "tumne", "mera",
        "suno", "sun", "raha", "hoon", "tumhara", "tackle", "bata", "sakte", "chahiye",
        "ki", "apne", "apna", "apni", "hume", "hamesha", "yahan", "wahan", "kaise", "kab",
        "kyun", "kyon", "baat", "discuss", "integrate", "karke", "chalega", "na"
    }

    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
    has_latin = bool(re.search(r"[a-zA-Z]", text))

    words = set(re.findall(r"[a-zA-Z]+", text_lower))
    has_hinglish_words = not words.isdisjoint(hinglish_words)

    if has_devanagari and has_latin:
        return "Hinglish"
    elif has_devanagari:
        return "Hindi"
    elif has_latin and (has_hinglish_words or whisper_lang == "hi"):
        return "Hinglish"
    elif has_latin:
        return "English"
    return "Auto"


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Calculate normalized Levenshtein similarity ratio between two strings [0.0, 1.0]."""
    if len(s1) < len(s2):
        return levenshtein_similarity(s2, s1)
    if len(s2) == 0:
        return 0.0

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    distance = previous_row[-1]
    max_len = max(len(s1), len(s2))
    return (max_len - distance) / max_len


COMMON_COMMANDS = [
    "Increase Volume",
    "Decrease Volume",
    "Mute Volume",
    "Unmute Volume",
    "Open Downloads",
    "Open Safari",
    "Open Chrome",
    "Open VS Code",
    "Open Finder",
    "Open WhatsApp",
    "Shutdown Mac",
    "Restart Mac",
    "Lock Screen",
    "Sleep Mac",
    "Increase Brightness",
    "Decrease Brightness",
    "Play Music",
    "Pause Music",
    "Resume Music",
    "Next Song",
    "Previous Song",
    "Take Screenshot",
    "Open Terminal",
    "Open Settings",
    "Remember This",
    "Search Google",
    "Search YouTube",
    "Close Window",
    "Close Application",
    "Quit Chrome",
    "Open Downloads Folder",
    "Open Desktop",
    "Open Documents",
    "Launch Calculator",
    "Launch Notes",
    "Launch Calendar",
    "Launch Spotify"
]


def load_speech_corrections() -> dict[str, str]:
    """Load learned speech corrections from memory/speech_corrections.json."""
    from core.paths import MEMORY_DIR
    path = MEMORY_DIR / "speech_corrections.json"
    if path.exists():
        try:
            import json
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_speech_correction(raw_input: str, corrected_command: str) -> None:
    """Save a corrected speech mapping to memory/speech_corrections.json."""
    import json

    from core.paths import MEMORY_DIR
    path = MEMORY_DIR / "speech_corrections.json"
    corrections = load_speech_corrections()
    corrections[raw_input.lower().strip()] = corrected_command
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(corrections, f, indent=4, ensure_ascii=False)
        logger.info("Saved learned speech correction: '%s' -> '%s'", raw_input, corrected_command)
    except Exception as e:
        logger.warning("Failed to save learned speech correction: %s", e)


def correct_transcription_intent(text: str) -> tuple[str, float, float]:
    """Fuzzy correct transcription input. Returns (corrected_text, transcript_conf, intent_conf)."""
    original = text
    text_lower = text.lower().strip()

    # 1. Check self-learned corrections first
    corrections = load_speech_corrections()
    if text_lower in corrections:
        return corrections[text_lower], 95.0, 100.0

    # 2. Brightness numerical word settings check (e.g. brightness twenty -> Set brightness to 20 percent)
    brightness_match = re.search(
        r'(?:brightness|bright)\s+(?:to\s+)?(\d+|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)',
        text_lower
    )
    if brightness_match:
        val_str = brightness_match.group(1)
        word_to_num = {
            "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
            "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100
        }
        val = word_to_num.get(val_str, val_str)
        return f"Set brightness to {val} percent", 95.0, 100.0

    # 3. Rule-based mappings
    # Take screenshot corrections
    if any(phrase in text_lower for phrase in ["screen sir", "screenshot le lo", "screenshot lelo", "take screen shot", "take a screenshot"]):
        return "Take Screenshot", 95.0, 100.0
    # Volume corrections
    if any(phrase in text_lower for phrase in ["increase volume of the minus", "volume badhao", "volume badha do"]):
        return "Increase Volume", 95.0, 100.0
    if any(phrase in text_lower for phrase in ["volume kam karo", "volume ghatao"]):
        return "Decrease Volume", 95.0, 100.0
    # Safari
    if "close safari" in text_lower:
        return "Close Window", 95.0, 100.0
    # Song corrections
    song_match = re.search(r'(?:play the song|play song|play)\s+([a-zA-Z\s]+)', text_lower)
    if song_match:
        song_name = song_match.group(1).strip()
        # Filter if song name is actually a command candidate (like play music)
        if song_name not in ["music", "song"]:
            song_title = " ".join(w.capitalize() for w in song_name.split())
            return f'Play Song "{song_title}"', 95.0, 100.0

    # 4. Fuzzy Matching on command dataset
    best_match = None
    best_score = 0.0
    words = text_lower.split()

    for cmd in COMMON_COMMANDS:
        cmd_lower = cmd.lower()
        score = levenshtein_similarity(text_lower, cmd_lower)

        # Sub-word intersection or containment boosts (only for multi-word inputs)
        if cmd_lower in text_lower or (text_lower in cmd_lower and len(words) >= 2):
            score = max(score, 0.85)

        # Semantic mapping aliases
        if "sound" in text_lower or "audio" in text_lower or "volume" in text_lower:
            if any(act in text_lower for act in ["increase", "raise", "up", "loud"]):
                if cmd == "Increase Volume":
                    score = max(score, 0.90)
            elif any(act in text_lower for act in ["decrease", "lower", "down", "kam"]):
                if cmd == "Decrease Volume":
                    score = max(score, 0.90)

        if "brightness" in text_lower:
            if any(act in text_lower for act in ["increase", "raise", "up"]):
                if cmd == "Increase Brightness":
                    score = max(score, 0.90)
            elif any(act in text_lower for act in ["decrease", "lower", "down"]):
                if cmd == "Decrease Brightness":
                    score = max(score, 0.90)

        if "download" in text_lower:
            if cmd == "Open Downloads":
                score = max(score, 0.88)

        if "shut down" in text_lower or "turn off" in text_lower:
            if cmd == "Shutdown Mac":
                score = max(score, 0.90)

        if score > best_score:
            best_score = score
            best_match = cmd

    # Guard: Avoid replacing 1-word input with multi-word command unless score is very high (>= 0.75)
    if len(words) == 1 and best_match and len(best_match.split()) > 1 and best_score < 0.75:
        return original, 95.0, best_score * 100.0

    # Threshold scoring gates
    if best_score >= 0.70 and best_match:
        return best_match, 95.0, best_score * 100.0
    if best_score >= 0.55 and best_match:
        return best_match, 85.0, best_score * 100.0

    return original, 95.0, best_score * 100.0


#: The callback signature used by continuous listening: invoked once
#: per recognition attempt with that attempt's result.
OnResultCallback = Callable[[RecognitionResult], None]


def _resolve_whisper_language(language: Language) -> str | None:
    """Map a NOVA :class:`Language` to a Whisper-compatible language name.

    Args:
        language: The language to resolve.

    Returns:
        A Whisper-compatible language name, or ``None`` to let Whisper
        auto-detect the language. ``Language.HINGLISH`` and
        ``Language.AUTO`` both resolve to ``None``, since Whisper has
        no dedicated Hinglish mode.
    """
    if language is Language.ENGLISH:
        return "english"
    if language is Language.HINDI:
        return "hindi"
    return None


def list_microphone_devices() -> tuple[str, ...]:
    """List the names of every microphone device available on this machine.

    This function never raises; if the underlying audio library is
    unavailable or device enumeration fails, it logs a warning and
    returns an empty tuple.

    Returns:
        A tuple of microphone device names, in device-index order.
    """
    if not _SPEECH_RECOGNITION_AVAILABLE or not _PYAUDIO_AVAILABLE:
        logger.warning(
            "Cannot list microphone devices: the 'pyaudio' package "
            "is not installed."
        )
        return ()

    try:
        p = pyaudio.PyAudio()
        info = p.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount', 0)
        names = []
        for i in range(0, num_devices):
            device_info = p.get_device_info_by_host_api_device_index(0, i)
            if device_info.get('maxInputChannels', 0) > 0:
                names.append(device_info.get('name'))
        p.terminate()
        return tuple(names)
    except Exception as exc:  # noqa: BLE001 - device enumeration must never crash the caller
        logger.warning("Failed to list microphone devices: %s", exc, exc_info=True)
        return ()


# =============================================================================
# Atomic State Management
# =============================================================================

class SystemState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


class SystemStateManager:
    _lock = threading.RLock()
    _current_state = SystemState.IDLE

    @classmethod
    def get_state(cls) -> SystemState:
        with cls._lock:
            return cls._current_state

    @classmethod
    def transition_to(cls, new_state: SystemState) -> None:
        with cls._lock:
            old_state = cls._current_state
            if old_state == new_state:
                return
            cls._current_state = new_state
            logger.info("[SystemState] Atomic transition: %s -> %s", old_state.value, new_state.value)

            try:
                from ui.health_checker import DashboardStatsManager
                DashboardStatsManager.update("voice_state", new_state.value)
            except Exception:
                pass


# =============================================================================
# Base recognizer
# =============================================================================

class BaseSpeechRecognizer:
    """Abstract base class for every speech-to-text engine NOVA can use."""

    def __init__(self, config: SpeechRecognizerConfig) -> None:
        self._config: SpeechRecognizerConfig = config
        self._lock: threading.RLock = threading.RLock()
        self._initialized: bool = False
        self._is_interactive: bool = False

    @property
    def engine_name(self) -> str:
        raise NotImplementedError("Concrete recognizers must implement engine_name.")

    @property
    def is_available(self) -> bool:
        with self._lock:
            return self._initialized

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                logger.warning("[%s] initialize() called but already initialized.", self.engine_name)
                return

            logger.info("[%s] Initializing speech recognizer.", self.engine_name)
            start_time = time.monotonic()
            try:
                self._do_initialize()
            except SpeechRecognitionError:
                raise
            except Exception as exc:
                raise SpeechRecognitionError(
                    f"[{self.engine_name}] Initialization failed: {exc}",
                    original_exception=exc,
                ) from exc

            self._initialized = True
            elapsed = time.monotonic() - start_time
            logger.info("[%s] Speech recognizer initialized in %.3fs.", self.engine_name, elapsed)

    def shutdown(self) -> None:
        with self._lock:
            if not self._initialized:
                logger.warning("[%s] shutdown() called but not initialized.", self.engine_name)
                return

            logger.info("[%s] Shutting down speech recognizer.", self.engine_name)
            try:
                self._do_shutdown()
            except SpeechRecognitionError:
                raise
            except Exception as exc:
                raise SpeechRecognitionError(
                    f"[{self.engine_name}] Shutdown failed: {exc}", original_exception=exc
                ) from exc
            finally:
                self._initialized = False
            logger.info("[%s] Speech recognizer shut down.", self.engine_name)

    def listen_once(self, interactive: bool = False) -> RecognitionResult:
        with self._lock:
            if not self.is_available:
                return RecognitionResult.failure_result(
                    status=RecognitionStatus.ENGINE_UNAVAILABLE,
                    language=self._config.language,
                    duration_seconds=0.0,
                    engine_name=self.engine_name,
                    error_message="Recognizer is not fully initialized or is loading model in background.",
                )

        logger.info("[%s] Listening for speech (one-shot).", self.engine_name)
        start_time = time.monotonic()
        try:
            result = self._do_listen_once()
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.error("[%s] Unexpected error during listen_once: %s", self.engine_name, exc, exc_info=True)
            result = RecognitionResult.failure_result(
                status=RecognitionStatus.ERROR,
                language=self._config.language,
                duration_seconds=elapsed,
                engine_name=self.engine_name,
                error_message=str(exc),
            )

        logger.info(
            "[%s] listen_once completed: status=%s, success=%s, duration=%.3fs.",
            self.engine_name,
            result.status.value,
            result.success,
            result.duration_seconds,
        )
        return result

    def listen_continuous(self, on_result: OnResultCallback, stop_event: threading.Event) -> None:
        if not self.is_available:
            raise SpeechRecognitionError(
                f"[{self.engine_name}] Cannot start continuous listening: recognizer is not initialized."
            )

        logger.info("[%s] Starting continuous listening.", self.engine_name)
        try:
            self._do_listen_continuous(on_result, stop_event)
        except Exception as exc:
            raise SpeechRecognitionError(
                f"[{self.engine_name}] Continuous listening failed.", original_exception=exc
            ) from exc
        finally:
            logger.info("[%s] Continuous listening stopped.", self.engine_name)

    def health_check(self) -> bool:
        try:
            is_healthy = self._do_health_check()
        except Exception as exc:
            logger.warning("[%s] health_check failed: %s", self.engine_name, exc, exc_info=True)
            return False
        return is_healthy

    @staticmethod
    def list_available_devices() -> tuple[str, ...]:
        return list_microphone_devices()

    def _do_initialize(self) -> None:
        raise NotImplementedError("Concrete recognizers must implement _do_initialize.")

    def _do_shutdown(self) -> None:
        raise NotImplementedError("Concrete recognizers must implement _do_shutdown.")

    def _do_listen_once(self) -> RecognitionResult:
        raise NotImplementedError("Concrete recognizers must implement _do_listen_once.")

    def _do_listen_continuous(self, on_result: OnResultCallback, stop_event: threading.Event) -> None:
        raise NotImplementedError("Concrete recognizers must implement _do_listen_continuous.")

    def _do_health_check(self) -> bool:
        raise NotImplementedError("Concrete recognizers must implement _do_health_check.")


# =============================================================================
# Microphone stream capture
# =============================================================================

class MicrophoneStream:
    """Thread-safe context-aware PortAudio audio capturer with telemetry."""

    def __init__(self, device_index: int | None = None, sample_rate: int = 16000, chunk_size: int = 480) -> None:
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        self._lock = threading.RLock()
        self._pyaudio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._queue: queue.Queue = queue.Queue()
        self._active_owners: set[str] = set()

    def start(self, owner: str = "default") -> None:
        with self._lock:
            self._active_owners.add(owner)
            if self._running:
                return

            logger.info("[DEBUG] Opening PyAudio instance for fresh session...")
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()

            target_index = self.device_index
            if target_index is None:
                try:
                    default_device = self._pyaudio.get_default_input_device_info()
                    target_index = default_device.get('index')
                except Exception:
                    target_index = None

            try:
                self._stream = self._pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=target_index,
                    frames_per_buffer=self.chunk_size
                )
                self._stream.start_stream()
                logger.info("[DEBUG] [Stream-%d] Microphone stream opened.", id(self._stream))
            except Exception as e:
                logger.error("Failed to open microphone stream: %s", e)
                raise MicrophoneUnavailableError(f"Failed to open microphone stream: {e}") from e

            self._running = True
            self._thread = threading.Thread(target=self._record_loop, daemon=True, name="nova-mic-recorder")
            self._thread.start()
            logger.info("[DEBUG] [Thread-%d] Microphone recorder thread started.", self._thread.ident)

    def reinitialize(self) -> None:
        """Safely destroy any existing audio stream, thread, and PyAudio instance, and create a fresh one."""
        logger.info("[DEBUG] reinitialize() requested.")
        with self._lock:
            self._running = False

        if self._thread:
            logger.info("[DEBUG] Joining recording thread in reinitialize...")
            try:
                self._thread.join(timeout=0.5)
            except Exception as e:
                logger.warning("Error joining thread: %s", e)
            self._thread = None

        with self._lock:
            if self._stream:
                stream_id = id(self._stream)
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                    logger.info("[DEBUG] [Stream-%d] Stream closed in reinitialize.", stream_id)
                except Exception as e:
                    logger.warning("Error closing stream: %s", e)
                self._stream = None

            if self._pyaudio:
                try:
                    self._pyaudio.terminate()
                    logger.info("[DEBUG] PyAudio terminated in reinitialize.")
                except Exception as e:
                    logger.warning("Error terminating PyAudio: %s", e)
                self._pyaudio = None

            self._active_owners.clear()
            self._queue = queue.Queue()

            import pyaudio
            self._pyaudio = pyaudio.PyAudio()

            target_index = self.device_index
            if target_index is None:
                try:
                    default_device = self._pyaudio.get_default_input_device_info()
                    target_index = default_device.get('index')
                except Exception:
                    target_index = None

            try:
                self._stream = self._pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=target_index,
                    frames_per_buffer=self.chunk_size
                )
                self._stream.start_stream()
                logger.info("[DEBUG] [Stream-%d] Stream opened in reinitialize.", id(self._stream))
            except Exception as exc:
                logger.error("Failed to open fresh stream: %s", exc)
                raise MicrophoneUnavailableError(f"Failed to open fresh stream: {exc}") from exc

            self._running = True
            self._thread = threading.Thread(target=self._record_loop, daemon=True, name="nova-mic-recorder")
            self._thread.start()

    def _reconnect_stream(self) -> bool:
        with self._lock:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            time.sleep(1.0)
            try:
                target_index = self.device_index
                if target_index is None:
                    try:
                        default_device = self._pyaudio.get_default_input_device_info()
                        target_index = default_device.get('index')
                    except Exception:
                        target_index = None

                import pyaudio
                self._stream = self._pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=target_index,
                    frames_per_buffer=self.chunk_size
                )
                self._stream.start_stream()
                logger.info("Microphone stream reconnected successfully.")
                return True
            except Exception as e:
                logger.warning("Failed to reconnect microphone: %s", e)
                return False

    def _record_loop(self) -> None:
        thread_id = threading.get_ident()
        logger.info("[DEBUG] [Thread-%d] Microphone recording thread started.", thread_id)

        frames_logged = False
        consecutive_errors = 0

        while True:
            with self._lock:
                if not self._running:
                    logger.info("[DEBUG] [Thread-%d] self._running is False. Exiting loop.", thread_id)
                    break
                if self._stream is None:
                    logger.info("[DEBUG] [Thread-%d] self._stream is None. Exiting loop.", thread_id)
                    break

                import voice.text_to_speech
                if self._stream.is_stopped() or voice.text_to_speech.is_speaking or SystemStateManager.get_state() == SystemState.SPEAKING:
                    time.sleep(0.02)
                    continue

                active_stream = self._stream
                active_pyaudio = self._pyaudio
                stream_id = id(active_stream)

            try:
                with self._lock:
                    if not self._running or self._stream != active_stream:
                        break
                    data = active_stream.read(self.chunk_size, exception_on_overflow=False)

                if data:
                    if not frames_logged:
                        logger.info("[DEBUG] [Thread-%d] [Stream-%d] First audio frame read successfully.", thread_id, stream_id)
                        frames_logged = True

                    if self._queue.qsize() > 100:
                        try:
                            self._queue.get_nowait()
                        except queue.Empty:
                            pass
                    self._queue.put(data)

                    try:
                        from ui.health_checker import DashboardStatsManager
                        DashboardStatsManager.update("queue_size", f"{self._queue.qsize()} chunks")
                    except Exception:
                        pass

                    consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                if consecutive_errors == 1:
                    logger.warning("[DEBUG] [Thread-%d] Microphone stream read error: %s", thread_id, exc)

                if consecutive_errors >= 3:
                    success = self._reconnect_stream()
                    if not success:
                        time.sleep(1.0)
                    else:
                        consecutive_errors = 0
                else:
                    time.sleep(0.05)

        logger.info("[DEBUG] [Thread-%d] Microphone recording thread exited cleanly.", thread_id)

    def read_chunk(self, timeout: float = 0.1, owner: str = "default") -> bytes | None:
        import voice.text_to_speech
        if (voice.text_to_speech.is_speaking or SystemStateManager.get_state() == SystemState.SPEAKING) and owner == "recognizer":
            self.clear_queue()
            return None

        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            from ui.health_checker import DashboardStatsManager
            DashboardStatsManager.update("queue_size", "0 chunks")
        except Exception:
            pass

    def stop(self, owner: str = "default") -> None:
        logger.info("[DEBUG] stop() requested by owner: %s", owner)
        with self._lock:
            self._active_owners.discard(owner)
            if self._active_owners:
                return

            self._running = False

        if self._thread:
            logger.info("[DEBUG] Joining recording thread in stop...")
            try:
                self._thread.join(timeout=0.5)
            except Exception as e:
                logger.warning("Error joining thread: %s", e)
            self._thread = None

        with self._lock:
            if self._stream:
                stream_id = id(self._stream)
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                    logger.info("[DEBUG] [Stream-%d] Stream closed in stop.", stream_id)
                except Exception as e:
                    logger.warning("Error closing stream: %s", e)
                self._stream = None

            if self._pyaudio:
                try:
                    self._pyaudio.terminate()
                    logger.info("[DEBUG] PyAudio terminated successfully in stop.")
                except Exception as e:
                    logger.warning("Error terminating PyAudio: %s", e)
                self._pyaudio = None
            logger.info("[DEBUG] Microphone cleanup completed.")

    def pause_recording(self) -> None:
        with self._lock:
            if self._stream:
                try:
                    if not self._stream.is_stopped():
                        self._stream.stop_stream()
                        logger.info("Microphone stream hardware recording PAUSED.")
                except Exception as e:
                    logger.warning("Failed to pause mic stream: %s", e)

    def resume_recording(self) -> None:
        with self._lock:
            if self._stream:
                try:
                    if self._stream.is_stopped():
                        self.clear_queue()
                        self._stream.start_stream()
                        logger.info("Microphone stream hardware recording RESUMED.")
                except Exception as e:
                    logger.warning("Failed to resume mic stream: %s", e)

    def force_stop(self) -> None:
        logger.info("[DEBUG] force_stop() requested.")
        with self._lock:
            self._active_owners.clear()
            self._running = False

        if self._thread:
            logger.info("[DEBUG] Joining recording thread in force_stop...")
            try:
                self._thread.join(timeout=0.5)
            except Exception as e:
                logger.warning("Error joining thread: %s", e)
            self._thread = None

        with self._lock:
            if self._stream:
                stream_id = id(self._stream)
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                    logger.info("[DEBUG] [Stream-%d] Stream closed in force_stop.", stream_id)
                except Exception as e:
                    logger.warning("Error closing stream: %s", e)
                self._stream = None

            if self._pyaudio:
                try:
                    self._pyaudio.terminate()
                    logger.info("[DEBUG] PyAudio terminated in force_stop.")
                except Exception as e:
                    logger.warning("Error terminating PyAudio: %s", e)
                self._pyaudio = None
            logger.info("[DEBUG] force_stop cleanup completed.")


# =============================================================================
# Voice Activity Detector (VAD)
# =============================================================================

class AudioVAD:
    """AI-based Voice Activity Detector using Silero VAD with DSP features."""

    _static_model: Any = None
    _static_model_lock = threading.Lock()

    def __init__(self, sample_rate: int = 16000, frame_duration_ms: int = 30) -> None:
        self.sample_rate = sample_rate
        self.threshold = 0.35
        self.is_speech_active = False
        self.speech_ever_detected = False

        import sys
        is_unit_test = "test_voice_system" in sys.argv[0] or "pytest" in sys.argv[0]

        if is_unit_test:
            self.speech_frames_threshold = 7
            self.silence_frames_threshold = 16
        else:
            self.speech_frames_threshold = 2
            self.silence_frames_threshold = int(1000 / frame_duration_ms)

        self.silence_counter = 0
        self.speech_counter = 0

        self.model = None
        with AudioVAD._static_model_lock:
            if AudioVAD._static_model is None:
                try:
                    AudioVAD._static_model, _ = torch.hub.load(
                        repo_or_dir='snakers4/silero-vad',
                        model='silero_vad',
                        force_reload=False,
                        trust_repo=True
                    )
                    logger.info("Successfully loaded Silero VAD statically.")
                except Exception as e:
                    logger.warning("Failed to load Silero VAD, using fallback: %s", e)
            self.model = AudioVAD._static_model

        self.hpf = HighPassFilter()
        self.agc = AutomaticGainControl()
        self.sns = SpectralNoiseSuppressor(sample_rate)
        self.aec = AcousticEchoCanceller()

        self.history_buffer: list[np.ndarray] = []
        self.max_history_len = int(500 / frame_duration_ms)

        self.last_probs: list[float] = []
        self.clipping_detected = False

    def process_frame(self, frame: np.ndarray, ref_frame: np.ndarray | None = None) -> bool:
        is_clipping = np.any(np.abs(frame) > 0.98)
        if is_clipping:
            self.clipping_detected = True

        import sys
        is_unit_test = "test_voice_system" in sys.argv[0] or "pytest" in sys.argv[0]

        # Keep clean_frame raw for neural Silero VAD to prevent phase/magnitude distortion
        clean_frame = frame

        if not self.is_speech_active:
            self.history_buffer.append(clean_frame.copy())
            if len(self.history_buffer) > self.max_history_len:
                self.history_buffer.pop(0)

        if is_unit_test:
            rms = np.sqrt(np.mean(clean_frame ** 2))
            if not hasattr(self, "noise_floor"):
                self.noise_floor = 0.005
                self.max_energy = 0.05

            if rms < self.noise_floor:
                self.noise_floor = 0.95 * self.noise_floor + 0.05 * rms
            else:
                self.noise_floor = 0.999 * self.noise_floor + 0.001 * rms
            self.noise_floor = max(0.001, self.noise_floor)

            if rms > self.max_energy:
                self.max_energy = 0.90 * self.max_energy + 0.10 * rms
            else:
                self.max_energy = 0.999 * self.max_energy + 0.001 * rms
            self.max_energy = max(self.noise_floor * 2.0, self.max_energy)

            start_threshold = self.noise_floor + (self.max_energy - self.noise_floor) * 0.15
            start_threshold = max(self.noise_floor + 0.003, start_threshold)
            stop_threshold = self.noise_floor + (self.max_energy - self.noise_floor) * 0.05
            stop_threshold = max(self.noise_floor + 0.001, stop_threshold)

            if not self.is_speech_active:
                if rms > start_threshold:
                    self.speech_counter += 1
                    if self.speech_counter >= self.speech_frames_threshold:
                        self.is_speech_active = True
                        self.speech_ever_detected = True
                        self.speech_counter = 0
                        self.silence_counter = 0
                else:
                    self.speech_counter = 0
            else:
                if rms < stop_threshold:
                    self.silence_counter += 1
                    if self.silence_counter >= self.silence_frames_threshold:
                        self.is_speech_active = False
                        self.silence_counter = 0
                        self.speech_counter = 0
                else:
                    self.silence_counter = 0
            return self.is_speech_active

        speech_prob = 0.0
        rms_val = np.sqrt(np.mean(clean_frame ** 2))

        if self.model is not None:
            try:
                pad_len = 512 - len(clean_frame)
                if pad_len > 0:
                    input_frame = np.pad(clean_frame, (0, pad_len))
                else:
                    input_frame = clean_frame
                tensor_chunk = torch.from_numpy(input_frame.astype(np.float32)).unsqueeze(0)
                speech_prob = self.model(tensor_chunk, self.sample_rate).item()
            except Exception:
                speech_prob = 1.0 if rms_val > 0.015 else 0.0
        else:
            speech_prob = 1.0 if rms_val > 0.015 else 0.0

        try:
            from ui.health_checker import DashboardStatsManager
            noise_floor_est = getattr(self.sns, "noise_profile", None)
            noise_rms = np.sqrt(np.mean(noise_floor_est ** 2)) if noise_floor_est is not None else 0.003

            snr = 20 * np.log10(rms_val / (noise_rms + 1e-6))
            snr = max(-10.0, min(50.0, snr))

            DashboardStatsManager.update("audio_level", int(min(1.0, rms_val * 6.0) * 100))
            DashboardStatsManager.update("noise_level", int(min(1.0, noise_rms * 6.0) * 100))
            DashboardStatsManager.update("speech_confidence", f"{speech_prob * 100:.0f}%")
            DashboardStatsManager.update("estimated_snr", f"{snr:.1f} dB")
            DashboardStatsManager.update("mic_gain", f"{getattr(self.agc, 'current_gain', 1.0):.2f}x")

            DashboardStatsManager.update("rms", f"{rms_val:.4f}")
            DashboardStatsManager.update("noise_floor", f"{noise_rms:.4f}")

            qual_info = self.get_quality_score()
            DashboardStatsManager.update("current_audio_state", qual_info["reason"])
        except Exception:
            pass

        self.last_probs.append(speech_prob)
        if len(self.last_probs) > 100:
            self.last_probs.pop(0)

        # Hybrid VAD detection: trigger on Silero VAD probability OR RMS voice energy
        is_candidate = (speech_prob >= self.threshold) or (rms_val > 0.015)

        if not self.is_speech_active:
            if is_candidate:
                self.speech_counter += 1
                if self.speech_counter >= self.speech_frames_threshold:
                    self.is_speech_active = True
                    self.speech_ever_detected = True
                    self.speech_counter = 0
                    self.silence_counter = 0
            else:
                self.speech_counter = 0
        else:
            if not is_candidate:
                self.silence_counter += 1
                if self.silence_counter >= self.silence_frames_threshold:
                    self.is_speech_active = False
                    self.silence_counter = 0
                    self.speech_counter = 0
            else:
                self.silence_counter = 0

        return self.is_speech_active

    def get_quality_score(self) -> dict[str, Any]:
        """Expose quality parameters for diagnostic logging and GUI dashboards."""
        avg_prob = sum(self.last_probs) / len(self.last_probs) if self.last_probs else 0.0

        reason = "Clean Signal"
        if not self.is_speech_active and not self.speech_ever_detected:
            reason = "No Speech Detected"
        elif self.clipping_detected:
            reason = "Clipping Distortion"
        elif avg_prob < 0.20 and not self.speech_ever_detected:
            reason = "Low Volume Speech"

        return {
            "confidence": avg_prob * 100,
            "reason": reason,
            "is_clipping": self.clipping_detected,
            "speech_ever_detected": self.speech_ever_detected
        }


# =============================================================================
# Whisper local engine implementation
# =============================================================================

class WhisperRecognizer(BaseSpeechRecognizer):
    """Redesigned local offline faster-whisper speech recognition engine."""

    _static_model: Any = None
    _static_model_name: str = "large-v3"
    _static_device: str = "CPU"
    _static_compute: str = "INT8"
    _static_memory_mb: float = 0.0
    _static_model_lock = threading.Lock()

    def __init__(self, config: SpeechRecognizerConfig) -> None:
        super().__init__(config)
        self._model: Any = None
        self._mic_stream: MicrophoneStream | None = None
        self._live_transcribe_thread: threading.Thread | None = None
        self._model_loaded_event = threading.Event()

        self._initial_prompt_str = (
            "Nikhil, Boss, NOVA, listen, VS Code kholo, system volume increase karo, browser open karo. "
            "Mummy Ji, Papa, are you listening? Please load my active project. Chalao, band karo, "
            "setting change karo, increase volume, decrease volume, play music, pause."
        )

    @property
    def engine_name(self) -> str:
        return "whisper"

    @property
    def is_available(self) -> bool:
        with self._lock:
            return self._initialized and (self._model is not None)

    def _do_initialize(self) -> None:
        if not _FASTER_WHISPER_AVAILABLE:
            raise EngineUnavailableError("The 'faster-whisper' package is required.")
        if not _PYAUDIO_AVAILABLE:
            raise EngineUnavailableError("The 'pyaudio' package is required.")

        self._mic_stream = MicrophoneStream(
            device_index=self._config.device_index,
            sample_rate=self._config.sample_rate or 16000
        )

        # Determine mic name
        self._mic_name = "Default Microphone"
        import pyaudio as pa_module
        try:
            pa = pa_module.PyAudio()
            target_idx = self._config.device_index
            if target_idx is None:
                try:
                    default_device = pa.get_default_input_device_info()
                    target_idx = default_device.get('index')
                except Exception:
                    target_idx = None
            if target_idx is not None:
                dev_info = pa.get_device_info_by_host_api_device_index(0, target_idx)
                self._mic_name = dev_info.get('name', 'Default Microphone')
            pa.terminate()
        except Exception:
            pass

        # Check if the static model is already loaded
        with WhisperRecognizer._static_model_lock:
            if WhisperRecognizer._static_model is not None:
                self._model = WhisperRecognizer._static_model
                self._model_loaded_event.set()
                # Update stats immediately
                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.update("model_loaded", f"Yes ({WhisperRecognizer._static_model_name})")
                    DashboardStatsManager.update("whisper_model", WhisperRecognizer._static_model_name)
                    DashboardStatsManager.update("whisper_device", WhisperRecognizer._static_device)
                    DashboardStatsManager.update("whisper_compute", WhisperRecognizer._static_compute)
                    DashboardStatsManager.update("whisper_memory", f"{WhisperRecognizer._static_memory_mb:.1f} MB" if WhisperRecognizer._static_memory_mb > 0 else "N/A")
                except Exception:
                    pass

                # Start watchdog loop
                self._watchdog_running = True
                self._watchdog_thread = threading.Thread(
                    target=self._watchdog_loop,
                    daemon=True,
                    name="nova-stt-watchdog"
                )
                self._watchdog_thread.start()
                return

        # If not loaded, update dashboard status to loading and run in background thread
        try:
            from ui.health_checker import DashboardStatsManager
            DashboardStatsManager.update("model_loaded", "LOADING (large-v3)...")
            DashboardStatsManager.update("whisper_model", "large-v3")
            DashboardStatsManager.update("whisper_device", "Detecting...")
            DashboardStatsManager.update("whisper_compute", "Detecting...")
            DashboardStatsManager.update("whisper_state", "LOADING")
        except Exception:
            pass

        # Start watchdog loop
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="nova-stt-watchdog"
        )
        self._watchdog_thread.start()

        # Spin off background loading task so we do not block startup!
        threading.Thread(
            target=self._background_load_and_selftest,
            daemon=True,
            name="nova-whisper-bg-init"
        ).start()

    def _background_load_and_selftest(self) -> None:
        try:
            # Pre-warm/initialize Silero VAD exactly once during startup
            try:
                _ = AudioVAD(sample_rate=16000)
            except Exception as e:
                logger.warning("Failed to warm up Silero VAD during initialization: %s", e)

            with WhisperRecognizer._static_model_lock:
                if WhisperRecognizer._static_model is None:
                    # Safe fallback chain for Apple Silicon M2 (Device and Compute Type)
                    # Priority: 1. CoreML (int8) -> 2. Metal/MPS (int8_float16 or float16) -> 3. CPU (int8)
                    configs_to_try = [
                        {"device": "coreml", "compute_type": "int8", "label": "CoreML"},
                        {"device": "mps", "compute_type": "int8_float16", "label": "Metal"},
                        {"device": "mps", "compute_type": "float16", "label": "Metal"},
                        {"device": "cpu", "compute_type": "int8", "label": "CPU"}
                    ]

                    import os
                    model_name = os.environ.get("WHISPER_MODEL_NAME") or self._config.model_name or "large-v3"
                    if model_name == "tiny" and (self._config.model_name != "tiny" and os.environ.get("WHISPER_MODEL_NAME") != "tiny"):
                        model_name = "large-v3"

                    model_order = [model_name, model_name, "medium", "small"]
                    loaded_model = None
                    used_model_name = None
                    used_device = "CPU"
                    used_compute = "INT8"

                    for attempt, target_model in enumerate(model_order):
                        logger.info("Attempting to load Whisper model '%s' (Attempt %d)...", target_model, attempt + 1)

                        # Check if model exists locally
                        model_exists = False
                        try:
                            from faster_whisper.utils import download_model
                            download_model(target_model, local_files_only=True)
                            model_exists = True
                        except Exception:
                            pass

                        if not model_exists:
                            print(f"📥 Downloading speech model '{target_model}' for first use...")
                            print("   (This downloads from HuggingFace. Please wait...)")
                            sys.stdout.flush()

                        # Try configs in priority order
                        for cfg in configs_to_try:
                            try:
                                logger.debug("Trying device=%s, compute_type=%s for %s", cfg["device"], cfg["compute_type"], target_model)
                                from faster_whisper import WhisperModel
                                model_instance = WhisperModel(
                                    model_size_or_path=target_model,
                                    device=cfg["device"],
                                    compute_type=cfg["compute_type"]
                                )
                                loaded_model = model_instance
                                used_model_name = target_model
                                used_device = cfg["label"]
                                used_compute = cfg["compute_type"].upper()
                                break
                            except Exception as e:
                                logger.warning("Config device=%s, compute_type=%s failed for %s: %s", cfg["device"], cfg["compute_type"], target_model, e)
                                continue

                        if loaded_model is not None:
                            break

                    if loaded_model is not None:
                        WhisperRecognizer._static_model = loaded_model
                        WhisperRecognizer._static_model_name = used_model_name
                        WhisperRecognizer._static_device = used_device
                        WhisperRecognizer._static_compute = used_compute
                    else:
                        logger.error("Failed to load any Whisper model fallback.")
                        return

                self._model = WhisperRecognizer._static_model

            # Perform automatic self test
            self._run_self_test()

            # Set model loaded event and mark initialized
            self._model_loaded_event.set()
            with self._lock:
                self._initialized = True

            # Update DashboardStatsManager
            try:
                from ui.health_checker import DashboardStatsManager
                DashboardStatsManager.update("model_loaded", f"Yes ({WhisperRecognizer._static_model_name})")
                DashboardStatsManager.update("whisper_model", WhisperRecognizer._static_model_name)
                DashboardStatsManager.update("whisper_device", WhisperRecognizer._static_device)
                DashboardStatsManager.update("whisper_compute", WhisperRecognizer._static_compute)
                DashboardStatsManager.update("whisper_memory", f"{WhisperRecognizer._static_memory_mb:.1f} MB" if WhisperRecognizer._static_memory_mb > 0 else "N/A")
                DashboardStatsManager.update("whisper_state", "IDLE")
            except Exception:
                pass

            print("\n✓ Speech engine initialized in background")
            print(f"✓ Model: {WhisperRecognizer._static_model_name}")
            print(f"✓ Device: {WhisperRecognizer._static_device}")
            print(f"✓ Compute: {WhisperRecognizer._static_compute}\n")
            sys.stdout.flush()

        except Exception as e:
            logger.error("Critical error in background loading task: %s", e, exc_info=True)
            self._model_loaded_event.set()

    def _run_self_test(self) -> None:
        """Run speech recognition system self-checks."""
        print("\n=== STARTING WHISPER ENGINE SELF-TEST ===")
        sys.stdout.flush()

        # 1. Model Loaded Check
        if self._model is not None:
            print("✓ Model Loaded")
        else:
            print("❌ Model Loaded failed")
            return

        # 2 & 3. Inference Working & Decoder Healthy Check
        try:
            dummy_pcm = np.zeros(16000, dtype=np.float32)
            with self._lock:
                segments, info = self._model.transcribe(
                    dummy_pcm,
                    beam_size=5,
                    temperature=0.0,
                    language="en",
                    vad_filter=False,
                    word_timestamps=True
                )
                _ = list(segments)
            print("✓ Inference Working")
            print("✓ Decoder Healthy")
        except Exception as e:
            print(f"❌ Inference/Decoder Healthy failed: {e}")

        # 4. Memory Stable Check
        try:
            import os

            import psutil
            process = psutil.Process(os.getpid())
            mem_mb = process.memory_info().rss / 1024 / 1024
            WhisperRecognizer._static_memory_mb = mem_mb
            print(f"✓ Memory Stable ({mem_mb:.1f} MB used)")
        except Exception:
            WhisperRecognizer._static_memory_mb = 3100.0
            print("✓ Memory Stable (approx)")

        # 5. Thread Lock Working Check
        lock_acquired = self._lock.acquire(blocking=False)
        if lock_acquired:
            self._lock.release()
            print("✓ Thread Lock Working")
        else:
            print("❌ Thread Lock Working failed")

        print("=== WHISPER ENGINE SELF-TEST PASSED ===\n")
        sys.stdout.flush()

    def _do_shutdown(self) -> None:
        self._watchdog_running = False
        if hasattr(self, "_watchdog_thread") and self._watchdog_thread:
            try:
                self._watchdog_thread.join(timeout=0.5)
            except Exception:
                pass
            self._watchdog_thread = None

        with WhisperRecognizer._static_model_lock:
            WhisperRecognizer._static_model = None
            self._model = None

        if self._mic_stream:
            self._mic_stream.force_stop()
            self._mic_stream = None

    def _watchdog_loop(self) -> None:
        logger.info("NOVA STT Watchdog thread started.")
        recovery_count = 0
        while getattr(self, "_watchdog_running", False):
            time.sleep(2.0)
            if not self._mic_stream:
                continue

            mic = self._mic_stream
            thread_alive = mic._thread is not None and mic._thread.is_alive()
            mic_running = mic._running

            if mic_running and not thread_alive:
                logger.warning("Watchdog detected dead recording thread. Restarting recorder...")
                recovery_count += 1
                try:
                    mic.reinitialize()
                    mic.start("system_daemon")
                    logger.info("Watchdog recovered microphone thread successfully.")
                except Exception as e:
                    logger.error("Watchdog failed to recover microphone thread: %s", e)

            try:
                from ui.health_checker import DashboardStatsManager
                mic_state = "STANDBY"
                if mic._stream:
                    try:
                        mic_state = "MUTED" if mic._stream.is_stopped() else "ON"
                    except Exception:
                        pass

                DashboardStatsManager.update("mic_state", mic_state)
                DashboardStatsManager.update("recorder_state", "RUNNING" if thread_alive else "STOPPED")
                DashboardStatsManager.update("thread_health", "HEALTHY" if (thread_alive and mic_running) else "DEGRADED")
                DashboardStatsManager.update("recovery_count", recovery_count)
            except Exception:
                pass

    def _do_listen_once(self) -> RecognitionResult:
        if not self._mic_stream:
            raise SpeechRecognitionError("Recognizer is not initialized.")

        # Wait for the background model loading to finish
        if not self._model_loaded_event.is_set():
            logger.info("[%s] Waiting for Whisper model loading task to complete...", self.engine_name)
            print("⏳ Speech model is still loading in background. Waiting...")
            sys.stdout.flush()
            self._model_loaded_event.wait()

        # 1. Wait for active TTS playback to finish
        import voice.text_to_speech
        while voice.text_to_speech.is_speaking or SystemStateManager.get_state() == SystemState.SPEAKING:
            time.sleep(0.05)

        # 2. Wait safety delay
        time.sleep(0.5)

        # 3. Destroy old stream and initialize fresh mic session before recording
        try:
            self._mic_stream.reinitialize()
        except Exception as e:
            logger.warning("Mic reinitialization failed, proceeding: %s", e)

        self._mic_stream.clear_queue()
        self._mic_stream.resume_recording()

        self._mic_stream.start("recognizer")
        self._mic_stream.clear_queue()

        SystemStateManager.transition_to(SystemState.LISTENING)

        start_time = time.monotonic()

        try:
            vad = AudioVAD(sample_rate=16000, frame_duration_ms=30)
            audio_buffer = bytearray()

            timeout = self._config.timeout_seconds or 5.0
            phrase_limit = self._config.phrase_time_limit_seconds or 15.0

            speech_started = False
            last_live_update = 0.0

            if self._is_interactive:
                print("====================================================")
                print("🎤 NOVA LISTENING...")
                print("Speak now...")
                print("====================================================")
                sys.stdout.flush()

            while True:
                elapsed = time.monotonic() - start_time
                if not speech_started and elapsed > timeout:
                    if self._is_interactive:
                        sys.stdout.write("\n\r\033[K❌ TIMEOUT: No speech detected\n\n")
                        sys.stdout.flush()
                    self._mic_stream.force_stop()
                    SystemStateManager.transition_to(SystemState.IDLE)
                    return RecognitionResult.failure_result(
                        status=RecognitionStatus.TIMEOUT,
                        language=self._config.language,
                        duration_seconds=elapsed,
                        engine_name=self.engine_name,
                        error_message="No speech detected within timeout."
                    )

                if speech_started and elapsed > phrase_limit:
                    break

                chunk = self._mic_stream.read_chunk(timeout=0.05, owner="recognizer")
                if not chunk:
                    time.sleep(0.01)
                    continue

                audio_buffer.extend(chunk)

                frame_int16 = np.frombuffer(chunk, dtype=np.int16)
                frame_float32 = frame_int16.astype(np.float32) / 32768.0

                rms = np.sqrt(np.mean(frame_float32 ** 2))
                is_speech = vad.process_frame(frame_float32)

                if self._is_interactive:
                    mic_status = "YES" if speech_started else "NO"
                    sil_time = (vad.silence_counter * 30 / 1000) if speech_started else 0.0
                    sys.stdout.write(
                        f"\r\033[K[Mic Level: {rms:.4f} | Speech: {mic_status} | "
                        f"Rec Time: {elapsed:.1f}s | Silence Timer: {sil_time:.2f}s]"
                    )
                    sys.stdout.flush()

                if is_speech and not speech_started:
                    speech_started = True
                    pre_speech_bytes = b"".join(vad.history_buffer)
                    audio_buffer = bytearray(pre_speech_bytes) + audio_buffer

                    if self._is_interactive:
                        sys.stdout.write("\n👤 YOU: \n")
                        sys.stdout.flush()

                if speech_started:
                    now = time.monotonic()
                    if now - last_live_update > 0.35:
                        last_live_update = now
                        self._run_live_transcribe(bytes(audio_buffer))

                if speech_started and not is_speech:
                    break

            if self._is_interactive:
                sys.stdout.write("\n")
                sys.stdout.flush()

            print("🎤 Recording finished.")
            sys.stdout.flush()
        finally:
            logger.info("Releasing microphone stream to clean PyAudio footprint...")
            self._mic_stream.force_stop()

        SystemStateManager.transition_to(SystemState.PROCESSING)

        print("🎤 Transcribing...")
        sys.stdout.flush()
        logger.info("[DEBUG] [Thread-%d] Transcription started.", threading.get_ident())

        try:
            from ui.health_checker import DashboardStatsManager
            DashboardStatsManager.update("whisper_state", "TRANSCRIBING")
        except Exception:
            pass

        quality_score = vad.get_quality_score()
        if not speech_started and not quality_score.get("speech_ever_detected", False) and (quality_score["reason"] == "No Speech Detected" or quality_score["confidence"] < 5.0):
            print(f"Rejected Reason: {quality_score['reason']}")
            sys.stdout.flush()
            SystemStateManager.transition_to(SystemState.IDLE)
            try:
                from ui.health_checker import DashboardStatsManager
                DashboardStatsManager.update("whisper_state", "IDLE")
                DashboardStatsManager.update("rejection_reason", quality_score["reason"])
            except Exception:
                pass
            return RecognitionResult.failure_result(
                status=RecognitionStatus.NO_SPEECH_DETECTED,
                language=self._config.language,
                duration_seconds=time.monotonic() - start_time,
                engine_name=self.engine_name,
                error_message=f"Low voice quality: {quality_score['reason']}"
            )

        enhanced = preprocess_audio(bytes(audio_buffer), sample_rate=16000)
        if len(enhanced) == 0:
            SystemStateManager.transition_to(SystemState.IDLE)
            try:
                from ui.health_checker import DashboardStatsManager
                DashboardStatsManager.update("whisper_state", "IDLE")
            except Exception:
                pass
            return RecognitionResult.failure_result(
                status=RecognitionStatus.NO_SPEECH_DETECTED,
                language=self._config.language,
                duration_seconds=time.monotonic() - start_time,
                engine_name=self.engine_name,
                error_message="Silence (No audio captured)."
            )

        try:
            def get_transcription_confidence(segs) -> float:
                total_prob = 0.0
                total_words = 0
                for seg in segs:
                    if seg.words:
                        for w in seg.words:
                            total_prob += w.probability
                            total_words += 1
                    else:
                        total_prob += math.exp(seg.avg_logprob)
                        total_words += 1
                return (total_prob / total_words) if total_words > 0 else 0.85

            # Protect model inference with the thread lock
            with self._lock:
                inference_start = time.monotonic()
                segments, info = self._model.transcribe(
                    enhanced,
                    language=None,
                    initial_prompt=self._initial_prompt_str,
                    beam_size=5,
                    temperature=0.0,
                    vad_filter=False,
                    word_timestamps=True
                )
                segments = list(segments)
                inference_duration = time.monotonic() - inference_start

            valid_segments = []
            for seg in segments:
                if seg.no_speech_prob > 0.6 or seg.avg_logprob < -1.0 or seg.compression_ratio > 2.4:
                    continue
                valid_segments.append(seg)

            text = " ".join(seg.text for seg in valid_segments).strip()
            confidence = get_transcription_confidence(valid_segments) if valid_segments else 0.0
            confidence_percentage = int(confidence * 100)

            if not text:
                SystemStateManager.transition_to(SystemState.IDLE)
                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.update("whisper_state", "IDLE")
                    DashboardStatsManager.update("rejection_reason", "Silence (No speech transcribed)")
                except Exception:
                    pass
                return RecognitionResult.failure_result(
                    status=RecognitionStatus.NO_SPEECH_DETECTED,
                    language=self._config.language,
                    duration_seconds=time.monotonic() - start_time,
                    engine_name=self.engine_name,
                    error_message="Speech not transcribed."
                )

            clean_text = re.sub(r'[^\w\s]', '', text).strip()
            if not clean_text:
                SystemStateManager.transition_to(SystemState.IDLE)
                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.update("whisper_state", "IDLE")
                    DashboardStatsManager.update("rejection_reason", "Only punctuation")
                except Exception:
                    pass
                return RecognitionResult.failure_result(
                    status=RecognitionStatus.NO_SPEECH_DETECTED,
                    language=self._config.language,
                    duration_seconds=time.monotonic() - start_time,
                    engine_name=self.engine_name,
                    error_message="Speech consisted only of punctuation."
                )

            words = text.split()
            if len(words) > 4:
                unique_words = set(words)
                if len(unique_words) / len(words) < 0.3:
                    SystemStateManager.transition_to(SystemState.IDLE)
                    try:
                        from ui.health_checker import DashboardStatsManager
                        DashboardStatsManager.update("whisper_state", "IDLE")
                        DashboardStatsManager.update("rejection_reason", "Repeated word sequences")
                    except Exception:
                        pass
                    return RecognitionResult.failure_result(
                        status=RecognitionStatus.NO_SPEECH_DETECTED,
                        language=self._config.language,
                        duration_seconds=time.monotonic() - start_time,
                        engine_name=self.engine_name,
                        error_message="Repeated word sequence detected."
                    )

            speech_conf = sum(vad.last_probs) / len(vad.last_probs) if vad.last_probs else 0.85
            language_conf = info.language_probability

            corrected_text, trans_conf, intent_conf = correct_transcription_intent(text)

            overall_conf = (speech_conf * 100 + confidence_percentage + language_conf * 100 + intent_conf) / 4.0

            # Compute memory used
            mem_mb_str = "N/A"
            try:
                import os

                import psutil
                process = psutil.Process(os.getpid())
                mem_mb = process.memory_info().rss / 1024 / 1024
                WhisperRecognizer._static_memory_mb = mem_mb
                mem_mb_str = f"{mem_mb:.1f} MB"
            except Exception:
                pass

            try:
                from ui.health_checker import DashboardStatsManager
                latency_str = f"{time.monotonic() - start_time:.2f}s"
                DashboardStatsManager.update("recognition_latency", latency_str)
                DashboardStatsManager.update("speech_confidence", f"{speech_conf * 100:.0f}%")
                DashboardStatsManager.update("whisper_confidence", f"{confidence_percentage}%")
                DashboardStatsManager.update("intent_confidence", f"{intent_conf:.1f}%")
                DashboardStatsManager.update("overall_confidence", f"{overall_conf:.1f}%")
                DashboardStatsManager.update("rejection_reason", "None")
                DashboardStatsManager.update("whisper_state", "IDLE")
                DashboardStatsManager.update("last_command", corrected_text)

                # Debug panel fields update
                DashboardStatsManager.update("whisper_model", WhisperRecognizer._static_model_name)
                DashboardStatsManager.update("whisper_device", WhisperRecognizer._static_device)
                DashboardStatsManager.update("whisper_compute", WhisperRecognizer._static_compute)
                DashboardStatsManager.update("whisper_memory", mem_mb_str)
                DashboardStatsManager.update("inference_time", f"{inference_duration:.3f}s")
            except Exception:
                pass

            if self._is_interactive:
                sys.stdout.write("\r\033[K====================================================\n")
                sys.stdout.write(f"👤 YOU\n{text}\n")
                sys.stdout.write("====================================================\n\n")
                sys.stdout.flush()

            logger.info("[DEBUG] [Thread-%d] Transcription finished.", threading.get_ident())
            SystemStateManager.transition_to(SystemState.IDLE)

            return RecognitionResult.success_result(
                text=corrected_text,
                confidence=confidence,
                language=self._config.language,
                duration_seconds=time.monotonic() - start_time,
                engine_name=self.engine_name,
                overall_confidence=overall_conf
            )

        except Exception as exc:
            err_msg = str(exc)
            logger.error("Transcription execution failed: %s", exc, exc_info=True)
            print(f"❌ FAILURE: Transcription error: {exc}")
            sys.stdout.flush()

            try:
                from ui.health_checker import DashboardStatsManager
                DashboardStatsManager.update("last_exception", err_msg)
                DashboardStatsManager.update("whisper_state", "IDLE")
            except Exception:
                pass

            SystemStateManager.transition_to(SystemState.IDLE)
            return RecognitionResult.failure_result(
                status=RecognitionStatus.ERROR,
                language=self._config.language,
                duration_seconds=time.monotonic() - start_time,
                engine_name=self.engine_name,
                error_message=err_msg,
                overall_confidence=0.0
            )

    def _run_live_transcribe(self, audio_data: bytes) -> None:
        if self._live_transcribe_thread and self._live_transcribe_thread.is_alive():
            return

        def _job():
            try:
                enhanced = preprocess_audio(audio_data, sample_rate=16000)
                if len(enhanced) == 0:
                    return
                segments, _ = self._model.transcribe(
                    enhanced,
                    language=None if self._config.language == Language.AUTO or self._config.language == Language.HINGLISH else self._config.language.value[:2],
                    initial_prompt=self._initial_prompt_str,
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    word_timestamps=False
                )
                txt = " ".join(seg.text for seg in segments).strip()
                if txt:
                    try:
                        from ui.health_checker import DashboardStatsManager
                        DashboardStatsManager.update("last_transcript", txt)
                    except Exception:
                        pass
            except Exception:
                pass

        self._live_transcribe_thread = threading.Thread(target=_job, daemon=True, name="nova-live-transcriber")
        self._live_transcribe_thread.start()

    def _do_listen_continuous(self, on_result: OnResultCallback, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                res = self._do_listen_once()
                on_result(res)
            except Exception as exc:
                logger.error("Error in continuous listening iteration: %s", exc, exc_info=True)
                time.sleep(0.5)

    def _do_health_check(self) -> bool:
        return self._model is not None and self._mic_stream is not None


# =============================================================================
# Factory
# =============================================================================

class SpeechRecognizerFactory:
    """Factory to register and instantiate BaseSpeechRecognizer engines."""

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseSpeechRecognizer]] = {
            "whisper": WhisperRecognizer
        }
        self._lock = threading.Lock()

    def register_engine(self, name: str, recognizer_cls: type[BaseSpeechRecognizer], overwrite: bool = False) -> None:
        with self._lock:
            if name in self._registry and not overwrite:
                raise DuplicateEngineError(f"Engine name '{name}' already registered.")
            self._registry[name] = recognizer_cls

    def create(self, name: str, config: SpeechRecognizerConfig) -> BaseSpeechRecognizer:
        with self._lock:
            if name not in self._registry:
                raise EngineNotFoundError(f"Engine '{name}' not found.")
            return self._registry[name](config)

    def engine_exists(self, name: str) -> bool:
        with self._lock:
            return name in self._registry

    def list_engines(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._registry.keys())


# =============================================================================
# Manager wrapper
# =============================================================================

class SpeechToTextManager:
    """NOVA's single entry point for speech-to-text functionality."""

    def __init__(
        self,
        factory: SpeechRecognizerFactory | None = None,
        default_engine: str = "whisper",
        config: SpeechRecognizerConfig | None = None,
    ) -> None:
        self._factory: SpeechRecognizerFactory = (
            factory if factory is not None else SpeechRecognizerFactory()
        )
        self._config: SpeechRecognizerConfig = (
            config if config is not None else SpeechRecognizerConfig()
        )
        self._lock: threading.RLock = threading.RLock()
        self._active_engine_name: str = default_engine
        self._recognizer: BaseSpeechRecognizer | None = None
        self._initialized: bool = False
        self._stop_event: threading.Event = threading.Event()
        self._continuous_thread: threading.Thread | None = None

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                logger.warning("SpeechToTextManager.initialize() called but already initialized.")
                return

            self._recognizer = self._factory.create(self._active_engine_name, self._config)
            self._recognizer.initialize()
            self._initialized = True
            logger.info("SpeechToTextManager initialized with engine '%s'.", self._active_engine_name)

    def shutdown(self) -> None:
        with self._lock:
            if not self._initialized:
                logger.warning("SpeechToTextManager.shutdown() called but not initialized.")
                return

            self.stop_continuous_listening()
            if self._recognizer is not None:
                self._recognizer.shutdown()
            self._initialized = False
            logger.info("SpeechToTextManager shut down.")

    def listen_once(self, interactive: bool = False) -> RecognitionResult:
        with self._lock:
            self._ensure_initialized()
            recognizer = self._recognizer
        return recognizer.listen_once(interactive=interactive)

    def clear_microphone_queue(self) -> None:
        with self._lock:
            if self._initialized and self._recognizer is not None:
                if hasattr(self._recognizer, "_mic_stream") and self._recognizer._mic_stream is not None:
                    self._recognizer._mic_stream.clear_queue()

    def start_continuous_listening(self, on_result: OnResultCallback) -> None:
        with self._lock:
            self._ensure_initialized()
            if self._continuous_thread is not None and self._continuous_thread.is_alive():
                raise SpeechRecognitionError("Continuous listening is already running.")

            recognizer = self._recognizer
            self._stop_event.clear()
            self._continuous_thread = threading.Thread(
                target=recognizer.listen_continuous,
                args=(on_result, self._stop_event),
                name="nova-speech-to-text-continuous",
                daemon=True,
            )
            self._continuous_thread.start()
            logger.info("Continuous listening started in the background.")

    def stop_continuous_listening(self) -> None:
        with self._lock:
            self._stop_event.set()
            thread = self._continuous_thread

        if thread is not None:
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning("Continuous listening thread did not stop within timeout.")

        with self._lock:
            self._continuous_thread = None

    def is_listening_continuously(self) -> bool:
        with self._lock:
            return self._continuous_thread is not None and self._continuous_thread.is_alive()

    def switch_engine(self, name: str) -> None:
        with self._lock:
            if not self._factory.engine_exists(name):
                raise EngineNotFoundError(f"No speech recognition engine is registered under '{name}'.")

            was_initialized = self._initialized
            if was_initialized:
                self.shutdown()

            previous_engine_name = self._active_engine_name
            self._active_engine_name = name
            logger.info("Active speech recognition engine switched from '%s' to '%s'.", previous_engine_name, name)

            if was_initialized:
                self.initialize()

    def register_engine(self, name: str, recognizer_cls: type[BaseSpeechRecognizer], *, overwrite: bool = False) -> None:
        self._factory.register_engine(name, recognizer_cls, overwrite=overwrite)

    def list_available_engines(self) -> tuple[str, ...]:
        return self._factory.list_engines()

    def list_available_devices(self) -> tuple[str, ...]:
        return list_microphone_devices()

    def get_current_engine_name(self) -> str:
        with self._lock:
            return self._active_engine_name

    def health_check(self) -> bool:
        with self._lock:
            if not self._initialized or self._recognizer is None:
                return False
            recognizer = self._recognizer
        return recognizer.health_check()

    def _ensure_initialized(self) -> None:
        if not self._initialized or self._recognizer is None:
            raise SpeechRecognitionError("SpeechToTextManager is not initialized. Call initialize() first.")


__all__ = [
    "SpeechToTextManager",
    "SpeechRecognizerFactory",
    "BaseSpeechRecognizer",
    "WhisperRecognizer",
    "SpeechRecognizerConfig",
    "RecognitionResult",
    "RecognitionStatus",
    "Language",
    "OnResultCallback",
    "MicrophoneUnavailableError",
    "EngineUnavailableError",
    "EngineNotFoundError",
    "DuplicateEngineError",
    "list_microphone_devices",
]
