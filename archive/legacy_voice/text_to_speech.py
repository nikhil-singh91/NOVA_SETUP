"""Text-to-Speech engine for NOVA.

This module is NOVA's long-term Text-to-Speech subsystem. It converts
text into spoken audio and nothing else: it contains no business
logic, never calls an AI provider, and never touches
:class:`~memory.memory_manager.MemoryManager`. It accepts Unicode text
(including Hindi/Devanagari and mixed Hinglish text) and speaks it;
what the text means or where it came from is entirely outside this
module's concern.

Architecture:
    :class:`BaseTextToSpeech` defines the contract every synthesis
    engine implements, using the same template-method pattern as
    :class:`~providers.base_provider.BaseProvider` and
    :class:`~voice.speech_to_text.BaseSpeechRecognizer`: public
    methods are concrete and handle logging, timing, lifecycle state,
    and error containment, while a small set of protected ``_do_*``
    hooks are implemented by each concrete engine.

    :class:`Pyttsx3Engine` is the first concrete engine, built on the
    ``pyttsx3`` library, which drives the operating system's own
    offline text-to-speech voices (SAPI5 on Windows, NSSpeechSynthesizer
    on macOS, espeak on Linux). It runs entirely offline; no text or
    audio ever leaves the machine.

    :class:`SpeechEngineFactory` lets new engines (Edge TTS,
    ElevenLabs, Azure Speech, Google TTS, Coqui TTS, OpenAI TTS, or
    anything else) be added by registering a new
    :class:`BaseTextToSpeech` subclass under a name, without modifying
    any code in this file.

    :class:`TextToSpeechManager` is the single entry point the rest of
    NOVA should use: it owns engine selection, lifecycle, synchronous
    and queued asynchronous speaking, interrupting speech, and health
    checks, so callers never need to know which concrete engine is
    active.

    :class:`EdgeTTSEngine` is a second concrete engine, built on
    Microsoft's ``edge-tts`` library for high-quality online neural
    voices (defaulting to the Hindi/Hinglish-capable
    ``hi-IN-SwaraNeural`` voice) and ``pygame`` for local playback of
    the synthesized audio. Text is sanitized (emoji, markdown, code
    blocks, URLs, and excessive whitespace are stripped) before being
    sent to the engine, since none of those should be spoken aloud.

Optional Dependencies:
    ``pyttsx3``, ``edge-tts``, and ``pygame`` are each treated as
    optional at import time. If any is missing, this module still
    imports successfully (so callers can inspect enums, dataclasses,
    and build a manager), but any attempt to actually initialize or
    use the engine that depends on it raises a clear
    :class:`EngineUnavailableError` explaining what to install.
"""

from __future__ import annotations

import asyncio
import os
import queue
import re
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Final

from core.exceptions import TextToSpeechError
from core.logger import get_logger

logger = get_logger(__name__)

# --- Optional dependency: pyttsx3 (offline, OS-native speech synthesis) ---
try:
    import pyttsx3

    _PYTTSX3_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    pyttsx3 = None  # type: ignore[assignment]
    _PYTTSX3_AVAILABLE = False

# --- Optional dependency: edge-tts (online, Microsoft Edge neural voices) ---
try:
    import edge_tts

    _EDGE_TTS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    edge_tts = None  # type: ignore[assignment]
    _EDGE_TTS_AVAILABLE = False

# --- Optional dependency: pygame (local audio playback for EdgeTTSEngine) ---
try:
    import pygame

    _PYGAME_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    pygame = None  # type: ignore[assignment]
    _PYGAME_AVAILABLE = False


_DEFAULT_RATE: Final[int] = 215
_DEFAULT_VOLUME: Final[float] = 1.0
_DEFAULT_LANGUAGE: Final[str] = "en"
_DEFAULT_MAX_RETRIES: Final[int] = 2
_DEFAULT_RETRY_BACKOFF_SECONDS: Final[float] = 1.0
_MIN_PITCH: Final[float] = 0.0
_MAX_PITCH: Final[float] = 2.0
_QUEUE_POLL_INTERVAL_SECONDS: Final[float] = 0.25
_THREAD_JOIN_TIMEOUT_SECONDS: Final[float] = 5.0

# --- EdgeTTSEngine-specific defaults ---
_DEFAULT_EDGE_VOICE: Final[str] = "hi-IN-SwaraNeural"
_EDGE_PLAYBACK_POLL_SECONDS: Final[float] = 0.05
_EDGE_TEMP_FILE_PREFIX: Final[str] = "nova_edge_tts_"
_EDGE_TEMP_FILE_SUFFIX: Final[str] = ".mp3"


# =============================================================================
# Exceptions
# =============================================================================


class EngineUnavailableError(TextToSpeechError):
    """Raised when a synthesis engine's runtime dependencies are missing."""

    default_message: str = "The requested text-to-speech engine is unavailable."


class VoiceUnavailableError(TextToSpeechError):
    """Raised when a requested voice cannot be found on the current engine."""

    default_message: str = "The requested voice is unavailable."


class EngineNotFoundError(TextToSpeechError):
    """Raised when a requested synthesis engine is not registered."""

    default_message: str = "The requested text-to-speech engine is not registered."


class DuplicateEngineError(TextToSpeechError):
    """Raised when attempting to register an engine name that already exists."""

    default_message: str = "A text-to-speech engine with this name is already registered."


# =============================================================================
# Global state for full-duplex prevention
# =============================================================================
is_speaking = False


# =============================================================================
# Enums
# =============================================================================


class SpeechStatus(str, Enum):
    """The possible outcomes of a speech synthesis attempt.

    Attributes:
        SUCCESS: The text was spoken to completion.
        CANCELLED: Speech was interrupted before completing.
        ENGINE_UNAVAILABLE: The engine's dependencies are missing or
            the engine is not initialized.
        VOICE_UNAVAILABLE: The configured voice could not be used.
        AUDIO_DEVICE_ERROR: The audio output device could not be
            accessed.
        ERROR: An unexpected error occurred.
    """

    SUCCESS = "success"
    CANCELLED = "cancelled"
    ENGINE_UNAVAILABLE = "engine_unavailable"
    VOICE_UNAVAILABLE = "voice_unavailable"
    AUDIO_DEVICE_ERROR = "audio_device_error"
    ERROR = "error"


class VoiceGender(str, Enum):
    """The gender classification of a synthesized voice.

    Attributes:
        MALE: A voice classified as male.
        FEMALE: A voice classified as female.
        NEUTRAL: A voice classified as gender-neutral.
        UNSPECIFIED: No gender information is available.
    """

    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"
    UNSPECIFIED = "unspecified"


class VoiceEngine(str, Enum):
    """The synthesis engines known to NOVA's roadmap.

    This enum documents NOVA's planned engines for typed, convenient
    selection. It is not the source of truth for which engines are
    actually usable at runtime; :class:`SpeechEngineFactory` accepts
    any string name, so an engine outside this list can still be
    registered and used without modifying this enum.

    Attributes:
        PYTTSX3: The built-in, offline, OS-native engine.
        EDGE_TTS: Microsoft Edge's online neural voices.
        ELEVENLABS: ElevenLabs' expressive neural voices.
        AZURE: Azure Cognitive Services Speech.
        GOOGLE: Google Cloud Text-to-Speech.
        COQUI: Coqui TTS, a self-hostable neural engine.
        OPENAI: OpenAI's text-to-speech API.
    """

    PYTTSX3 = "pyttsx3"
    EDGE_TTS = "edge_tts"
    ELEVENLABS = "elevenlabs"
    AZURE = "azure"
    GOOGLE = "google"
    COQUI = "coqui"
    OPENAI = "openai"


# =============================================================================
# Data model
# =============================================================================


@dataclass(frozen=True)
class SpeechConfig:
    """Configuration for a text-to-speech engine.

    Every value is configurable and has a sensible default; nothing
    in this module hardcodes a value that belongs here.

    Attributes:
        voice_id: An explicit, engine-specific voice identifier to
            use. If ``None``, a voice is selected automatically based
            on ``language`` and ``gender``.
        language: The preferred language for voice selection, as a
            short code (for example, ``"en"`` or ``"hi"``). Text
            itself is always accepted as Unicode regardless of this
            setting.
        gender: The preferred voice gender, used for automatic voice
            selection when ``voice_id`` is not set.
        rate: The speaking rate, in words per minute.
        volume: The output volume, from ``0.0`` (silent) to ``1.0``
            (full volume).
        pitch: An optional pitch adjustment in ``[0.0, 2.0]``, where
            ``1.0`` represents an engine's natural pitch. Reserved for
            engines that support pitch control; see
            :meth:`BaseTextToSpeech.supports_pitch`.
        emotion: An optional emotional style hint (for example,
            ``"cheerful"``). Reserved for engines that support
            emotional styling; see
            :meth:`BaseTextToSpeech.supports_emotion`.
        max_retries: The number of additional attempts made after a
            transient failure before giving up.
        retry_backoff_seconds: The delay between retry attempts, in
            seconds.

    Raises:
        TextToSpeechError: If any field fails validation during
            construction.
    """

    voice_id: str | None = None
    language: str = _DEFAULT_LANGUAGE
    gender: VoiceGender = VoiceGender.UNSPECIFIED
    rate: int = _DEFAULT_RATE
    volume: float = _DEFAULT_VOLUME
    pitch: float | None = None
    emotion: str | None = None
    max_retries: int = _DEFAULT_MAX_RETRIES
    retry_backoff_seconds: float = _DEFAULT_RETRY_BACKOFF_SECONDS

    def __post_init__(self) -> None:
        """Validate this configuration's fields.

        Raises:
            TextToSpeechError: If any field is invalid.
        """
        if not isinstance(self.language, str) or not self.language.strip():
            raise TextToSpeechError("language must be a non-empty string.")
        if not isinstance(self.gender, VoiceGender):
            raise TextToSpeechError(f"gender must be a VoiceGender, got {type(self.gender).__name__}.")
        if not isinstance(self.rate, int) or isinstance(self.rate, bool) or self.rate <= 0:
            raise TextToSpeechError(f"rate must be a positive integer, got {self.rate!r}.")
        if not isinstance(self.volume, (int, float)) or not (0.0 <= self.volume <= 1.0):
            raise TextToSpeechError(f"volume must be between 0.0 and 1.0, got {self.volume!r}.")
        if self.pitch is not None and not (_MIN_PITCH <= self.pitch <= _MAX_PITCH):
            raise TextToSpeechError(
                f"pitch must be between {_MIN_PITCH} and {_MAX_PITCH} when provided, "
                f"got {self.pitch!r}."
            )
        if self.max_retries < 0:
            raise TextToSpeechError("max_retries must be non-negative.")
        if self.retry_backoff_seconds < 0:
            raise TextToSpeechError("retry_backoff_seconds must be non-negative.")


@dataclass(frozen=True)
class VoiceInfo:
    """Descriptive metadata about a single voice available on an engine.

    Attributes:
        id: The engine-specific identifier used to select this voice.
        name: A human-readable name for this voice.
        gender: This voice's gender classification, if known.
        languages: The languages this voice supports, as short codes.
    """

    id: str
    name: str
    gender: VoiceGender
    languages: tuple[str, ...]


@dataclass(frozen=True)
class SpeechResult:
    """The outcome of a single speech synthesis attempt.

    Attributes:
        status: The specific outcome of the attempt.
        success: Whether the text was spoken to completion.
        duration_seconds: How long the attempt took, in seconds.
        engine_name: The name of the engine that produced this
            result.
        voice_id: The voice identifier used, if known.
        timestamp: The UTC timestamp at which this result was
            produced.
        error_message: A human-readable error description, if
            ``success`` is ``False`` and an error occurred.
    """

    status: SpeechStatus
    success: bool
    duration_seconds: float
    engine_name: str
    voice_id: str | None
    timestamp: datetime
    error_message: str | None = None

    @classmethod
    def success_result(
        cls, *, duration_seconds: float, engine_name: str, voice_id: str | None
    ) -> SpeechResult:
        """Construct a successful speech result.

        Args:
            duration_seconds: How long speaking took, in seconds.
            engine_name: The name of the engine that produced this
                result.
            voice_id: The voice identifier used, if known.

        Returns:
            A ``SpeechResult`` with ``status=SUCCESS`` and
            ``success=True``.
        """
        return cls(
            status=SpeechStatus.SUCCESS,
            success=True,
            duration_seconds=duration_seconds,
            engine_name=engine_name,
            voice_id=voice_id,
            timestamp=datetime.now(UTC),
            error_message=None,
        )

    @classmethod
    def failure_result(
        cls,
        *,
        status: SpeechStatus,
        duration_seconds: float,
        engine_name: str,
        voice_id: str | None = None,
        error_message: str | None = None,
    ) -> SpeechResult:
        """Construct an unsuccessful speech result.

        Args:
            status: The specific failure outcome. Must not be
                ``SpeechStatus.SUCCESS``.
            duration_seconds: How long the attempt took, in seconds.
            engine_name: The name of the engine that produced this
                result.
            voice_id: The voice identifier used, if known.
            error_message: A human-readable error description, if
                available.

        Returns:
            A ``SpeechResult`` with the given ``status`` and
            ``success=False``.
        """
        return cls(
            status=status,
            success=False,
            duration_seconds=duration_seconds,
            engine_name=engine_name,
            voice_id=voice_id,
            timestamp=datetime.now(UTC),
            error_message=error_message,
        )


#: The callback signature used by queued asynchronous speech: invoked
#: once per spoken item with that item's result.
OnSpeechCompleteCallback = Callable[[SpeechResult], None]


# =============================================================================
# Base text-to-speech engine
# =============================================================================


class BaseTextToSpeech:
    """Abstract base class for every text-to-speech engine NOVA can use.

    Public methods are concrete and provide logging, timing, lifecycle
    state tracking, and error containment for free. Concrete engines
    implement only the protected ``_do_*`` hooks. This mirrors the
    template-method pattern used by
    :class:`~providers.base_provider.BaseProvider` and
    :class:`~voice.speech_to_text.BaseSpeechRecognizer`.

    Attributes:
        _config: The configuration this engine was constructed with.
        _lock: A reentrant lock guarding lifecycle state transitions.
        _initialized: Whether :meth:`initialize` has completed
            successfully without a subsequent :meth:`shutdown`.
    """

    def __init__(self, config: SpeechConfig) -> None:
        """Initialize shared engine state.

        Args:
            config: The configuration this engine should use.
        """
        self._config: SpeechConfig = config
        self._lock: threading.RLock = threading.RLock()
        self._initialized: bool = False

    @property
    def engine_name(self) -> str:
        """Return the unique, human-readable name of this engine.

        Returns:
            The engine's name (for example, ``"pyttsx3"``).

        Raises:
            NotImplementedError: If a subclass does not override this
                property.
        """
        raise NotImplementedError("Concrete engines must implement engine_name.")

    @property
    def is_available(self) -> bool:
        """Report whether this engine is currently initialized and usable.

        Returns:
            ``True`` if :meth:`initialize` has completed successfully
            and :meth:`shutdown` has not since been called.
        """
        with self._lock:
            return self._initialized

    def initialize(self) -> None:
        """Initialize this engine, making it ready to speak.

        Calling this method more than once without an intervening
        :meth:`shutdown` is a no-op.

        Raises:
            TextToSpeechError: If initialization fails.
        """
        with self._lock:
            if self._initialized:
                logger.warning(
                    "[%s] initialize() called but already initialized.", self.engine_name
                )
                return

            logger.info("[%s] Initializing text-to-speech engine.", self.engine_name)
            start_time = time.monotonic()
            try:
                self._do_initialize()
            except TextToSpeechError:
                raise
            except Exception as exc:
                raise TextToSpeechError(
                    f"[{self.engine_name}] Initialization failed: {exc}",
                    original_exception=exc,
                ) from exc

            self._initialized = True
            elapsed = time.monotonic() - start_time
            logger.info(
                "[%s] Text-to-speech engine initialized in %.3fs.", self.engine_name, elapsed
            )

    def shutdown(self) -> None:
        """Shut down this engine, releasing any held resources.

        Calling this method when the engine is not initialized is a
        no-op.

        Raises:
            TextToSpeechError: If shutdown fails.
        """
        with self._lock:
            if not self._initialized:
                logger.warning(
                    "[%s] shutdown() called but not initialized.", self.engine_name
                )
                return

            logger.info("[%s] Shutting down text-to-speech engine.", self.engine_name)
            try:
                self._do_shutdown()
            except TextToSpeechError:
                raise
            except Exception as exc:
                raise TextToSpeechError(
                    f"[{self.engine_name}] Shutdown failed: {exc}", original_exception=exc
                ) from exc
            finally:
                self._initialized = False
            logger.info("[%s] Text-to-speech engine shut down.", self.engine_name)

    def speak(self, text: str) -> SpeechResult:
        """Speak text synchronously, blocking until complete or interrupted.

        This method never raises: any unexpected failure, or invalid
        input, is captured and returned as a failed
        :class:`SpeechResult` instead of propagating an exception.

        Args:
            text: The Unicode text to speak.

        Returns:
            The outcome of this speech attempt.
        """
        with self._lock:
            if not self._initialized:
                return SpeechResult.failure_result(
                    status=SpeechStatus.ENGINE_UNAVAILABLE,
                    duration_seconds=0.0,
                    engine_name=self.engine_name,
                    voice_id=self._config.voice_id,
                    error_message="Engine is not initialized.",
                )

        if not isinstance(text, str) or not text.strip():
            return SpeechResult.failure_result(
                status=SpeechStatus.ERROR,
                duration_seconds=0.0,
                engine_name=self.engine_name,
                voice_id=self._config.voice_id,
                error_message="Text to speak must be a non-empty string.",
            )

        logger.info("[%s] Speaking text (%d characters).", self.engine_name, len(text))
        start_time = time.monotonic()
        try:
            result = self._do_speak(text)
        except Exception as exc:  # noqa: BLE001 - speak() must never crash the caller
            elapsed = time.monotonic() - start_time
            logger.error(
                "[%s] Unexpected error during speak: %s", self.engine_name, exc, exc_info=True
            )
            result = SpeechResult.failure_result(
                status=SpeechStatus.ERROR,
                duration_seconds=elapsed,
                engine_name=self.engine_name,
                voice_id=self._config.voice_id,
                error_message=str(exc),
            )

        logger.info(
            "[%s] speak completed: status=%s, success=%s, duration=%.3fs.",
            self.engine_name,
            result.status.value,
            result.success,
            result.duration_seconds,
        )
        return result

    def stop(self) -> None:
        """Interrupt any speech currently in progress on this engine.

        This method never raises. It is a no-op if nothing is
        currently being spoken.
        """
        try:
            self._do_stop()
        except Exception as exc:  # noqa: BLE001 - stop() must never crash the caller
            logger.warning("[%s] stop() failed: %s", self.engine_name, exc, exc_info=True)

    def health_check(self) -> bool:
        """Check whether this engine is currently healthy and usable.

        Returns:
            ``True`` if the health check succeeds, ``False``
            otherwise. Never raises.
        """
        try:
            return self._do_health_check()
        except Exception as exc:  # noqa: BLE001 - health checks must never crash the caller
            logger.warning(
                "[%s] health_check failed: %s", self.engine_name, exc, exc_info=True
            )
            return False

    def list_voices(self) -> tuple[VoiceInfo, ...]:
        """List every voice available on this engine.

        Returns:
            A tuple of available voices. Returns an empty tuple, and
            logs a warning, if voice enumeration fails. Never raises.
        """
        try:
            return self._do_list_voices()
        except Exception as exc:  # noqa: BLE001 - voice listing must never crash the caller
            logger.warning(
                "[%s] Failed to list voices: %s", self.engine_name, exc, exc_info=True
            )
            return ()

    def supports_pitch(self) -> bool:
        """Report whether this engine can adjust pitch.

        Returns:
            ``False`` by default. Engines with pitch control must
            override this method to return ``True``.
        """
        return False

    def supports_emotion(self) -> bool:
        """Report whether this engine can apply emotional styling.

        Returns:
            ``False`` by default. Engines with emotional styling
            support must override this method to return ``True``.
        """
        return False

    def supports_ssml(self) -> bool:
        """Report whether this engine accepts SSML markup.

        Returns:
            ``False`` by default. Engines with SSML support must
            override this method to return ``True``.
        """
        return False

    def supports_streaming(self) -> bool:
        """Report whether this engine can stream audio incrementally.

        Returns:
            ``False`` by default. Engines with streaming support must
            override this method to return ``True``.
        """
        return False

    def _do_initialize(self) -> None:
        """Perform engine-specific initialization.

        Raises:
            NotImplementedError: If a subclass does not override this
                method.
        """
        raise NotImplementedError("Concrete engines must implement _do_initialize.")

    def _do_shutdown(self) -> None:
        """Perform engine-specific teardown.

        Raises:
            NotImplementedError: If a subclass does not override this
                method.
        """
        raise NotImplementedError("Concrete engines must implement _do_shutdown.")

    def _do_speak(self, text: str) -> SpeechResult:
        """Perform the engine-specific work of speaking text.

        Args:
            text: The Unicode text to speak.

        Returns:
            The outcome of this speech attempt.

        Raises:
            NotImplementedError: If a subclass does not override this
                method.
        """
        raise NotImplementedError("Concrete engines must implement _do_speak.")

    def _do_stop(self) -> None:
        """Perform the engine-specific work of interrupting current speech.

        Raises:
            NotImplementedError: If a subclass does not override this
                method.
        """
        raise NotImplementedError("Concrete engines must implement _do_stop.")

    def _do_health_check(self) -> bool:
        """Perform the engine-specific work of checking engine health.

        Returns:
            ``True`` if the engine is healthy.

        Raises:
            NotImplementedError: If a subclass does not override this
                method.
        """
        raise NotImplementedError("Concrete engines must implement _do_health_check.")

    def _do_list_voices(self) -> tuple[VoiceInfo, ...]:
        """Perform the engine-specific work of listing available voices.

        Returns:
            A tuple of available voices.

        Raises:
            NotImplementedError: If a subclass does not override this
                method.
        """
        raise NotImplementedError("Concrete engines must implement _do_list_voices.")


# =============================================================================
# pyttsx3 engine
# =============================================================================


class Pyttsx3Engine(BaseTextToSpeech):
    """Text-to-speech engine backed by the offline ``pyttsx3`` library.

    ``pyttsx3`` drives the operating system's own native voices, so no
    text or audio ever leaves the machine. It has a well-known
    limitation: a single ``pyttsx3`` engine instance is not safe to
    drive concurrently from multiple threads. This class serializes
    all speech and interruption calls through a dedicated lock to
    respect that constraint, independent of the lifecycle lock
    inherited from :class:`BaseTextToSpeech`.

    Attributes:
        _engine: The underlying ``pyttsx3`` engine instance, or
            ``None`` before initialization.
        _speak_lock: A lock serializing calls into the underlying
            engine, since it is not safe for concurrent use.
        _cancel_event: An event set by :meth:`_do_stop` to signal that
            an in-progress :meth:`_do_speak` call should be treated as
            cancelled.
    """

    def __init__(self, config: SpeechConfig) -> None:
        """Initialize a pyttsx3 engine instance.

        Args:
            config: The configuration this engine should use.
        """
        super().__init__(config)
        self._engine: Any = None
        self._speak_lock: threading.Lock = threading.Lock()
        self._cancel_event: threading.Event = threading.Event()

    @property
    def engine_name(self) -> str:
        """Return the unique name of this engine.

        Returns:
            The literal string ``"pyttsx3"``.
        """
        return "pyttsx3"

    def _do_initialize(self) -> None:
        """Construct the underlying pyttsx3 engine and apply configuration.

        Raises:
            EngineUnavailableError: If ``pyttsx3`` is not installed, or
                the underlying engine fails to construct.
        """
        if not _PYTTSX3_AVAILABLE:
            raise EngineUnavailableError(
                "The 'pyttsx3' package is required for this engine. Install it "
                "with: pip install pyttsx3"
            )

        try:
            self._engine = pyttsx3.init()
        except Exception as exc:
            raise EngineUnavailableError(
                f"Failed to construct the pyttsx3 engine: {exc}", original_exception=exc
            ) from exc

        self._apply_configuration()

    def _do_shutdown(self) -> None:
        """Release the underlying pyttsx3 engine."""
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception as exc:  # noqa: BLE001 - shutdown must proceed regardless
                logger.debug("[pyttsx3] Error while stopping engine during shutdown: %s", exc)
        self._engine = None

    def _do_speak(self, text: str) -> SpeechResult:
        """Speak text, retrying on transient engine failures.

        Args:
            text: The Unicode text to speak.

        Returns:
            The outcome of this speech attempt.
        """
        start_time = time.monotonic()
        last_error: Exception | None = None
        attempts = self._config.max_retries + 1

        with self._speak_lock:
            self._cancel_event.clear()

            for attempt_number in range(1, attempts + 1):
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception as exc:  # noqa: BLE001 - transient engine errors are retried
                    last_error = exc
                    logger.warning(
                        "[pyttsx3] Speech synthesis error on attempt %d/%d: %s",
                        attempt_number,
                        attempts,
                        exc,
                    )
                    if attempt_number < attempts:
                        time.sleep(self._config.retry_backoff_seconds)
                        continue
                    return SpeechResult.failure_result(
                        status=SpeechStatus.AUDIO_DEVICE_ERROR,
                        duration_seconds=time.monotonic() - start_time,
                        engine_name=self.engine_name,
                        voice_id=self._config.voice_id,
                        error_message=str(exc),
                    )

                if self._cancel_event.is_set():
                    return SpeechResult.failure_result(
                        status=SpeechStatus.CANCELLED,
                        duration_seconds=time.monotonic() - start_time,
                        engine_name=self.engine_name,
                        voice_id=self._config.voice_id,
                        error_message="Speech was interrupted before completing.",
                    )

                return SpeechResult.success_result(
                    duration_seconds=time.monotonic() - start_time,
                    engine_name=self.engine_name,
                    voice_id=self._config.voice_id,
                )

        return SpeechResult.failure_result(
            status=SpeechStatus.ERROR,
            duration_seconds=time.monotonic() - start_time,
            engine_name=self.engine_name,
            voice_id=self._config.voice_id,
            error_message=(
                str(last_error) if last_error else "Speech synthesis failed for an unknown reason."
            ),
        )

    def _do_stop(self) -> None:
        """Signal cancellation and ask the underlying engine to stop speaking."""
        self._cancel_event.set()
        if self._engine is not None:
            self._engine.stop()

    def _do_health_check(self) -> bool:
        """Verify the pyttsx3 dependency is available and the engine is constructed.

        Returns:
            ``True`` if ``pyttsx3`` is installed and the engine
            instance has been constructed.
        """
        return _PYTTSX3_AVAILABLE and self._engine is not None

    def _do_list_voices(self) -> tuple[VoiceInfo, ...]:
        """List every voice pyttsx3 reports as available on this system.

        Returns:
            A tuple of available voices.
        """
        if self._engine is None:
            return ()

        voices = self._engine.getProperty("voices") or ()
        voice_infos = []
        for voice in voices:
            voice_infos.append(
                VoiceInfo(
                    id=voice.id,
                    name=voice.name,
                    gender=self._map_gender(getattr(voice, "gender", None)),
                    languages=self._decode_languages(getattr(voice, "languages", ())),
                )
            )
        return tuple(voice_infos)

    def _apply_configuration(self) -> None:
        """Apply the current :class:`SpeechConfig` to the underlying engine.

        Pitch and emotion are intentionally not applied here: pyttsx3
        has no cross-platform support for either, which is why
        :meth:`supports_pitch` and :meth:`supports_emotion` both
        report ``False`` for this engine.
        """
        self._engine.setProperty("rate", self._config.rate)
        self._engine.setProperty("volume", self._config.volume)

        if self._config.voice_id is not None:
            self._engine.setProperty("voice", self._config.voice_id)
            return

        selected_voice = self._select_voice_for_preferences()
        if selected_voice is not None:
            self._engine.setProperty("voice", selected_voice.id)

    def _select_voice_for_preferences(self) -> VoiceInfo | None:
        """Best-effort selection of a voice matching the configured language and gender.

        pyttsx3's voice metadata (language and gender fields) is
        reported inconsistently across operating systems and
        text-to-speech backends, so this matching is heuristic rather
        than guaranteed.

        Returns:
            A matching :class:`VoiceInfo`, or ``None`` if no voice
            metadata is available or no match is found (in which case
            the engine's own default voice remains in effect).
        """
        available_voices = self._do_list_voices()
        if not available_voices:
            return None

        language_prefix = self._config.language.strip().lower()[:2]

        def matches_language(voice: VoiceInfo) -> bool:
            return any(lang.lower().startswith(language_prefix) for lang in voice.languages)

        def matches_gender(voice: VoiceInfo) -> bool:
            return (
                self._config.gender is VoiceGender.UNSPECIFIED
                or voice.gender is self._config.gender
            )

        for voice in available_voices:
            if matches_language(voice) and matches_gender(voice):
                return voice

        for voice in available_voices:
            if matches_language(voice):
                return voice

        return None

    @staticmethod
    def _map_gender(raw_gender: Any) -> VoiceGender:
        """Map pyttsx3's inconsistent raw gender metadata to :class:`VoiceGender`.

        Args:
            raw_gender: The raw ``gender`` attribute from a pyttsx3
                voice object, which may be ``None``, a string, bytes,
                or another platform-specific representation.

        Returns:
            The best-effort corresponding :class:`VoiceGender`.
        """
        if raw_gender is None:
            return VoiceGender.UNSPECIFIED

        text_value = raw_gender.decode("utf-8", errors="ignore") if isinstance(raw_gender, bytes) else str(raw_gender)
        normalized = text_value.strip().lower()

        if "female" in normalized:
            return VoiceGender.FEMALE
        if "male" in normalized:
            return VoiceGender.MALE
        return VoiceGender.UNSPECIFIED

    @staticmethod
    def _decode_languages(raw_languages: Any) -> tuple[str, ...]:
        """Decode pyttsx3's inconsistent raw language metadata into strings.

        Args:
            raw_languages: The raw ``languages`` attribute from a
                pyttsx3 voice object, which may contain strings,
                bytes, or be entirely empty depending on platform.

        Returns:
            A tuple of decoded language codes.
        """
        if not raw_languages:
            return ()

        decoded: list[str] = []
        for entry in raw_languages:
            if isinstance(entry, bytes):
                decoded.append(entry.decode("utf-8", errors="ignore"))
            else:
                decoded.append(str(entry))
        return tuple(value for value in decoded if value)


# =============================================================================
# edge-tts engine
# =============================================================================


class EdgeTTSEngine(BaseTextToSpeech):
    """Text-to-speech engine backed by Microsoft's online ``edge-tts`` voices.

    ``edge-tts`` produces high-quality neural speech, including strong
    Hindi and Hinglish support via ``hi-IN-SwaraNeural`` (the default
    voice for this engine). Synthesis is performed asynchronously
    (``edge_tts.Communicate.save``) into a temporary MP3 file, which is
    then played back locally with ``pygame`` and deleted immediately
    afterward, regardless of outcome, so no temporary audio files are
    ever left behind.

    Text is sanitized before synthesis: emoji, markdown formatting,
    fenced/inline code blocks, URLs, and excessive whitespace are all
    stripped, since none of these should be spoken aloud.

    Like :class:`Pyttsx3Engine`, a single instance of this engine is
    not safe to drive concurrently from multiple threads (the
    underlying ``pygame`` mixer is a single, process-wide audio
    device), so all speech and interruption calls are serialized
    through a dedicated lock, independent of the lifecycle lock
    inherited from :class:`BaseTextToSpeech`.

    Attributes:
        _speak_lock: A lock serializing calls into synthesis and
            playback, since both are not safe for concurrent use.
        _cancel_event: An event set by :meth:`_do_stop` to signal that
            an in-progress :meth:`_do_speak` call should be treated as
            cancelled.
        _mixer_ready: Whether the ``pygame`` audio mixer has been
            successfully initialized.
    """

    _CODE_BLOCK_PATTERN: Final[re.Pattern[str]] = re.compile(r"```.*?```", re.DOTALL)
    _INLINE_CODE_PATTERN: Final[re.Pattern[str]] = re.compile(r"`[^`]*`")
    _MARKDOWN_LINK_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[([^\]]*)\]\([^)]*\)")
    _URL_PATTERN: Final[re.Pattern[str]] = re.compile(r"https?://\S+|www\.\S+")
    _MARKDOWN_HEADER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
    _MARKDOWN_EMPHASIS_PATTERN: Final[re.Pattern[str]] = re.compile(r"(\*\*\*|\*\*|\*|___|__|_|~~)")
    _EMOJI_PATTERN: Final[re.Pattern[str]] = re.compile(
        "["
        "\U0001f300-\U0001faff"
        "\U00002600-\U000027bf"
        "\U0001f1e6-\U0001f1ff"
        "\U0001f900-\U0001f9ff"
        "\U00002b00-\U00002bff"
        "\U0001f000-\U0001f0ff"
        "\U0000fe00-\U0000fe0f"
        "]+",
        flags=re.UNICODE,
    )
    _WHITESPACE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\s+")

    def __init__(self, config: SpeechConfig) -> None:
        """Initialize an edge-tts engine instance.

        Args:
            config: The configuration this engine should use.
        """
        super().__init__(config)
        self._speak_lock: threading.Lock = threading.Lock()
        self._cancel_event: threading.Event = threading.Event()
        self._mixer_ready: bool = False

    @property
    def engine_name(self) -> str:
        """Return the unique name of this engine.

        Returns:
            The literal string ``"edge_tts"``.
        """
        return "edge_tts"

    def supports_pitch(self) -> bool:
        """Report that edge-tts supports pitch adjustment.

        Returns:
            ``True``.
        """
        return True

    def _do_initialize(self) -> None:
        """Verify dependencies are installed and initialize the audio mixer.

        Raises:
            EngineUnavailableError: If ``edge-tts`` or ``pygame`` is
                not installed, or the audio mixer fails to initialize.
        """
        if not _EDGE_TTS_AVAILABLE:
            raise EngineUnavailableError(
                "The 'edge-tts' package is required for this engine. Install it "
                "with: pip install edge-tts"
            )
        if not _PYGAME_AVAILABLE:
            raise EngineUnavailableError(
                "The 'pygame' package is required for this engine. Install it "
                "with: pip install pygame"
            )

        try:
            pygame.mixer.init()
        except Exception as exc:
            raise EngineUnavailableError(
                f"Failed to initialize the pygame audio mixer: {exc}", original_exception=exc
            ) from exc

        self._mixer_ready = True

    def _do_shutdown(self) -> None:
        """Stop any playback and release the audio mixer."""
        if _PYGAME_AVAILABLE and self._mixer_ready:
            try:
                pygame.mixer.music.stop()
            except Exception as exc:  # noqa: BLE001 - shutdown must proceed regardless
                logger.debug("[edge_tts] Error while stopping playback during shutdown: %s", exc)
            try:
                pygame.mixer.quit()
            except Exception as exc:  # noqa: BLE001 - shutdown must proceed regardless
                logger.debug("[edge_tts] Error while releasing the audio mixer: %s", exc)

        self._mixer_ready = False

    def _do_speak(self, text: str) -> SpeechResult:
        """Sanitize, synthesize, and play text, retrying on transient failures.

        Args:
            text: The Unicode text to speak.

        Returns:
            The outcome of this speech attempt.
        """
        start_time = time.monotonic()
        voice_id = self._config.voice_id or _DEFAULT_EDGE_VOICE
        sanitized_text = self._sanitize_text(text)

        if not sanitized_text:
            return SpeechResult.failure_result(
                status=SpeechStatus.ERROR,
                duration_seconds=time.monotonic() - start_time,
                engine_name=self.engine_name,
                voice_id=voice_id,
                error_message="Text was empty after removing emoji, markdown, code, and URLs.",
            )

        last_error: Exception | None = None
        attempts = self._config.max_retries + 1

        with self._speak_lock:
            self._cancel_event.clear()

            for attempt_number in range(1, attempts + 1):
                temp_path: str | None = None
                try:
                    temp_path = self._synthesize_to_file(sanitized_text, voice_id)

                    if self._cancel_event.is_set():
                        return SpeechResult.failure_result(
                            status=SpeechStatus.CANCELLED,
                            duration_seconds=time.monotonic() - start_time,
                            engine_name=self.engine_name,
                            voice_id=voice_id,
                            error_message="Speech was interrupted before playback began.",
                        )

                    self._play_audio_file(temp_path)
                except Exception as exc:  # noqa: BLE001 - transient errors are retried
                    last_error = exc
                    logger.warning(
                        "[edge_tts] Speech synthesis/playback error on attempt %d/%d: %s",
                        attempt_number,
                        attempts,
                        exc,
                    )
                    if attempt_number < attempts:
                        time.sleep(self._config.retry_backoff_seconds)
                        continue
                    return SpeechResult.failure_result(
                        status=SpeechStatus.AUDIO_DEVICE_ERROR,
                        duration_seconds=time.monotonic() - start_time,
                        engine_name=self.engine_name,
                        voice_id=voice_id,
                        error_message=str(exc),
                    )
                finally:
                    self._cleanup_temp_file(temp_path)

                if self._cancel_event.is_set():
                    return SpeechResult.failure_result(
                        status=SpeechStatus.CANCELLED,
                        duration_seconds=time.monotonic() - start_time,
                        engine_name=self.engine_name,
                        voice_id=voice_id,
                        error_message="Speech was interrupted before completing.",
                    )

                return SpeechResult.success_result(
                    duration_seconds=time.monotonic() - start_time,
                    engine_name=self.engine_name,
                    voice_id=voice_id,
                )

        return SpeechResult.failure_result(
            status=SpeechStatus.ERROR,
            duration_seconds=time.monotonic() - start_time,
            engine_name=self.engine_name,
            voice_id=voice_id,
            error_message=(
                str(last_error) if last_error else "Speech synthesis failed for an unknown reason."
            ),
        )

    def _do_stop(self) -> None:
        """Signal cancellation and immediately stop any active playback."""
        self._cancel_event.set()
        if _PYGAME_AVAILABLE and self._mixer_ready:
            try:
                pygame.mixer.music.stop()
            except Exception as exc:  # noqa: BLE001 - stop() must proceed regardless
                logger.debug("[edge_tts] Error while stopping playback: %s", exc)

    def _do_health_check(self) -> bool:
        """Verify dependencies are available and the audio mixer is ready.

        Returns:
            ``True`` if ``edge-tts`` and ``pygame`` are installed and
            the audio mixer has been initialized.
        """
        return _EDGE_TTS_AVAILABLE and _PYGAME_AVAILABLE and self._mixer_ready

    def _do_list_voices(self) -> tuple[VoiceInfo, ...]:
        """List every voice edge-tts currently offers.

        This performs a network request to Microsoft's voice list
        service every time it is called.

        Returns:
            A tuple of available voices.
        """
        raw_voices = asyncio.run(edge_tts.list_voices())
        voice_infos = []
        for raw_voice in raw_voices:
            short_name = str(raw_voice.get("ShortName", ""))
            if not short_name:
                continue
            locale = str(raw_voice.get("Locale", ""))
            gender = self._map_gender(raw_voice.get("Gender"))
            friendly_name = str(raw_voice.get("FriendlyName", short_name))
            voice_infos.append(
                VoiceInfo(
                    id=short_name,
                    name=friendly_name,
                    gender=gender,
                    languages=(locale,) if locale else (),
                )
            )
        return tuple(voice_infos)

    def _synthesize_to_file(self, text: str, voice_id: str) -> str:
        """Synthesize sanitized text into a temporary MP3 file.

        Args:
            text: The already-sanitized text to synthesize.
            voice_id: The edge-tts voice identifier to use.

        Returns:
            The path to the generated temporary MP3 file. The caller
            is responsible for deleting it via :meth:`_cleanup_temp_file`.

        Raises:
            Exception: Any error raised by the underlying ``edge-tts``
                synthesis call, propagated to the retry loop in
                :meth:`_do_speak`.
        """
        file_descriptor, temp_path = tempfile.mkstemp(
            prefix=_EDGE_TEMP_FILE_PREFIX, suffix=_EDGE_TEMP_FILE_SUFFIX
        )
        os.close(file_descriptor)

        rate = self._format_rate(self._config.rate)
        volume = self._format_volume(self._config.volume)
        pitch = self._format_pitch(self._config.pitch)

        asyncio.run(self._generate_speech_file(text, voice_id, rate, volume, pitch, temp_path))
        return temp_path

    @staticmethod
    async def _generate_speech_file(
        text: str, voice_id: str, rate: str, volume: str, pitch: str, output_path: str
    ) -> None:
        """Asynchronously synthesize speech and save it to a file.

        Args:
            text: The sanitized text to synthesize.
            voice_id: The edge-tts voice identifier to use.
            rate: The edge-tts rate adjustment string (for example,
                ``"+10%"``).
            volume: The edge-tts volume adjustment string.
            pitch: The edge-tts pitch adjustment string.
            output_path: The file path to write the synthesized audio
                to.
        """

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate,
            volume=volume,
            pitch=pitch,
        )
        await communicate.save(output_path)

    def _play_audio_file(self, path: str) -> None:
        """Play an audio file with pygame, honoring cancellation immediately.

        Args:
            path: The path to the audio file to play.
        """
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()

        # Wait up to 300ms for pygame to register busy state and begin buffering/playback
        for _ in range(30):
            if pygame.mixer.music.get_busy():
                break
            time.sleep(0.01)

        while pygame.mixer.music.get_busy():
            if self._cancel_event.is_set():
                pygame.mixer.music.stop()
                break
            time.sleep(_EDGE_PLAYBACK_POLL_SECONDS)

    @staticmethod
    def _cleanup_temp_file(path: str | None) -> None:
        """Release any file handle on and delete a temporary audio file.

        This is always called from a ``finally`` block in
        :meth:`_do_speak`, regardless of whether synthesis or playback
        succeeded, so no temporary audio file is ever left behind.

        Args:
            path: The path to the temporary file to remove, or
                ``None`` if none was created yet.
        """
        if not path:
            return

        if _PYGAME_AVAILABLE and hasattr(pygame.mixer.music, "unload"):
            try:
                pygame.mixer.music.unload()
            except Exception as exc:  # noqa: BLE001 - cleanup must proceed regardless
                logger.debug("[edge_tts] Error while unloading audio file: %s", exc)

        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as exc:
            logger.debug("[edge_tts] Failed to remove temporary file '%s': %s", path, exc)

    @staticmethod
    def _format_rate(rate: int) -> str:
        """Convert an absolute words-per-minute rate into an edge-tts rate string.

        Args:
            rate: The configured rate, in words per minute.

        Returns:
            A percentage delta string relative to NOVA's default rate
            (for example, ``"+14%"`` or ``"-20%"``).
        """
        delta_percent = ((rate - _DEFAULT_RATE) / _DEFAULT_RATE) * 100 + 20
        sign = "+" if delta_percent >= 0 else ""
        return f"{sign}{delta_percent:.0f}%"

    @staticmethod
    def _format_volume(volume: float) -> str:
        """Convert a ``[0.0, 1.0]`` volume into an edge-tts volume string.

        Args:
            volume: The configured volume, from ``0.0`` to ``1.0``.

        Returns:
            A percentage delta string relative to full volume (for
            example, ``"+0%"`` or ``"-50%"``).
        """
        delta_percent = (volume - 1.0) * 100
        sign = "+" if delta_percent >= 0 else ""
        return f"{sign}{delta_percent:.0f}%"

    @staticmethod
    def _format_pitch(pitch: float | None) -> str:
        """Convert a ``[0.0, 2.0]`` pitch into an edge-tts pitch string.

        Args:
            pitch: The configured pitch, where ``1.0`` is natural, or
                ``None`` if unset.

        Returns:
            A Hertz delta string (for example, ``"+0Hz"`` or
            ``"-25Hz"``).
        """
        if pitch is None:
            return "+0Hz"
        delta_hz = (pitch - 1.0) * 50
        sign = "+" if delta_hz >= 0 else ""
        return f"{sign}{delta_hz:.0f}Hz"

    @staticmethod
    def _map_gender(raw_gender: Any) -> VoiceGender:
        """Map edge-tts's raw gender metadata to :class:`VoiceGender`.

        Args:
            raw_gender: The raw ``Gender`` field from edge-tts's voice
                list (typically ``"Male"`` or ``"Female"``).

        Returns:
            The corresponding :class:`VoiceGender`.
        """
        if raw_gender is None:
            return VoiceGender.UNSPECIFIED
        normalized = str(raw_gender).strip().lower()
        if "female" in normalized:
            return VoiceGender.FEMALE
        if "male" in normalized:
            return VoiceGender.MALE
        return VoiceGender.UNSPECIFIED

    @classmethod
    def _sanitize_text(cls, text: str) -> str:
        """Strip emoji, markdown, code blocks, URLs, and excess whitespace.

        Args:
            text: The raw text to sanitize.

        Returns:
            The sanitized text, ready for speech synthesis.
        """
        cleaned = cls._CODE_BLOCK_PATTERN.sub(" ", text)
        cleaned = cls._INLINE_CODE_PATTERN.sub(" ", cleaned)
        cleaned = cls._MARKDOWN_LINK_PATTERN.sub(r"\1", cleaned)
        cleaned = cls._URL_PATTERN.sub(" ", cleaned)
        cleaned = cls._MARKDOWN_HEADER_PATTERN.sub("", cleaned)
        cleaned = cls._MARKDOWN_EMPHASIS_PATTERN.sub("", cleaned)
        cleaned = cls._EMOJI_PATTERN.sub("", cleaned)
        cleaned = cls._WHITESPACE_PATTERN.sub(" ", cleaned).strip()
        return cleaned


# =============================================================================
# Factory
# =============================================================================


class SpeechEngineFactory:
    """Constructs :class:`BaseTextToSpeech` instances by registered engine name.

    New engines are added by calling :meth:`register_engine`; no
    existing code needs to change. ``"pyttsx3"`` (offline) and
    ``"edge_tts"`` (online, higher-quality neural voices) are
    registered by default; ElevenLabs, Azure Speech, Google TTS, Coqui
    TTS, OpenAI TTS, or any future engine can be added the same way.

    Attributes:
        _lock: A reentrant lock guarding the engine registry.
        _registry: The mapping of engine name to engine class.
    """

    def __init__(self) -> None:
        """Construct a factory pre-registered with NOVA's built-in engines."""
        self._lock: threading.RLock = threading.RLock()
        self._registry: dict[str, type[BaseTextToSpeech]] = {}
        self.register_engine(VoiceEngine.PYTTSX3.value, Pyttsx3Engine)
        self.register_engine(VoiceEngine.EDGE_TTS.value, EdgeTTSEngine)

    def register_engine(
        self, name: str, engine_cls: type[BaseTextToSpeech], *, overwrite: bool = False
    ) -> None:
        """Register an engine class under a unique name.

        Args:
            name: The unique name to register the engine under.
            engine_cls: The :class:`BaseTextToSpeech` subclass to
                construct when this engine is requested.
            overwrite: If ``True``, replace an existing registration
                under the same name.

        Raises:
            DuplicateEngineError: If ``name`` is already registered
                and ``overwrite`` is ``False``.
        """
        with self._lock:
            if name in self._registry and not overwrite:
                raise DuplicateEngineError(
                    f"A text-to-speech engine is already registered under '{name}'."
                )
            self._registry[name] = engine_cls
            logger.info("Text-to-speech engine '%s' registered.", name)

    def create(self, name: str, config: SpeechConfig) -> BaseTextToSpeech:
        """Construct a new engine instance for a registered engine name.

        Args:
            name: The name of the engine to construct.
            config: The configuration to construct the engine with.

        Returns:
            A newly constructed, uninitialized engine.

        Raises:
            EngineNotFoundError: If no engine is registered under
                ``name``.
        """
        with self._lock:
            engine_cls = self._registry.get(name)
            if engine_cls is None:
                raise EngineNotFoundError(
                    f"No text-to-speech engine is registered under '{name}'."
                )
            return engine_cls(config)

    def engine_exists(self, name: str) -> bool:
        """Check whether an engine is registered under a given name.

        Args:
            name: The name to check.

        Returns:
            ``True`` if an engine is registered under ``name``.
        """
        with self._lock:
            return name in self._registry

    def list_engines(self) -> tuple[str, ...]:
        """List the names of every registered engine.

        Returns:
            A tuple of registered engine names.
        """
        with self._lock:
            return tuple(self._registry.keys())


# =============================================================================
# Manager
# =============================================================================


class TextToSpeechManager:
    """NOVA's single entry point for text-to-speech functionality.

    ``TextToSpeechManager`` owns engine selection, lifecycle,
    synchronous speaking, queued asynchronous speaking (a background
    worker thread processes queued text in order), interrupting
    speech, and health checks, so the rest of NOVA never needs to know
    which concrete engine is active.

    Note:
        single mechanism here, :meth:`speak_async`: every call enqueues
        text for a background worker to speak in order, which is what
        both queuing and asynchronous speaking mean in practice. A
        separate, identically behaving method was deliberately not
        added, to avoid duplicating this logic under two names.

    Attributes:
        _factory: The factory used to construct engine instances.
        _config: The configuration used to construct the active
            engine.
        _lock: A reentrant lock guarding all internal state.
        _active_engine_name: The name of the currently selected
            engine.
        _engine: The currently active engine instance, or ``None``
            before initialization.
        _initialized: Whether the manager has completed
            :meth:`initialize`.
        _queue: The pending queue of ``(text, callback)`` pairs
            awaiting asynchronous speech.
        _worker_thread: The background thread processing the queue, or
            ``None`` before initialization.
        _worker_stop_event: The event used to signal the worker thread
            to stop.
        _speaking_event: An event set for the duration of an active
            speech attempt, used by :meth:`is_speaking`.
    """

    def __init__(
        self,
        factory: SpeechEngineFactory | None = None,
        # default_engine: str = VoiceEngine.PYTTSX3.value,
        default_engine: str = VoiceEngine.EDGE_TTS.value,
        config: SpeechConfig | None = None,
    ) -> None:
        """Construct an uninitialized text-to-speech manager.

        Args:
            factory: An optional, pre-configured
                :class:`SpeechEngineFactory`. If ``None``, a new
                factory with NOVA's built-in engines is created.
            default_engine: The name of the engine to use by default.
            config: The configuration to construct the active engine
                with. If ``None``, default configuration is used.
        """
        self._factory: SpeechEngineFactory = factory if factory is not None else SpeechEngineFactory()
        self._config: SpeechConfig = config if config is not None else SpeechConfig()
        self._lock: threading.RLock = threading.RLock()
        self._active_engine_name: str = default_engine
        self._engine: BaseTextToSpeech | None = None
        self._initialized: bool = False

        self._queue: queue.Queue[tuple[str, OnSpeechCompleteCallback | None]] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._worker_stop_event: threading.Event = threading.Event()
        self._speaking_event: threading.Event = threading.Event()
        self._interrupted: threading.Event = threading.Event()

    def initialize(self) -> None:
        """Construct and initialize the active engine, and start the worker thread.

        Calling this method more than once without an intervening
        :meth:`shutdown` is a no-op.

        Raises:
            EngineNotFoundError: If the active engine is not
                registered with the factory.
            TextToSpeechError: If the engine fails to initialize.
        """
        with self._lock:
            if self._initialized:
                logger.warning(
                    "TextToSpeechManager.initialize() called but already initialized."
                )
                return

            self._engine = self._factory.create(self._active_engine_name, self._config)
            self._engine.initialize()

            self._worker_stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._run_worker_loop,
                name="nova-text-to-speech-worker",
                daemon=True,
            )
            self._worker_thread.start()

            self._initialized = True
            logger.info(
                "TextToSpeechManager initialized with engine '%s'.", self._active_engine_name
            )

    def shutdown(self) -> None:
        """Stop the worker thread and shut down the active engine.

        Calling this method when the manager is not initialized is a
        no-op.
        """
        with self._lock:
            if not self._initialized:
                logger.warning("TextToSpeechManager.shutdown() called but not initialized.")
                return

            self._worker_stop_event.set()
            worker_thread = self._worker_thread

        self.stop(clear_queue=True)

        if worker_thread is not None:
            worker_thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)
            if worker_thread.is_alive():
                logger.warning(
                    "Text-to-speech worker thread did not stop within %.1fs.",
                    _THREAD_JOIN_TIMEOUT_SECONDS,
                )

        with self._lock:
            self._worker_thread = None
            if self._engine is not None:
                self._engine.shutdown()
            self._initialized = False
            logger.info("TextToSpeechManager shut down.")

    def speak(self, text: str) -> SpeechResult:
        """Speak text synchronously, blocking until complete or interrupted.

        Args:
            text: The Unicode text to speak.

        Returns:
            The outcome of this speech attempt.

        Raises:
            TextToSpeechError: If the manager is not initialized.
        """
        with self._lock:
            self._ensure_initialized()
            engine = self._engine

        self._speaking_event.set()
        try:
            return engine.speak(text)
        finally:
            self._speaking_event.clear()

    def speak_async(
        self, text: str, on_complete: OnSpeechCompleteCallback | None = None
    ) -> None:
        """Enqueue text to be spoken asynchronously by the background worker.

        Args:
            text: The Unicode text to speak.
            on_complete: An optional callback invoked with this item's
                :class:`SpeechResult` once it has been spoken.

        Raises:
            TextToSpeechError: If the manager is not initialized.
        """
        with self._lock:
            self._ensure_initialized()
        self._queue.put((text, on_complete))
        logger.debug("Enqueued text for asynchronous speech (%d characters).", len(text))

    def stop(self, *, clear_queue: bool = True) -> None:
        """Interrupt any speech in progress, and optionally clear the pending queue.

        Args:
            clear_queue: If ``True`` (the default), also discard every
                pending item in the asynchronous speech queue.
        """
        self._interrupted.set()
        if clear_queue:
            drained_count = 0
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
                drained_count += 1
            if drained_count:
                logger.info("Cleared %d pending item(s) from the speech queue.", drained_count)

        with self._lock:
            engine = self._engine
        if engine is not None:
            engine.stop()
            logger.info("Speech interrupted.")

    def is_speaking(self) -> bool:
        """Check whether the engine is currently speaking.

        Returns:
            ``True`` if a speech attempt is currently in progress.
        """
        return self._speaking_event.is_set()

    def pending_queue_size(self) -> int:
        """Return the number of items waiting in the asynchronous speech queue.

        Returns:
            The number of pending items.
        """
        return self._queue.qsize()

    def switch_engine(self, name: str) -> None:
        """Switch the active engine at runtime.

        If the manager is currently initialized, it is fully shut down
        and reinitialized with the new engine.

        Args:
            name: The name of the engine to switch to.

        Raises:
            EngineNotFoundError: If no engine is registered under
                ``name``.
            TextToSpeechError: If the new engine fails to initialize.
        """
        with self._lock:
            if not self._factory.engine_exists(name):
                raise EngineNotFoundError(
                    f"No text-to-speech engine is registered under '{name}'."
                )

            was_initialized = self._initialized
            if was_initialized:
                self.shutdown()

            previous_engine_name = self._active_engine_name
            self._active_engine_name = name
            logger.info(
                "Active text-to-speech engine switched from '%s' to '%s'.",
                previous_engine_name,
                name,
            )

            if was_initialized:
                self.initialize()

    def update_config(self, config: SpeechConfig) -> None:
        """Replace the active configuration and reapply it to the active engine.

        If the manager is currently initialized, the active engine is
        shut down and reinitialized with the new configuration, since
        engines such as ``pyttsx3`` apply configuration at
        initialization time.

        Args:
            config: The new configuration to use.
        """
        with self._lock:
            was_initialized = self._initialized
            if was_initialized:
                self.shutdown()

            self._config = config
            logger.info("Text-to-speech configuration updated.")

            if was_initialized:
                self.initialize()

    def register_engine(
        self, name: str, engine_cls: type[BaseTextToSpeech], *, overwrite: bool = False
    ) -> None:
        """Register a new engine with the underlying factory.

        Args:
            name: The unique name to register the engine under.
            engine_cls: The :class:`BaseTextToSpeech` subclass to
                register.
            overwrite: If ``True``, replace an existing registration
                under the same name.

        Raises:
            DuplicateEngineError: If ``name`` is already registered
                and ``overwrite`` is ``False``.
        """
        self._factory.register_engine(name, engine_cls, overwrite=overwrite)

    def list_available_engines(self) -> tuple[str, ...]:
        """List the names of every engine registered with the factory.

        Returns:
            A tuple of registered engine names.
        """
        return self._factory.list_engines()

    def list_available_voices(self) -> tuple[VoiceInfo, ...]:
        """List every voice available on the active engine.

        Returns:
            A tuple of available voices. Returns an empty tuple if the
            manager is not initialized.
        """
        with self._lock:
            if not self._initialized or self._engine is None:
                return ()
            engine = self._engine
        return engine.list_voices()

    def get_current_engine_name(self) -> str:
        """Return the name of the currently active engine.

        Returns:
            The active engine's name.
        """
        with self._lock:
            return self._active_engine_name

    def health_check(self) -> bool:
        """Check whether the active engine is currently healthy.

        Returns:
            ``True`` if the manager is initialized and the active
            engine reports healthy, ``False`` otherwise.
        """
        with self._lock:
            if not self._initialized or self._engine is None:
                return False
            engine = self._engine
        return engine.health_check()

    def _run_worker_loop(self) -> None:
        """Continuously process the asynchronous speech queue until stopped.

        Each queued item is spoken via the active engine, and its
        result is delivered to that item's callback, if one was
        provided. A failure in one item is logged and does not stop
        the worker from processing subsequent items.
        """
        while not self._worker_stop_event.is_set():
            try:
                text, on_complete = self._queue.get(timeout=_QUEUE_POLL_INTERVAL_SECONDS)
            except queue.Empty:
                continue

            self._interrupted.clear()
            with self._lock:
                engine = self._engine

            self._speaking_event.set()
            import voice.text_to_speech
            voice.text_to_speech.is_speaking = True

            # Stop microphone recording completely BEFORE TTS audio begins
            try:
                from core.registry import registry
                if registry.exists("stt_manager"):
                    stt = registry.get("stt_manager")
                    if hasattr(stt, "recognizer") and hasattr(stt.recognizer, "_mic_stream") and stt.recognizer._mic_stream:
                        stt.recognizer._mic_stream.pause_recording()
            except Exception as e:
                logger.warning("Failed to pause microphone before speaking: %s", e)

            # Publish speaking started event to central bus
            try:
                from core.event_bus import NovaEvent
                from core.registry import registry
                if registry.exists("event_bus"):
                    registry.get("event_bus").publish(NovaEvent.SPEAKING_STARTED, text=text)
            except Exception as e:
                logger.warning("Failed to publish SPEAKING_STARTED: %s", e)

            try:
                if engine is None:
                    result = SpeechResult.failure_result(
                        status=SpeechStatus.ENGINE_UNAVAILABLE,
                        duration_seconds=0.0,
                        engine_name=self._active_engine_name,
                        error_message="No active engine is available.",
                    )
                else:
                    start_time = time.monotonic()
                    if self._interrupted.is_set():
                        result = SpeechResult.failure_result(
                            status=SpeechStatus.CANCELLED,
                            duration_seconds=0.0,
                            engine_name=self._active_engine_name,
                            voice_id=self._config.voice_id,
                            error_message="Interrupted by user."
                        )
                    else:
                        res = engine.speak(text)
                        duration = time.monotonic() - start_time
                        if self._interrupted.is_set():
                            result = SpeechResult.failure_result(
                                status=SpeechStatus.CANCELLED,
                                duration_seconds=duration,
                                engine_name=self._active_engine_name,
                                voice_id=self._config.voice_id,
                                error_message="Interrupted by user."
                            )
                        elif res.status == SpeechStatus.SUCCESS:
                            result = SpeechResult.success_result(
                                duration_seconds=duration,
                                engine_name=self._active_engine_name,
                                voice_id=self._config.voice_id,
                            )
                        else:
                            result = SpeechResult.failure_result(
                                status=res.status,
                                duration_seconds=duration,
                                engine_name=self._active_engine_name,
                                voice_id=self._config.voice_id,
                                error_message=res.error_message,
                            )
            finally:
                self._speaking_event.clear()
                voice.text_to_speech.is_speaking = False

                # Publish speaking finished event to central bus
                try:
                    from core.event_bus import NovaEvent
                    from core.registry import registry
                    if registry.exists("event_bus"):
                        success_val = (result.status == SpeechStatus.SUCCESS) if 'result' in locals() else True
                        registry.get("event_bus").publish(NovaEvent.SPEAKING_FINISHED, success=success_val)
                except Exception as e:
                    logger.warning("Failed to publish SPEAKING_FINISHED: %s", e)

                # Re-enable the microphone ONLY after TTS confirms playback has fully finished and safety delay is complete
                try:
                    from core.registry import registry
                    if registry.exists("stt_manager"):
                        stt = registry.get("stt_manager")
                        if hasattr(stt, "recognizer") and hasattr(stt.recognizer, "_mic_stream") and stt.recognizer._mic_stream:
                            # 300 ms safety delay as requested (200-500 ms)
                            time.sleep(0.3)
                            stt.recognizer._mic_stream.resume_recording()
                except Exception as e:
                    logger.warning("Failed to resume microphone after speaking: %s", e)

                self._queue.task_done()

            if on_complete is not None:
                try:
                    on_complete(result)
                except Exception as exc:  # noqa: BLE001 - a bad callback must not end the loop
                    logger.error(
                        "on_complete callback raised an exception: %s", exc, exc_info=True
                    )

    def _ensure_initialized(self) -> None:
        """Verify the manager is initialized before permitting an operation.

        Raises:
            TextToSpeechError: If :meth:`initialize` has not been
                called successfully.
        """
        if not self._initialized or self._engine is None:
            raise TextToSpeechError(
                "TextToSpeechManager is not initialized. Call initialize() first."
            )


__all__ = [
    "TextToSpeechManager",
    "SpeechEngineFactory",
    "BaseTextToSpeech",
    "Pyttsx3Engine",
    "EdgeTTSEngine",
    "SpeechConfig",
    "SpeechResult",
    "SpeechStatus",
    "VoiceGender",
    "VoiceEngine",
    "VoiceInfo",
    "OnSpeechCompleteCallback",
    "EngineUnavailableError",
    "VoiceUnavailableError",
    "EngineNotFoundError",
    "DuplicateEngineError",
]
