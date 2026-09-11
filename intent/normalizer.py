"""Natural language text normalization and wake-word preprocessing for NOVA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NormalizedInput:
    raw: str
    normalized: str
    cleaned_lower: str
    has_wake_word: bool
    disambiguated: str = ""
    disambiguation_reason: str = ""


class TextNormalizer:
    """Preprocesses spoken transcripts and user text to strip conversational wrappers and wake words while preserving entity tokens."""

    # Common wake word patterns (including phonetic variants from Whisper transcription)
    WAKE_WORD_PATTERNS = [
        r"^(?:hey\s+|hi\s+|hello\s+|ok\s+|okay\s+|arre\s+|suno\s+)?(?:nova|nobba|no\s+va)\b[,\s:;!.-]*",
        r"^(?:hey|hi|hello)\s+(?:nova|nobba|boss|sir|bhai)\b[,\s:;!.-]*",
        r"[,\s:;!.-]+(?:nova|nobba)\s*$",
    ]

    # Leading conversational opening wrappers and filler prefixes
    CONVERSATIONAL_PREFIXES = [
        r"^(?:boss|sir|bhai|buddy)[,\s:;!.-]+",
        r"^(?:okay|ok|alright|well|so|now)[,\s:;!.-]+",
        r"^(?:hey|hi|hello)[,\s:;!.-]+",
        r"^(?:can\s+you\s+please|could\s+you\s+please|will\s+you\s+please|would\s+you\s+please)[,\s:;!.-]+",
        r"^(?:can\s+you|could\s+you|would\s+you|will\s+you)[,\s:;!.-]+",
        r"^(?:i\s+want\s+you\s+to|i\s+would\s+like\s+you\s+to|i\s+need\s+you\s+to|i\'d\s+like\s+you\s+to)[,\s:;!.-]+",
        r"^(?:i\s+want\s+to|i\s+would\s+like\s+to|i\'d\s+like\s+to|i\s+need\s+to)[,\s:;!.-]+",
        r"^(?:please|kripya|zara|kindly)[,\s:;!.-]+",
        r"^(?:tell\s+me|help\s+me\s+to|help\s+me)[,\s:;!.-]+",
        r"^(?:please\s+go\s+ahead\s+and|just\s+go\s+ahead\s+and|go\s+ahead\s+and|please\s+go\s+and|go\s+and|just|make\s+sure\s+to)[,\s:;!.-]+",
    ]

    # Trailing polite particles that can be safely stripped ONLY when not part of a named entity
    TRAILING_WRAPPERS = [
        r"[,\s:;!.-]+(?:please|kripya|zara|kindly|for\s+me|quickly|fast|boss|sir)\s*$",
        r"[,\s:;!.-]+(?:for\s+me\s+please|please\s+for\s+me)\s*$",
    ]

    # Entity definition guard: If the end of the text matches these, do NOT strip trailing tokens
    ENTITY_TRAILING_GUARDS = [
        r"(?:named|called|titled|labeled|name\s+of|search\s+for|looking\s+for|look\s+for)\s+[^\s,;:]+$",
        r"(?:into|to|as)\s+[^\s,;:]+$",
    ]

    @classmethod
    def normalize(cls, text: str) -> NormalizedInput:
        """Strip wake words, leading conversational prefixes, and trailing particles while preserving core query tokens."""
        if not text:
            return NormalizedInput(raw="", normalized="", cleaned_lower="", has_wake_word=False)

        raw = text.strip()
        working = raw
        has_wake_word = False

        # Iteratively strip wake words, prefixes, and wrappers
        changed = True
        iterations = 0
        while changed and iterations < 6:
            changed = False
            iterations += 1

            # Strip leading/trailing punctuation and whitespace on each iteration
            new_w = re.sub(r"^[,\s:;!.-]+", "", working)
            new_w = re.sub(r"[,\s:;!.\-\?]+$", "", new_w).strip()
            if new_w != working:
                working = new_w
                changed = True

            # 1. Detect and strip wake word
            for pat in cls.WAKE_WORD_PATTERNS:
                if re.search(pat, working, re.IGNORECASE):
                    has_wake_word = True
                    new_w = re.sub(pat, "", working, count=1, flags=re.IGNORECASE).strip()
                    if new_w != working:
                        working = new_w
                        changed = True

            # 2. Strip leading conversational prefixes
            for pat in cls.CONVERSATIONAL_PREFIXES:
                new_w = re.sub(pat, "", working, count=1, flags=re.IGNORECASE).strip()
                if new_w != working:
                    working = new_w
                    changed = True

            # 3. Strip trailing polite wrappers ONLY if not guarded by entity context
            is_guarded = any(re.search(g, working, re.IGNORECASE) for g in cls.ENTITY_TRAILING_GUARDS)
            if not is_guarded:
                for pat in cls.TRAILING_WRAPPERS:
                    new_w = re.sub(pat, "", working, count=1, flags=re.IGNORECASE).strip()
                    if new_w != working:
                        working = new_w
                        changed = True

        # Clean stray internal punctuation (e.g. "Right? What is..." -> "Right What is...")
        working = re.sub(r"([a-zA-Z0-9])\?+\s*", r"\1 ", working)
        working = re.sub(r"([a-zA-Z0-9])[,;:]+\s*", r"\1 ", working)

        # Final strip leading/trailing punctuation and clean multiple internal whitespace
        working = re.sub(r"^[,\s:;!.-]+", "", working)
        working = re.sub(r"[,\s:;!.\-\?]+$", "", working).strip()
        working = re.sub(r"\s+", " ", working)

        # Stage B: Semantic Command Disambiguation
        from intent.disambiguator import SemanticCommandDisambiguator
        disambig_res = SemanticCommandDisambiguator.disambiguate(working)

        effective_text = disambig_res.interpreted_text if disambig_res.is_disambiguated else working
        cleaned_lower = effective_text.lower().strip()

        return NormalizedInput(
            raw=raw,
            normalized=working,
            cleaned_lower=cleaned_lower,
            has_wake_word=has_wake_word,
            disambiguated=disambig_res.interpreted_text if disambig_res.is_disambiguated else "",
            disambiguation_reason=disambig_res.reason if disambig_res.is_disambiguated else "",
        )
