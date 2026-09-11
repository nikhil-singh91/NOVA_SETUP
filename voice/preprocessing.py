"""Audio preprocessing pipeline for clean acoustic signal conditioning in NOVA Voice V2."""

from __future__ import annotations

import numpy as np


class AudioPreprocessor:
    """Preprocesses raw float32 microphone audio to improve speech recognition quality.

    Features:
        - DC Offset Removal: Centers the signal around 0.0 to eliminate microphone bias.
        - High-Pass Filter (approx. 80Hz cutoff): Attenuates low-frequency desk rumble and handling noise.
        - Soft Peak Normalization / AGC: Standardizes speech volume while avoiding clipping or boosting pure silence.
    """

    @staticmethod
    def remove_dc_offset(audio: np.ndarray) -> np.ndarray:
        """Subtract the mean from the audio buffer to eliminate DC bias, preserving non-zero variance."""
        if len(audio) == 0:
            return audio
        mean = float(np.mean(audio))
        std = float(np.std(audio))
        # If signal has AC variation (std > 1e-4) and non-zero mean, subtract DC bias
        if std > 1e-4 and abs(mean) > 1e-4:
            return audio - mean
        return audio

    @staticmethod
    def high_pass_filter(audio: np.ndarray, sample_rate: int = 16000, cutoff_hz: float = 80.0) -> np.ndarray:
        """First-order IIR high-pass filter to eliminate sub-audible room rumble."""
        if len(audio) < 2:
            return audio

        dt = 1.0 / sample_rate
        rc = 1.0 / (2.0 * np.pi * cutoff_hz)
        alpha = rc / (rc + dt)

        filtered = np.empty_like(audio)
        filtered[0] = audio[0]
        for i in range(1, len(audio)):
            filtered[i] = alpha * (filtered[i - 1] + audio[i] - audio[i - 1])

        return filtered

    @staticmethod
    def normalize_peak(audio: np.ndarray, target_peak: float = 0.85, noise_gate_rms: float = 0.005) -> np.ndarray:
        """Normalize audio volume if speech energy is present, preventing clipping."""
        if len(audio) == 0:
            return audio

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < noise_gate_rms:
            # Pure silence or very low background noise; do not boost noise
            return audio

        peak = float(np.max(np.abs(audio)))
        if peak > 1e-5:
            # Apply soft scaling towards target peak without exceeding 1.0
            scale = min(target_peak / peak, 3.5)
            normalized = audio * scale
            return np.clip(normalized, -1.0, 1.0)
        return audio

    @classmethod
    def preprocess_finalized_audio(cls, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """Complete audio preprocessing pipeline applied before passing audio to ASR."""
        if len(audio) == 0:
            return audio

        # 1. Remove DC bias
        clean = cls.remove_dc_offset(audio)

        # 2. Filter low-frequency rumble
        clean = cls.high_pass_filter(clean, sample_rate=sample_rate, cutoff_hz=80.0)

        # 3. Soft peak normalization
        clean = cls.normalize_peak(clean, target_peak=0.85)

        return clean.astype(np.float32)
