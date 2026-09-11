"""Non-speech audio event detection and conversational handling for NOVA Voice V2.

Detects acoustic and transcript non-speech events:
- Cough / throat clearing
- Sneeze
- Laughter / giggles
- Sighs
- Silence / background noise
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


class AudioEventType(str, Enum):
    """Categorical classification of non-speech acoustic events."""

    NONE = "none"
    COUGH = "cough"
    SNEEZE = "sneeze"
    LAUGHTER = "laughter"
    SIGH = "sigh"
    THROAT_CLEAR = "throat_clear"


@dataclass(frozen=True)
class AudioEventResult:
    """Outcome of audio event analysis on user utterance."""

    event_type: AudioEventType
    clean_text: str
    is_isolated_event: bool
    confidence: float = 0.9
    details: str = ""


# Regex patterns matching non-speech annotations from Whisper or audio preprocessing
_COUGH_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:cough|coughs|coughing|clears?\s*throat|throat\s*clearing)\s*(?:\]|\)|\*)",
    re.IGNORECASE,
)
_SNEEZE_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:sneeze|sneezes|sneezing)\s*(?:\]|\)|\*)",
    re.IGNORECASE,
)
_LAUGHTER_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:laughter|laugh|laughs|laughing|chuckle|chuckles|giggle|giggles|haha|hehe)\s*(?:\]|\)|\*)",
    re.IGNORECASE,
)
_SIGH_PATTERN = re.compile(
    r"(?:\[|\(|\*)\s*(?:sigh|sighs|sighing|deep\s*breath|gasp)\s*(?:\]|\)|\*)",
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
        if not raw_trimmed:
            return AudioEventResult(
                event_type=AudioEventType.NONE,
                clean_text="",
                is_isolated_event=False,
            )

        detected_type = AudioEventType.NONE
        clean_text = raw_trimmed

        # 1. Check Cough / Throat Clearing
        if _COUGH_PATTERN.search(clean_text) or any(
            w in clean_text.lower().split() for w in ["*cough*", "[cough]", "(cough)", "*clears throat*"]
        ):
            detected_type = AudioEventType.COUGH
            clean_text = _COUGH_PATTERN.sub("", clean_text).strip()

        # 2. Check Sneeze
        elif _SNEEZE_PATTERN.search(clean_text):
            detected_type = AudioEventType.SNEEZE
            clean_text = _SNEEZE_PATTERN.sub("", clean_text).strip()

        # 3. Check Laughter
        elif _LAUGHTER_PATTERN.search(clean_text):
            detected_type = AudioEventType.LAUGHTER
            clean_text = _LAUGHTER_PATTERN.sub("", clean_text).strip()

        # 4. Check Sigh
        elif _SIGH_PATTERN.search(clean_text):
            detected_type = AudioEventType.SIGH
            clean_text = _SIGH_PATTERN.sub("", clean_text).strip()

        # Clean trailing / leading punctuation remnants after tag removal
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        clean_text = re.sub(r"^[,\-\.\s]+|[,\-\.\s]+$", "", clean_text).strip()

        # Check if the remaining text has meaningful speech or is just wake word/isolated event
        residual_words = [w for w in re.sub(r"[^\w\s]", "", clean_text.lower()).split() if w not in ("nova", "hey", "hi", "ok", "okay")]
        is_isolated = (detected_type != AudioEventType.NONE) and (len(residual_words) == 0)

        # 5. Acoustic heuristic check on audio buffer if no textual tag was produced
        if detected_type == AudioEventType.NONE and audio is not None and len(audio) > 0:
            detected_type = cls._detect_acoustic_burst(audio, sample_rate)
            if detected_type != AudioEventType.NONE and len(residual_words) == 0:
                is_isolated = True

        return AudioEventResult(
            event_type=detected_type,
            clean_text=clean_text,
            is_isolated_event=is_isolated,
            confidence=0.92 if detected_type != AudioEventType.NONE else 1.0,
            details=f"Detected {detected_type.value} (isolated={is_isolated})",
        )

    @staticmethod
    def _detect_acoustic_burst(audio: np.ndarray, sample_rate: int) -> AudioEventType:
        """Lightweight acoustic transient detector for coughs or sharp sneezes."""
        if len(audio) < sample_rate * 0.2 or len(audio) > sample_rate * 2.5:
            return AudioEventType.NONE

        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        if peak == 0.0 or rms == 0.0:
            return AudioEventType.NONE

        crest_factor = peak / rms
        # Zero-crossing rate
        zcr = float(np.mean(np.abs(np.diff(np.sign(audio)))) / 2)

        # Coughs/sneezes typically exhibit high crest factor (> 4.5) with moderate-to-high zero-crossing rate
        if crest_factor > 5.5 and 0.15 < zcr < 0.45 and rms > 0.04:
            return AudioEventType.COUGH

        return AudioEventType.NONE
