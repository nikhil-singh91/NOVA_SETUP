import re
from typing import Callable

def get_levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the edit distance between two strings."""
    if len(s1) < len(s2):
        return get_levenshtein_distance(s2, s1)
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
    """Classifies text into local intents using exact and fuzzy matching."""

    def __init__(self) -> None:
        self._intents: dict[str, list[str]] = {
            "shutdown": [
                "bye", "bye nova", "shutdown", "shutdown nova", "exit", "exit nova",
                "close yourself", "stop listening", "sleep", "go to sleep", "see you",
                "talk to you later", "thats all", "thats enough", "quit", "quit nova",
                "बाय", "बाय नोवा", "बाए नोबा", "बाय नोबा", "शटडाउन", "एग्जिट", "बंद करो", "सो जाओ", "सोने जाओ"
            ],
            # Easy to add future intents
            "restart": ["restart", "restart nova"],
            "sleep_mode": ["sleep mode"],
            "mute": ["mute"],
            "unmute": ["unmute"],
            "open_vscode": ["open vscode", "open vs code"],
            "open_chrome": ["open chrome"],
            "play_music": ["play music"]
        }

    def recognize(self, text: str) -> str | None:
        """Recognize if the input text matches any registered intent.

        Returns the intent name if matched, or None.
        """
        cleaned_input = self._clean_text(text)
        if not cleaned_input:
            return None

        # Try exact keyword / substring matching first
        for intent, phrases in self._intents.items():
            for phrase in phrases:
                cleaned_phrase = self._clean_text(phrase)
                if cleaned_input == cleaned_phrase or cleaned_phrase in cleaned_input:
                    return intent

        # Fallback to fuzzy matching with Levenshtein distance
        for intent, phrases in self._intents.items():
            for phrase in phrases:
                cleaned_phrase = self._clean_text(phrase)
                dist = get_levenshtein_distance(cleaned_input, cleaned_phrase)
                # Allow minor changes (e.g. 1-2 characters off)
                max_allowed_dist = 2 if len(cleaned_phrase) <= 8 else 3
                if dist <= max_allowed_dist:
                    return intent

        return None

    def _clean_text(self, text: str) -> str:
        text = text.lower().strip()
        # Remove punctuation
        text = re.sub(r"[^\w\s]", "", text)
        return " ".join(text.split())


class VoiceCommandRouter:
    """Routes recognized intents to their corresponding local logic handlers."""

    def __init__(self, recognizer: CommandRecognizer) -> None:
        self.recognizer = recognizer
        self._handlers: dict[str, Callable[[], None]] = {}

    def register_handler(self, intent: str, handler: Callable[[], None]) -> None:
        self._handlers[intent] = handler

    def route(self, text: str) -> bool:
        """Route the command to the registered handler if recognized.

        Returns True if routed successfully, False otherwise.
        """
        intent = self.recognizer.recognize(text)
        if intent and intent in self._handlers:
            self._handlers[intent]()
            return True
        return False
