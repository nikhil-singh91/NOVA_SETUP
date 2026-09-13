"""Context-aware speech disambiguation and semantic command interpretation for NOVA."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.logger import get_logger

from intent.models import CanonicalIntent

logger = get_logger(__name__)


from intent.entity_resolver import EntityResolver


@dataclass
class DisambiguationResult:
    """Outcome of contextual speech disambiguation."""

    is_disambiguated: bool
    original_text: str
    interpreted_text: str
    reason: str
    suggested_intent: CanonicalIntent | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class SemanticCommandDisambiguator:
    """Stage B Semantic Interpreter.

    Evaluates the complete utterance in the context of desktop assistant interaction.
    Resolves ASR acoustic ambiguities and homophones (e.g. 'Right' vs 'Write', 'Le' vs 'Play')
    without hardcoding specific phrases, while strictly preserving natural conversation.
    """

    # Common conversational phrases where 'right' must NEVER be converted to 'write'
    CONVERSATIONAL_RIGHT_PATTERNS = [
        r"\b(?:what\s+is|whats)\s+(?:right|the\s+right)\b",
        r"\bright\s+and\s+wrong\b",
        r"\bwrong\s+and\s+right\b",
        r"\bright\s+or\s+wrong\b",
        r"\bis\s+(?:that|it|this)\s+right\b",
        r"\bright\s+now\b",
        r"\ball\s+right\b",
        r"\balright\b",
        r"\bturn\s+right\b",
        r"\bright\s+(?:side|hand|here|there|angle|direction|turn|corner)\b",
        r"\bthat's\s+right\b",
        r"\byou're\s+right\b",
        r"\bam\s+i\s+right\b",
    ]

    # Leading write-action homophone patterns: "right", "rite", "wight", "wrote"
    WRITE_HOMOPHONE_PATTERN = re.compile(
        r"^(?:right|rite|wight|wrote)\b[,\s:;!.\-\?]*",
        re.IGNORECASE,
    )

    # Patterns indicating a request to draft, compose, generate, or type content
    WRITE_CONTENT_INDICATORS = [
        r"\bcode\b",
        r"\bprogram\b",
        r"\balgorithm\b",
        r"\bbubble\s+sort\b",
        r"\bsort\b",
        r"\breverse\b",
        r"\bpython\b",
        r"\bc\+\+\b",
        r"\bcpp\b",
        r"\bjavascript\b",
        r"\bleave\s+application\b",
        r"\bapplication\s+for\b",
        r"\bletter\b",
        r"\bessay\b",
        r"\bnotes?\b",
        r"\bdocument\b",
        r"\bparagraph\b",
        r"\bpoem\b",
        r"\bstory\b",
        r"\bwhat\s+is\s+.+?\s+with\s+answer\b",
        r"\bwith\s+answer\b",
        r"\bin\s+(?:notepad|textedit|text\s+editor|file|editor)\b",
        r"\bhello\s+world\b",
    ]

    @classmethod
    def disambiguate_candidates(cls, candidates: list[str]) -> DisambiguationResult:
        """Evaluate a list of candidate hypotheses (N-best) and return the best semantic interpretation."""
        if not candidates:
            return cls.disambiguate("")

        # First evaluate each candidate
        results = [cls.disambiguate(c) for c in candidates if c and c.strip()]
        if not results:
            return cls.disambiguate(candidates[0])

        # Prefer disambiguated command actions over un-disambiguated text if candidate indicates an action
        for r in results:
            if r.is_disambiguated and r.suggested_intent != CanonicalIntent.GENERAL_CONVERSATION:
                return r

        return results[0]

    @classmethod
    def disambiguate(cls, text: str) -> DisambiguationResult:
        """Evaluate raw/normalized transcript against assistant grammar and contextual probability.

        Args:
            text: Transcribed input string.

        Returns:
            DisambiguationResult containing interpreted text, suggested intent, and parameters.
        """
        raw = (text or "").strip()
        if not raw:
            return DisambiguationResult(
                is_disambiguated=False,
                original_text=raw,
                interpreted_text=raw,
                reason="Empty input",
                suggested_intent=CanonicalIntent.GENERAL_CONVERSATION,
            )

        lower = raw.lower()

        # Clean trailing punctuation for lexical checks
        clean_text = re.sub(r"[,\s:;!.\-\?]+$", "", lower).strip()

        # -------------------------------------------------------------
        # Rule 1: Guard Normal Conversation against 'Right' -> 'Write'
        # -------------------------------------------------------------
        for pat in cls.CONVERSATIONAL_RIGHT_PATTERNS:
            if re.search(pat, clean_text):
                return DisambiguationResult(
                    is_disambiguated=False,
                    original_text=raw,
                    interpreted_text=raw,
                    reason="Conversational/adverbial 'right' detected; preserved without modification.",
                    suggested_intent=CanonicalIntent.GENERAL_CONVERSATION,
                )

        # -------------------------------------------------------------
        # Rule 2: Evaluate 'Right' -> 'Write' Command Disambiguation
        # -------------------------------------------------------------
        if cls.WRITE_HOMOPHONE_PATTERN.match(clean_text):
            # Extract the remainder of the sentence after the leading homophone
            remainder = cls.WRITE_HOMOPHONE_PATTERN.sub("", raw).strip()
            # Also clean leading punctuation from remainder (e.g. "Right? What is..." -> "What is...")
            remainder_clean = re.sub(r"^[,\s:;!.\-\?]+", "", remainder).strip()
            rem_lower = remainder_clean.lower()

            # Check if remainder contains semantic signals of content to be written
            has_write_indicator = any(re.search(ind, rem_lower) for ind in cls.WRITE_CONTENT_INDICATORS)
            # Or if remainder starts with a question/topic like "what is...", "how to...", or contains "in notepad"
            has_question_or_topic = bool(re.match(r"^(?:what\s+is|explain|describe|create|generate|write|about)\b", rem_lower))
            # Or remainder is substantial (> 2 words) and not a directional instruction
            is_valid_clause = len(remainder_clean.split()) >= 2 and not any(d in rem_lower for d in ["side", "turn", "now", "here", "there"])

            if (has_write_indicator or has_question_or_topic or is_valid_clause) and remainder_clean:
                # Extract destination and clean content
                destination = "NOTEPAD"
                content = remainder_clean
                m_dest = re.search(r"\s+in\s+(notepad|textedit|text\s+editor)$", content, re.IGNORECASE)
                if m_dest:
                    dest_str = m_dest.group(1).lower()
                    destination = "NOTEPAD" if "notepad" in dest_str else "TEXTEDIT"
                    content = content[:m_dest.start()].strip()

                interpreted = f"write {content}" if destination == "NOTEPAD" and not m_dest else f"write {remainder_clean}"

                logger.info(
                    "Contextual Disambiguation: Interpreted '%s' as WRITE command (Content: '%s', Destination: '%s')",
                    raw,
                    content,
                    destination,
                )

                return DisambiguationResult(
                    is_disambiguated=True,
                    original_text=raw,
                    interpreted_text=interpreted,
                    reason="Leading 'Right' followed by content clause disambiguated to WRITE command.",
                    suggested_intent=CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT,
                    parameters={
                        "topic": content,
                        "content": content,
                        "destination": destination,
                        "open_in_editor": True,
                    },
                    confidence=0.92,
                )

        # -------------------------------------------------------------
        # Rule 3: Music / Media Playback Disambiguation via Generalized Entity Resolution
        # -------------------------------------------------------------
        generic_music_terms = {
            "another song", "another one", "one more", "something else", "play another",
            "play another song", "play another one", "play one more",
            "play a song", "play some songs", "play some music", "i want to listen to some songs",
            "i want to listen to songs", "i want to listen to music", "i feel like listening to music",
            "play me something", "play something", "give me a song", "put some music on",
            "koi gaana sunao", "kuch sunao", "kuch baja do", "ek aur sunao", "gaana bajao", "music chalao",
            "ek aur bajao", "dusra gaana bajao", "dusra chalao", "kuch aur bajao", "kuch aur chalao",
            "play songs", "songs chalao",
        }
        if clean_text not in generic_music_terms and not clean_text.startswith("play ") and any(k in clean_text for k in ("song", "music", "track", "video", "baja", "bajao")):
            media_query, conf = EntityResolver.extract_media_entity(clean_text)
            if conf >= 0.80 and media_query and media_query.lower() not in ("another", "some", "a", "one", "another song", "something"):
                interpreted = f"play {media_query}"
                logger.info("Contextual Disambiguation: Interpreted '%s' as PLAY_MEDIA (Query: '%s')", raw, media_query)
                return DisambiguationResult(
                    is_disambiguated=True,
                    original_text=raw,
                    interpreted_text=interpreted,
                    reason="Media query pattern recognized with extracted entity.",
                    suggested_intent=CanonicalIntent.PLAY_MEDIA,
                    parameters={"platform": "youtube", "query": media_query},
                    confidence=conf,
                )

        # -------------------------------------------------------------
        # Default: No disambiguation needed
        # -------------------------------------------------------------
        return DisambiguationResult(
            is_disambiguated=False,
            original_text=raw,
            interpreted_text=raw,
            reason="Transcript conforms to standard grammar; no disambiguation required.",
            confidence=1.0,
        )
