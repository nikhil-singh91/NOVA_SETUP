"""Local keyword and intent recognition for voice commands."""

from __future__ import annotations

import re
from typing import Callable

from core.logger import get_logger

logger = get_logger(__name__)


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the minimum edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


class CommandRecognizer:
    """Classifies spoken phrases into local intents without requiring an LLM call."""

    def __init__(self) -> None:
        self._intents: dict[str, list[str]] = {
            "shutdown": [
                "shutdown",
                "shutdown nova",
                "exit",
                "exit nova",
                "quit",
                "quit nova",
                "close yourself",
                "turn off nova",
                "power off nova",
                "go to sleep",
                "बाय नोवा",
                "शटडाउन",
                "एग्जिट",
                "बंद करो",
                "सो जाओ",
            ],
            "cancel": ["cancel", "stop", "nevermind", "रहने दो", "रुको"],
        }

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"[^\w\s]", "", text.lower()).strip()

    def recognize(self, text: str) -> str | None:
        """Return the matched intent name, or None if no local intent matched."""
        cleaned_input = self._clean(text)
        if not cleaned_input:
            return None

        # Strip wake words for normalized local matching
        normalized = re.sub(r"^(?:hey\s+|hi\s+|ok\s+|okay\s+)?nova\s+", "", cleaned_input).strip()

        # 1. Exact match on cleaned or normalized input
        for intent, phrases in self._intents.items():
            for phrase in phrases:
                cleaned_phrase = self._clean(phrase)
                if cleaned_input == cleaned_phrase or normalized == cleaned_phrase:
                    return intent

        # 2. Fuzzy match for short isolated commands
        for intent, phrases in self._intents.items():
            for phrase in phrases:
                cleaned_phrase = self._clean(phrase)
                dist = levenshtein_distance(normalized, cleaned_phrase)
                max_len = max(len(normalized), len(cleaned_phrase))
                if max_len > 3 and dist <= 1:
                    return intent

        return None


class VoiceCommandRouter:
    """Dispatches recognized local voice intents to registered handler callables."""

    def __init__(self, recognizer: CommandRecognizer | None = None) -> None:
        self.recognizer = recognizer or CommandRecognizer()
        self._handlers: dict[str, Callable[[], None]] = {}

    def register_handler(self, intent: str, handler: Callable[[], None]) -> None:
        """Register a handler callback for an intent."""
        self._handlers[intent] = handler

    def route(self, text: str) -> bool:
        """Recognize and execute a command handler if matched.

        Returns True if a local command was matched and handled, False otherwise.
        """
        intent = self.recognizer.recognize(text)
        if intent and intent in self._handlers:
            logger.info("Local command recognized: '%s' -> executing handler.", intent)
            try:
                self._handlers[intent]()
                return True
            except Exception as exc:
                logger.error("Error executing command handler for '%s': %s", intent, exc, exc_info=True)
                return False
        return False
