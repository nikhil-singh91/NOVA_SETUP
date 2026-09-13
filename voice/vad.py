"""Voice Activity Detection (VAD) with adaptive noise tracking and natural pause tolerance."""

from __future__ import annotations

import collections
import time
from typing import Any

import numpy as np
from core.logger import get_logger

from voice.state import VADState

logger = get_logger(__name__)


class VoiceActivityDetector:
    """Detects start, continuation, and conclusion of human speech.

    Features:
        - Adaptive noise floor estimation over non-speech frames.
        - Pre-roll ring buffer preserving audio before speech detection.
        - Hangover tolerance allowing natural conversational pauses.
        - Minimum duration filter to reject transient pops, breaths, or keyboard clicks.
        - Maximum recording time limit to prevent runaway memory usage.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 512,
        silence_duration_s: float = 1.1,
        min_speech_duration_s: float = 0.30,
        max_speech_duration_s: float = 20.0,
        energy_threshold_multiplier: float = 2.5,
        base_energy_threshold: float = 0.012,
        preroll_duration_s: float = 0.6,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.silence_duration_s = silence_duration_s
        self.min_speech_duration_s = min_speech_duration_s
        self.max_speech_duration_s = max_speech_duration_s
        self.energy_threshold_multiplier = energy_threshold_multiplier
        self.base_energy_threshold = base_energy_threshold

        self.chunk_duration_s = self.chunk_size / self.sample_rate

        # Pre-roll ring buffer
        preroll_chunks = max(3, int(preroll_duration_s / self.chunk_duration_s))
        self._preroll_buffer: collections.deque[np.ndarray] = collections.deque(maxlen=preroll_chunks)

        # Internal state
        self._state = VADState.SILENCE
        self._speech_buffer: list[np.ndarray] = []
        self._noise_floor: float = base_energy_threshold
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0

        # Calibration frames
        self._calibration_count = 0
        self._is_calibrated = False

    @property
    def state(self) -> VADState:
        """Return the current VAD state."""
        return self._state

    @property
    def current_threshold(self) -> float:
        """Return the effective energy threshold for speech detection."""
        return max(self.base_energy_threshold, self._noise_floor * self.energy_threshold_multiplier)

    def reset(self) -> None:
        """Reset internal speech accumulation buffers and return to SILENCE state."""
        self._state = VADState.SILENCE
        self._speech_buffer.clear()
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0

    def process_chunk(self, chunk: np.ndarray) -> tuple[VADState, np.ndarray | None]:
        """Process an incoming float32 audio chunk.

        Args:
            chunk: Float32 normalized audio array.

        Returns:
            Tuple of (current VADState, finalized audio array if SPEECH_FINALIZED else None).
        """
        now = time.monotonic()
        rms = float(np.sqrt(np.mean(chunk ** 2))) + 1e-6

        # Adaptive noise floor tracking (exponential moving average when quiet)
        if self._state == VADState.SILENCE:
            if rms < self.current_threshold * 1.2:
                # Update noise floor slowly
                alpha = 0.05
                self._noise_floor = (1.0 - alpha) * self._noise_floor + alpha * rms
                self._calibration_count += 1
                if self._calibration_count > 15:
                    self._is_calibrated = True

        threshold = self.current_threshold
        is_speech_frame = rms > threshold

        # Always append to pre-roll ring buffer
        self._preroll_buffer.append(chunk)

        if self._state == VADState.SILENCE:
            if is_speech_frame:
                self._consecutive_speech_frames += 1
                # Require 2 consecutive frames (~64ms) to trigger speech onset
                if self._consecutive_speech_frames >= 2:
                    self._state = VADState.SPEECH_START
                    self._speech_start_time = now
                    self._last_speech_time = now
                    self._consecutive_silence_frames = 0
                    # Seed speech buffer with the pre-roll history
                    self._speech_buffer = list(self._preroll_buffer)
                    logger.debug("VAD: Speech onset detected (RMS=%.4f, threshold=%.4f).", rms, threshold)
                    return (VADState.SPEECH_START, None)
            else:
                self._consecutive_speech_frames = 0
            return (VADState.SILENCE, None)

        elif self._state in (VADState.SPEECH_START, VADState.IN_SPEECH):
            self._state = VADState.IN_SPEECH
            self._speech_buffer.append(chunk)

            if is_speech_frame:
                self._last_speech_time = now
                self._consecutive_silence_frames = 0
            else:
                self._consecutive_silence_frames += 1

            speech_duration = max(now - self._speech_start_time, len(self._speech_buffer) * self.chunk_duration_s)
            silence_duration = max(now - self._last_speech_time, self._consecutive_silence_frames * self.chunk_duration_s)

            # Condition 1: Max recording duration reached -> force finalize
            if speech_duration >= self.max_speech_duration_s:
                logger.info("VAD: Max recording duration reached (%.1fs). Finalizing.", speech_duration)
                final_audio = self._finalize_audio()
                return (VADState.SPEECH_FINALIZED, final_audio)

            # Condition 2: Silence duration exceeds hangover threshold -> finalize
            if silence_duration >= self.silence_duration_s:
                # Check if overall speech was long enough
                effective_speech_duration = speech_duration - silence_duration
                if effective_speech_duration >= self.min_speech_duration_s or speech_duration >= self.min_speech_duration_s:
                    logger.debug(
                        "VAD: Speech completed naturally (speech=%.2fs, silence=%.2fs).",
                        effective_speech_duration,
                        silence_duration,
                    )
                    final_audio = self._finalize_audio()
                    return (VADState.SPEECH_FINALIZED, final_audio)
                else:
                    # Too short: likely a mic click or breath
                    logger.debug(
                        "VAD: Speech segment rejected as too short (%.2fs < %.2fs).",
                        effective_speech_duration,
                        self.min_speech_duration_s,
                    )
                    self.reset()
                    return (VADState.SILENCE, None)

            return (VADState.IN_SPEECH, None)

        return (self._state, None)

    def _finalize_audio(self) -> np.ndarray:
        """Concatenate buffered chunks into a single float32 array and reset."""
        if not self._speech_buffer:
            self.reset()
            return np.array([], dtype=np.float32)

        final_audio = np.concatenate(self._speech_buffer, axis=0)
        self.reset()
        return final_audio

    def get_metrics(self) -> dict[str, Any]:
        """Return diagnostic metrics."""
        return {
            "state": self._state.value,
            "noise_floor": self._noise_floor,
            "threshold": self.current_threshold,
            "is_calibrated": self._is_calibrated,
            "buffer_chunks": len(self._speech_buffer),
        }
