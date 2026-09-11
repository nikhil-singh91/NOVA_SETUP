"""Unified Voice Manager coordinating listening, transcription, and speech for NOVA Voice V2."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

import numpy as np

from config.settings import settings
from core.event_bus import NovaEvent
from core.logger import get_logger
from core.registry import registry
from voice.listener import VoiceListener
from voice.microphone import MicrophoneManager
from voice.preprocessing import AudioPreprocessor
from voice.quality import TranscriptQualityGate
from voice.speaker import SpeakerManager
from voice.state import SpeechOutputResult, TranscriptionResult, VoiceState
from voice.transcriber import TranscriptionManager
from voice.vad import VoiceActivityDetector

logger = get_logger(__name__)


class VoiceManager:
    """Central orchestrator for NOVA Voice V2.

    Coordinates microphone capture, voice activity detection (VAD),
    speech transcription, text-to-speech playback, and state synchronization.
    """

    def __init__(self) -> None:
        self.sample_rate = settings.stt_sample_rate or 16000
        self.device_index = settings.stt_device_index

        # Components
        self.microphone = MicrophoneManager(
            sample_rate=self.sample_rate,
            device_index=self.device_index,
        )
        self.vad = VoiceActivityDetector(
            sample_rate=self.sample_rate,
            silence_duration_s=settings.stt_silence_duration_seconds,
            min_speech_duration_s=settings.stt_min_speech_duration_seconds,
            max_speech_duration_s=settings.stt_max_speech_duration_seconds,
        )
        self.transcriber = TranscriptionManager(
            primary_engine=settings.stt_engine or "faster_whisper",
            model_size=settings.whisper_model_name or "base",
            language=settings.stt_language or "auto",
        )
        self.quality_gate = TranscriptQualityGate()
        self.speaker = SpeakerManager(
            voice=settings.tts_voice,
            rate=settings.tts_rate,
            volume=settings.tts_volume,
            primary_engine=settings.tts_engine,
        )

        self._state = VoiceState.IDLE
        self._state_lock = threading.RLock()
        self._listener: VoiceListener | None = None
        self._on_text_callback: Callable[[TranscriptionResult], None] | None = None
        self._is_initialized = False

    @property
    def state(self) -> VoiceState:
        """Return the current VoiceState."""
        with self._state_lock:
            return self._state

    def set_state(self, new_state: VoiceState, **details: Any) -> None:
        """Transition to a new VoiceState and notify the EventBus."""
        with self._state_lock:
            old_state = self._state
            if old_state == new_state:
                return
            self._state = new_state
            logger.info("VoiceState changed: %s -> %s", old_state.value, new_state.value)

        # Notify EventBus
        try:
            if registry.exists("event_bus"):
                bus = registry.get("event_bus")
                bus.publish(
                    NovaEvent.STATE_CHANGED,
                    old_state=old_state.value,
                    new_state=new_state.value,
                    **details,
                )
        except Exception as exc:
            logger.debug("Failed to publish STATE_CHANGED on EventBus: %s", exc)

    def initialize(self) -> None:
        """Initialize all voice subcomponents."""
        if self._is_initialized:
            return

        logger.info("Initializing NOVA Voice V2 manager...")

        # 1. Initialize Microphone
        self.microphone.initialize()

        # 2. Initialize Speaker
        self.speaker.initialize()

        # 3. Initialize Transcriber
        self.transcriber.initialize()

        # 4. Construct Listener
        self._listener = VoiceListener(
            microphone=self.microphone,
            vad=self.vad,
            on_speech_finalized=self._handle_finalized_speech,
            get_voice_state=lambda: self.state,
        )

        self._is_initialized = True
        self.set_state(VoiceState.IDLE)
        logger.info("NOVA Voice V2 initialized successfully.")

    def start_listening(self, on_text: Callable[[TranscriptionResult], None]) -> None:
        """Start continuous speech listening in the background."""
        if not self._is_initialized:
            self.initialize()

        self._on_text_callback = on_text

        assert self._listener is not None
        self._listener.start()
        self.set_state(VoiceState.LISTENING)

        try:
            if registry.exists("event_bus"):
                registry.get("event_bus").publish(NovaEvent.LISTENING_STARTED)
        except Exception:
            pass

        logger.info("Voice V2 continuous listening started.")

    def stop_listening(self) -> None:
        """Pause continuous listening."""
        if self._listener is not None:
            self._listener.stop()
        self.set_state(VoiceState.IDLE)
        logger.info("Voice V2 continuous listening stopped.")

    def _handle_finalized_speech(self, audio: np.ndarray) -> None:
        """Internal callback invoked by VoiceListener when user stops speaking."""
        # 1. Transition to PROCESSING state
        self.set_state(VoiceState.PROCESSING)

        # Calculate audio diagnostics
        audio_dur = len(audio) / self.sample_rate if self.sample_rate else 0.0
        rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) > 0 else 0.0

        # Preprocess audio (DC offset removal, 80Hz rumble filter, soft peak normalization)
        preprocessed_audio = AudioPreprocessor.preprocess_finalized_audio(audio, sample_rate=self.sample_rate)

        # 2. Transcribe finalized audio
        transcription = self.transcriber.transcribe(preprocessed_audio, sample_rate=self.sample_rate)

        # Non-speech audio event detection (cough, sneeze, laughter, sigh)
        from voice.audio_events import AudioEventDetector, AudioEventType
        event_res = AudioEventDetector.analyze(transcription.text, preprocessed_audio, sample_rate=self.sample_rate)
        transcription.audio_event = event_res.event_type.value
        transcription.is_isolated_audio_event = event_res.is_isolated_event
        if event_res.clean_text:
            transcription.text = event_res.clean_text

        # 3. Evaluate transcript through centralized TranscriptQualityGate
        quality = self.quality_gate.evaluate(transcription)
        if not quality.accepted and event_res.is_isolated_event and event_res.event_type in (
            AudioEventType.COUGH,
            AudioEventType.SNEEZE,
            AudioEventType.LAUGHTER,
            AudioEventType.SIGH,
            AudioEventType.THROAT_CLEAR,
        ):
            from voice.state import QualityCheckResult, QualityDecision
            quality = QualityCheckResult(
                accepted=True,
                decision=QualityDecision.ACCEPTED,
                confidence=0.9,
                transcript=transcription.text or f"[{event_res.event_type.value}]",
                reason=f"Isolated non-speech event: {event_res.event_type.value}",
                is_command_candidate=False,
            )
        transcription.quality = quality

        try:
            from ui.health_checker import DashboardStatsManager
            conf = transcription.confidence
            if conf is not None and conf > 0.0:
                DashboardStatsManager.update("speech_confidence", f"{conf * 100:.0f}%")
            else:
                DashboardStatsManager.update("speech_confidence", "UNKNOWN")
        except Exception:
            pass

        action_name = "DISPATCH_TO_TURN_PIPELINE" if quality.accepted else "DISCARD_NON_SPEECH"

        logger.info(
            "\n====================================================\n"
            "🎤 NOVA VOICE PIPELINE AUDIT\n"
            "AUDIO DURATION:       %.2fs (RMS: %.4f)\n"
            "VAD RESULT:           SPEECH_FINALIZED (%d samples)\n"
            "STT ENGINE:           %s\n"
            "RAW TRANSCRIPT:       \"%s\"\n"
            "ACOUSTIC METRICS:     conf=%.2f, no_speech_prob=%.2f, avg_logprob=%.2f, comp_ratio=%.2f\n"
            "TRANSCRIPT GATE:      decision=%s, accepted=%s\n"
            "GATE REASON:          %s\n"
            "PIPELINE ACTION:      %s\n"
            "====================================================",
            audio_dur,
            rms,
            len(audio),
            transcription.provider_name,
            transcription.text,
            transcription.confidence,
            transcription.no_speech_prob,
            transcription.avg_logprob,
            transcription.compression_ratio,
            quality.decision.value,
            quality.accepted,
            quality.reason,
            action_name,
        )

        # 4. If speech quality is acceptable, pass to application turn pipeline
        if quality.accepted and self._on_text_callback is not None:
            try:
                self._on_text_callback(transcription)
            except Exception as exc:
                logger.error("Error passing transcription to turn callback: %s", exc, exc_info=True)
                self.set_state(VoiceState.LISTENING)
        else:
            # Silence, cough, noise, or hallucination -> return directly to LISTENING
            logger.debug("Voice input discarded by quality gate: %s", quality.reason)
            self.set_state(VoiceState.LISTENING)


    def speak(self, text: str) -> SpeechOutputResult:
        """Speak text synchronously."""
        if not self._is_initialized:
            self.initialize()

        self.set_state(VoiceState.SPEAKING, text=text)
        try:
            if registry.exists("event_bus"):
                registry.get("event_bus").publish(NovaEvent.SPEAKING_STARTED, text=text)
        except Exception:
            pass

        result = self.speaker.speak(text)

        try:
            if registry.exists("event_bus"):
                registry.get("event_bus").publish(NovaEvent.SPEAKING_FINISHED, success=result.success)
        except Exception:
            pass

        # Return to LISTENING if listener is active, else IDLE
        if self._listener is not None and self._listener.is_active():
            self.set_state(VoiceState.LISTENING)
        else:
            self.set_state(VoiceState.IDLE)

        return result

    def speak_async(
        self,
        text: str,
        on_complete: Callable[[SpeechOutputResult], None] | None = None,
    ) -> None:
        """Speak text asynchronously without blocking."""
        if not self._is_initialized:
            self.initialize()

        self.set_state(VoiceState.SPEAKING, text=text)
        try:
            if registry.exists("event_bus"):
                registry.get("event_bus").publish(NovaEvent.SPEAKING_STARTED, text=text)
        except Exception:
            pass

        def _wrapped_on_complete(result: SpeechOutputResult) -> None:
            try:
                if registry.exists("event_bus"):
                    registry.get("event_bus").publish(NovaEvent.SPEAKING_FINISHED, success=result.success)
            except Exception:
                pass

            if self._listener is not None and self._listener.is_active():
                self.set_state(VoiceState.LISTENING)
            else:
                self.set_state(VoiceState.IDLE)

            if on_complete is not None:
                on_complete(result)

        self.speaker.speak_async(text, on_complete=_wrapped_on_complete)

    def stop_speaking(self) -> None:
        """Stop any active speech playback immediately."""
        self.speaker.stop()
        if self._listener is not None and self._listener.is_active():
            self.set_state(VoiceState.LISTENING)
        else:
            self.set_state(VoiceState.IDLE)

    def health_check(self) -> bool:
        """Return True if all voice subsystems are operational."""
        return self._is_initialized and self.microphone is not None and self.speaker is not None

    def shutdown(self) -> None:
        """Cleanly tear down all voice subsystems."""
        self.stop_listening()
        self.speaker.shutdown()
        self.transcriber.shutdown()
        self.microphone.shutdown()
        self._is_initialized = False
        self.set_state(VoiceState.IDLE)
        logger.info("VoiceManager shut down.")
