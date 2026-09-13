"""Non-speech audio event detection and conversational handling for NOVA Voice V2.

Detects acoustic and transcript non-speech events:
- Speech
- Cough / throat clearing
- Sneeze
- Laughter / chuckles / giggles
- Sighs
- Silence / background noise
- Unknown
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

import numpy as np


class AudioEventType(str, Enum):
    """Categorical classification of non-speech acoustic and vocal cues."""

    NONE = "none"
    SPEECH = "speech"
    COUGH = "cough"
    SNEEZE = "sneeze"
    LAUGHTER = "laughter"
    SIGH = "sigh"
    THROAT_CLEAR = "throat_clear"
    BACKGROUND_NOISE = "background_noise"
    SILENCE = "silence"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AudioEventResult:
    """Outcome of audio event analysis on user utterance."""

    event_type: AudioEventType
    clean_text: str
    is_isolated_event: bool
    confidence: float = 0.9
    details: str = ""


# Regex patterns matching non-speech annotations from Whisper or transcripts
_COUGH_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:cough|coughs|coughing|hack|hacks|hacking)\s*(?:\]|\)|\*)|\b(?:coughs?|coughing)\b(?=[\s,\.\!\?]*$)",
    re.IGNORECASE,
)
_THROAT_CLEAR_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:clears?\s*throat|throat\s*clearing|ahem|harrumph)\s*(?:\]|\)|\*)|\b(?:ahem|throat\s*clearing)\b",
    re.IGNORECASE,
)
_SNEEZE_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:sneeze|sneezes|sneezing|achoo)\s*(?:\]|\)|\*)|\b(?:achoo|sneezes?)\b(?=[\s,\.\!\?]*$)",
    re.IGNORECASE,
)
_LAUGHTER_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:laughter|laugh|laughs|laughing|chuckle|chuckles|giggle|giggles|snicker|cackle|haha|hehe)\s*(?:\]|\)|\*)|\b(?:haha+|hehe+|lol)\b",
    re.IGNORECASE,
)
_SIGH_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:sigh|sighs|sighing|deep\s*breath|gasp|heavy\s*sigh)\s*(?:\]|\)|\*)|\b(?:sighs?)\b(?=[\s,\.\!\?]*$)",
    re.IGNORECASE,
)


class AudioEventDetector:
    """Detects and isolates non-speech acoustic events from transcript and audio buffer."""

    @classmethod
    def analyze(
        cls,
        text: str,
        audio: np.ndarray | None = None,
        sample_rate: int = 16000,
    ) -> AudioEventResult:
        """Analyze text transcript and optional audio for non-speech events.

        Returns clean speech text (with event markers stripped) and detected event.
        """
        raw_trimmed = text.strip() if text else ""
        detected_type = AudioEventType.NONE
        clean_text = raw_trimmed

        # 1. If text transcript is available, parse explicit cues
        if raw_trimmed:
            if _COUGH_PATTERN.search(clean_text) or any(
                w in clean_text.lower().split() for w in ["*cough*", "[cough]", "(cough)"]
            ):
                detected_type = AudioEventType.COUGH
                clean_text = _COUGH_PATTERN.sub("", clean_text).strip()

            elif _THROAT_CLEAR_PATTERN.search(clean_text) or any(
                w in clean_text.lower().split() for w in ["*clears throat*", "[throat clearing]", "(throat clearing)"]
            ):
                detected_type = AudioEventType.THROAT_CLEAR
                clean_text = _THROAT_CLEAR_PATTERN.sub("", clean_text).strip()

            elif _SNEEZE_PATTERN.search(clean_text):
                detected_type = AudioEventType.SNEEZE
                clean_text = _SNEEZE_PATTERN.sub("", clean_text).strip()

            elif _LAUGHTER_PATTERN.search(clean_text):
                detected_type = AudioEventType.LAUGHTER
                clean_text = _LAUGHTER_PATTERN.sub("", clean_text).strip()

            elif _SIGH_PATTERN.search(clean_text):
                detected_type = AudioEventType.SIGH
                clean_text = _SIGH_PATTERN.sub("", clean_text).strip()

            # Clean trailing / leading punctuation remnants after tag removal
            clean_text = re.sub(r"\s+", " ", clean_text).strip()
            clean_text = re.sub(r"^[,\-\.\s]+|[,\-\.\s]+$", "", clean_text).strip()

        # Check meaningful residual words excluding wake words & greetings
        residual_words = [
            w for w in re.sub(r"[^\w\s]", "", clean_text.lower()).split()
            if w not in ("nova", "hey", "hi", "ok", "okay")
        ]
        is_isolated = (detected_type != AudioEventType.NONE) and (len(residual_words) == 0)

        # If isolated event detected from text, clean_text should be empty
        if is_isolated:
            clean_text = ""

        # 2. Acoustic signal analysis on raw audio buffer if no textual cue or to verify tail
        if audio is not None and len(audio) > 0:
            if detected_type == AudioEventType.NONE:
                if len(residual_words) == 0:
                    # Pure non-verbal audio (or only wake word)
                    acoustic_event = cls._detect_acoustic_event(audio, sample_rate)
                    if acoustic_event in (
                        AudioEventType.COUGH,
                        AudioEventType.SNEEZE,
                        AudioEventType.LAUGHTER,
                        AudioEventType.SIGH,
                        AudioEventType.THROAT_CLEAR,
                    ):
                        detected_type = acoustic_event
                        is_isolated = True
                        clean_text = ""
                    elif acoustic_event in (AudioEventType.SILENCE, AudioEventType.BACKGROUND_NOISE):
                        detected_type = acoustic_event
                        is_isolated = False
                else:
                    # User spoke words! Check if audio tail contains an event (e.g. speech + cough at the end)
                    tail_dur = min(1.0, len(audio) / sample_rate)
                    tail_samples = int(tail_dur * sample_rate)
                    tail_audio = audio[-tail_samples:]
                    tail_event = cls._detect_acoustic_event(tail_audio, sample_rate)
                    if tail_event in (
                        AudioEventType.COUGH,
                        AudioEventType.SNEEZE,
                        AudioEventType.LAUGHTER,
                        AudioEventType.SIGH,
                        AudioEventType.THROAT_CLEAR,
                    ):
                        detected_type = tail_event
                        is_isolated = False

        conf = 0.92 if detected_type not in (AudioEventType.NONE, AudioEventType.SILENCE) else 1.0
        return AudioEventResult(
            event_type=detected_type,
            clean_text=clean_text,
            is_isolated_event=is_isolated,
            confidence=conf,
            details=f"Detected {detected_type.value} (isolated={is_isolated})",
        )

    @classmethod
    def _detect_acoustic_event(cls, audio: np.ndarray, sample_rate: int) -> AudioEventType:
        """Evaluate acoustic characteristics for human vocal cues and audio events."""
        if len(audio) == 0:
            return AudioEventType.SILENCE

        dur = len(audio) / sample_rate
        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))

        # Pure silence
        if rms < 0.002 or peak < 0.005:
            return AudioEventType.SILENCE

        crest_factor = peak / rms if rms > 1e-6 else 0.0
        zcr = float(np.mean(np.abs(np.diff(np.sign(audio)))) / 2)

        # Low-level steady background noise
        if rms < 0.008 and crest_factor < 2.0 and dur > 0.4:
            return AudioEventType.BACKGROUND_NOISE

        # 1. Laughter: Syllabic rhythmic modulation (3.5 - 7.5 Hz envelope peaks)
        if dur >= 0.45:
            laughter_detected = cls._detect_rhythmic_laughter(audio, sample_rate)
            if laughter_detected:
                return AudioEventType.LAUGHTER

        # 2. Sneeze: Violent explosive transient + high-frequency turbulent friction
        if 0.12 <= dur <= 0.50 and crest_factor > 5.5 and zcr > 0.28 and rms > 0.025:
            return AudioEventType.SNEEZE

        # 3. Cough: Sharp acoustic burst with high crest factor
        if 0.12 <= dur <= 0.70 and crest_factor > 4.2 and 0.10 <= zcr <= 0.60 and rms > 0.025:
            return AudioEventType.COUGH

        # 4. Throat Clear: Moderate raspy friction burst
        if 0.20 <= dur <= 1.2 and 2.8 <= crest_factor <= 5.0 and 0.15 <= zcr <= 0.55 and 0.012 <= rms <= 0.18:
            return AudioEventType.THROAT_CLEAR

        # 5. Sigh: Soft prolonged exhalation with smooth decay
        if dur >= 0.50 and 0.004 <= rms <= 0.06:
            half = len(audio) // 2
            rms_first = float(np.sqrt(np.mean(audio[:half]**2)))
            rms_second = float(np.sqrt(np.mean(audio[half:]**2)))
            if rms_second > 1e-6 and (rms_first / rms_second) >= 1.4:
                return AudioEventType.SIGH

        return AudioEventType.NONE

    @staticmethod
    def _detect_rhythmic_laughter(audio: np.ndarray, sample_rate: int) -> bool:
        """Detect rhythmic syllabic bursts characteristic of laughter (3.5 - 7.5 Hz)."""
        frame_len = int(sample_rate * 0.04)  # 40ms frame
        hop_len = int(sample_rate * 0.02)    # 20ms hop
        if len(audio) < frame_len * 4:
            return False

        num_frames = (len(audio) - frame_len) // hop_len + 1
        if num_frames < 10:
            return False

        frame_energies = np.array([
            float(np.sqrt(np.mean(audio[i * hop_len : i * hop_len + frame_len] ** 2)))
            for i in range(num_frames)
        ])
        mean_energy = float(np.mean(frame_energies))
        if mean_energy < 0.008:
            return False

        # Identify local energy peaks with minimum distance of 4 frames (~80ms)
        peak_indices: list[int] = []
        min_dist = 4
        for i in range(1, len(frame_energies) - 1):
            if frame_energies[i] >= frame_energies[i - 1] and frame_energies[i] >= frame_energies[i + 1]:
                if frame_energies[i] > 1.15 * mean_energy:
                    if not peak_indices or (i - peak_indices[-1]) >= min_dist:
                        peak_indices.append(i)

        if len(peak_indices) < 3:
            return False

        # Calculate time intervals between successive peaks
        intervals_s = [
            (peak_indices[k] - peak_indices[k - 1]) * (hop_len / sample_rate)
            for k in range(1, len(peak_indices))
        ]
        avg_interval = float(np.mean(intervals_s))
        std_interval = float(np.std(intervals_s))

        # Laughter bursts typically occur every 110ms to 320ms (~3.1 to 9 Hz) with rhythmic spacing
        if 0.11 <= avg_interval <= 0.32 and std_interval < 0.14:
            return True

        return False
