"""Regex parser to classify bilingual English/Hindi speech inputs into macOS commands."""

from __future__ import annotations

import re
from typing import Any

from mac_control.models import CommandCategory, MacCommand


class CommandParser:
    """Classifies user queries into specific executable macOS actions using regex."""

    def __init__(self) -> None:
        self._init_rules()

    def _init_rules(self) -> None:
        """Define regex patterns and map them to categories and actions."""
        # Note: input text is pre-cleaned (lowercased, no punctuation)
        self.rules: list[dict[str, Any]] = [
            # ==========================================
            # 1. VOLUME CONTROL
            # ==========================================
            {
                "category": CommandCategory.VOLUME,
                "action": "mute",
                "patterns": [
                    r"\bmute\b", r"\bsilent\b", r"\bawaa?z\s+band\b",
                    r"\bawaa?z\s+mute\b", r"\bmute\s+kar\b"
                ]
            },
            {
                "category": CommandCategory.VOLUME,
                "action": "unmute",
                "patterns": [
                    r"\bunmute\b", r"\bawaa?z\s+chalu\b", r"\bawaa?z\s+unmute\b",
                    r"\bunmute\s+kar\b"
                ]
            },
            {
                "category": CommandCategory.VOLUME,
                "action": "set",
                "patterns": [
                    r"(?:volume|sound|awaa?z|audio)\s+(?:to|set\s+to|kar\s+do|pe\s+kar\s+do)?\s*(\d+)%?",
                    r"(\d+)%?\s*(?:volume|sound|awaa?z|audio)\b",
                    r"\b(?:volume|sound|awaa?z)\s+(\d+)\s*(?:pe|percent|kar)?\b"
                ]
            },
            {
                "category": CommandCategory.VOLUME,
                "action": "increase",
                "patterns": [
                    r"\b(?:increase|raise|turn\s+up|up|louder|plus)\s+(?:the\s+)?(?:volume|sound|awaa?z)\b",
                    r"\b(?:volume|sound|awaa?z)\s+(?:up|badhao|teiz|tej|jyada|zyada|plus)\b",
                    r"\bmake\s+(?:it\s+|volume\s+)?louder\b", r"\bsound\s+badhao\b", r"\bawaa?z\s+badhao\b", r"\bvolume\s+badhao\b"
                ]
            },
            {
                "category": CommandCategory.VOLUME,
                "action": "decrease",
                "patterns": [
                    r"\b(?:decrease|lower|turn\s+down|down|quieter|minus|softer)\s+(?:the\s+)?(?:volume|sound|awaa?z)\b",
                    r"\b(?:volume|sound|awaa?z)\s+(?:down|kam|dheema|dhima|halka|minus)\b",
                    r"\bmake\s+(?:it\s+|volume\s+)?(?:quieter|softer|dimmer)\b", r"\bsound\s+kam\b", r"\bawaa?z\s+kam\b", r"\bvolume\s+kam\b"
                ]
            },
            {
                "category": CommandCategory.VOLUME,
                "action": "get",
                "patterns": [
                    r"\b(?:what is|get|check|show)\s+(?:the\s+)?(?:volume|sound|awaa?z)\b",
                    r"\b(?:volume|sound|awaa?z)\s+(?:kya|kitna)\s+(?:hai)\b",
                    r"\b(?:volume|sound|awaa?z)\s+(?:check|status|show)\b"
                ]
            },

            # ==========================================
            # 2. BRIGHTNESS CONTROL
            # ==========================================
            {
                "category": CommandCategory.BRIGHTNESS,
                "action": "set",
                "patterns": [
                    r"(?:brightness|light|chamak)\s+(?:to|set\s+to|kar\s+do|pe\s+kar\s+do)?\s*(\d+)%?",
                    r"(\d+)%?\s*(?:brightness|light|chamak)\b"
                ]
            },
            {
                "category": CommandCategory.BRIGHTNESS,
                "action": "increase",
                "patterns": [
                    r"\b(?:increase|raise|turn\s+up|up|plus)\s+(?:the\s+)?(?:brightness|light|chamak)\b",
                    r"\b(?:brightness|light|chamak)\s+(?:up|badhao|teiz|tej|jyada|zyada|plus)\b",
                    r"\bmake\s+(?:my\s+)?(?:screen|it|display)\s+brighter\b",
                    r"\bbrightness\s+up\b"
                ]
            },
            {
                "category": CommandCategory.BRIGHTNESS,
                "action": "decrease",
                "patterns": [
                    r"\b(?:decrease|lower|turn\s+down|down|minus)\s+(?:the\s+)?(?:brightness|light|chamak)\b",
                    r"\b(?:brightness|light|chamak)\s+(?:down|kam|dheema|dhima|halka|minus)\b",
                    r"\bmake\s+(?:my\s+)?(?:screen|it|display)\s+(?:dimmer|less\s+bright)\b",
                    r"\bbrightness\s+down\b",
                    r"\bdim\s+(?:the\s+)?screen\b"
                ]
            },
            {
                "category": CommandCategory.BRIGHTNESS,
                "action": "get",
                "patterns": [
                    r"\b(?:what is|get|current|check|show)\s+(?:the\s+)?(?:brightness|light|chamak)\b",
                    r"\b(?:brightness|light|chamak)\s+(?:check|status|show)\b"
                ]
            },

            # ==========================================
            # 3. BROWSER CONTROL
            # ==========================================
            {
                "category": CommandCategory.BROWSER,
                "action": "google_search",
                "patterns": [
                    r"\bgoogle\s+search\s+(.+)",
                    r"\bsearch\s+google\s+for\s+(.+)",
                    r"\bsearch\s+for\s+(.+)\s+on\s+google\b",
                    r"(.+)\s+search\s+karo\b",
                    r"(.+)\s+search\s+on\s+google\b"
                ]
            },
            {
                "category": CommandCategory.BROWSER,
                "action": "youtube_search",
                "patterns": [
                    r"\byoutube\s+search\s+(.+)",
                    r"\bsearch\s+youtube\s+for\s+(.+)",
                    r"\bsearch\s+for\s+(.+)\s+on\s+youtube\b",
                    r"(.+)\s+youtube\s+pe\s+search\b"
                ]
            },
            {
                "category": CommandCategory.BROWSER,
                "action": "open_website",
                "patterns": [
                    r"\bopen\s+(github|leetcode|codechef|chatgpt|gmail|drive|google\s+drive|notion|youtube|google)\b",
                    r"\b(github|leetcode|codechef|chatgpt|gmail|drive|google\s+drive|notion|youtube|google)\s+kholo\b"
                ]
            },

            # ==========================================
            # 4. MEDIA CONTROL
            # ==========================================
            {
                "category": CommandCategory.MEDIA,
                "action": "play_song",
                "patterns": [
                    r"\bplay\s+(.+)",
                    r"(.+)\s+(?:chalao|bajao)\b",
                    r"\bmusic\s+chalao\b",
                    r"\bplay\s+music\b"
                ]
            },
            {
                "category": CommandCategory.MEDIA,
                "action": "pause",
                "patterns": [
                    r"\bpause\b", r"\broko\b", r"\bpause\s+music\b"
                ]
            },
            {
                "category": CommandCategory.MEDIA,
                "action": "resume",
                "patterns": [
                    r"\bresume\b", r"\bchalu\s+karo\b", r"\bresume\s+music\b"
                ]
            },
            {
                "category": CommandCategory.MEDIA,
                "action": "next",
                "patterns": [
                    r"\bnext\b", r"\bnext\s+song\b", r"\bnext\s+track\b",
                    r"\bagla\s+gaana\b", r"\bagla\b"
                ]
            },
            {
                "category": CommandCategory.MEDIA,
                "action": "previous",
                "patterns": [
                    r"\bprevious\b", r"\bprev\b", r"\bpichhla\s+gaana\b", r"\bpichhla\b"
                ]
            },
            {
                "category": CommandCategory.MEDIA,
                "action": "stop",
                "patterns": [
                    r"\bstop\b", r"\bband\s+karo\b", r"\bstop\s+music\b"
                ]
            },

            # ==========================================
            # 5. FINDER CONTROL
            # ==========================================
            {
                "category": CommandCategory.FINDER,
                "action": "open_folder",
                "patterns": [
                    r"\bopen\s+(desktop|downloads|documents|project|movies|pictures|finder)(?:\s+folder|\s+directory)?\b",
                    r"\b(desktop|downloads|documents|project|movies|pictures|finder)(?:\s+folder|\s+directory)?\s+kholo\b"
                ]
            },
            {
                "category": CommandCategory.FINDER,
                "action": "reveal_file",
                "patterns": [
                    r"\breveal\s+(?:file\s+)?(.+)"
                ]
            },

            # ==========================================
            # 6. SCREENSHOT CONTROL
            # ==========================================
            {
                "category": CommandCategory.SCREENSHOT,
                "action": "capture_full",
                "patterns": [
                    r"\b(?:take|capture|grab|snap|save)\s+(?:a\s+)?screenshot\b",
                    r"\b(?:take|capture|grab|snap|save)\s+(?:a\s+)?(?:screen\s+capture|screen\s+shot|snapshot)\b",
                    r"\b(?:take|capture|grab|snap|save)\s+(?:my|the|current)\s+screen\b",
                    r"\b(?:take|click|get)\s+(?:a\s+)?(?:picture|photo)\s+of\s+(?:my|the|current)\s+screen\b",
                    r"\b(?:save|capture)\s+what\s+(?:i\s+am|i\'?m)\s+(?:seeing|looking\s+at)\b",
                    r"\b(?:screenshot|screen\s+shot|screen\s+capture)\s*(?:this|lo|le\s+lo|karo)?\b",
                    r"\bscreen\s+(?:ka\s+screenshot|ki\s+photo|ki\s+picture)\s*(?:lo|le\s+lo)?\b"
                ]
            },
            {
                "category": CommandCategory.SCREENSHOT,
                "action": "capture_area",
                "patterns": [
                    r"\b(?:take|capture)\s+area\s+screenshot\b",
                    r"\b(?:screenshot|screen\s+shot)\s+area\s*lo\b"
                ]
            },
            {
                "category": CommandCategory.SCREENSHOT,
                "action": "capture_window",
                "patterns": [
                    r"\b(?:take|capture)\s+window\s+screenshot\b",
                    r"\b(?:screenshot|screen\s+shot)\s+window\s*lo\b"
                ]
            },
            {
                "category": CommandCategory.SCREENSHOT,
                "action": "open_folder",
                "patterns": [
                    r"\bopen\s+screenshot\s+folder\b",
                    r"\bscreenshot\s+folder\s+kholo\b"
                ]
            },

            # ==========================================
            # 7. CLIPBOARD CONTROL
            # ==========================================
            {
                "category": CommandCategory.CLIPBOARD,
                "action": "copy",
                "patterns": [
                    r"\bcopy\s+(.+)"
                ]
            },
            {
                "category": CommandCategory.CLIPBOARD,
                "action": "paste",
                "patterns": [
                    r"\bpaste\b"
                ]
            },
            {
                "category": CommandCategory.CLIPBOARD,
                "action": "clear",
                "patterns": [
                    r"\bclear\s+clipboard\b"
                ]
            },
            {
                "category": CommandCategory.CLIPBOARD,
                "action": "read",
                "patterns": [
                    r"\bread\s+clipboard\b"
                ]
            },

            # ==========================================
            # 8. NETWORK CONTROL
            # ==========================================
            {
                "category": CommandCategory.NETWORK,
                "action": "on",
                "patterns": [
                    r"\b(?:turn\s+on|enable|switch\s+on)\s+(?:the\s+|my\s+)?(?:wifi|wi-fi)\b",
                    r"\b(?:wifi|wi-fi)\s+(?:on|chalu|enable)\b",
                ],
                "args": {"target": "wifi"}
            },
            {
                "category": CommandCategory.NETWORK,
                "action": "off",
                "patterns": [
                    r"\b(?:turn\s+off|disable|switch\s+off)\s+(?:the\s+|my\s+)?(?:wifi|wi-fi)\b",
                    r"\b(?:wifi|wi-fi)\s+(?:off|band|disable)\b",
                ],
                "args": {"target": "wifi"}
            },
            {
                "category": CommandCategory.NETWORK,
                "action": "status",
                "patterns": [
                    r"\b(?:check|is|what|which|tell\s+me)\s+(?:my\s+|the\s+)?(?:wifi|wi-fi|network)(?:\s+(?:on|connected\s+to|status|state))?\b",
                    r"\b(?:wifi|wi-fi)\s+(?:status|check|state)\b",
                ],
                "args": {"target": "wifi"}
            },
            {
                "category": CommandCategory.NETWORK,
                "action": "on",
                "patterns": [
                    r"\b(?:turn\s+on|enable|switch\s+on)\s+(?:the\s+|my\s+)?bluetooth\b",
                    r"\bbluetooth\s+(?:on|chalu|enable)\b",
                ],
                "args": {"target": "bluetooth"}
            },
            {
                "category": CommandCategory.NETWORK,
                "action": "off",
                "patterns": [
                    r"\b(?:turn\s+off|disable|switch\s+off)\s+(?:the\s+|my\s+)?bluetooth\b",
                    r"\bbluetooth\s+(?:off|band|disable)\b",
                ],
                "args": {"target": "bluetooth"}
            },
            {
                "category": CommandCategory.NETWORK,
                "action": "status",
                "patterns": [
                    r"\b(?:check|is|what|tell\s+me)\s+(?:my\s+|the\s+)?bluetooth(?:\s+(?:on|status|state|on\s+or\s+off))?\b",
                    r"\bbluetooth\s+(?:status|check|state)\b",
                ],
                "args": {"target": "bluetooth"}
            },
            {
                "category": CommandCategory.NETWORK,
                "action": "get",
                "patterns": [
                    r"\b(?:check|show|get)\s+network\s+status\b",
                    r"\bnetwork\s+check\b"
                ]
            },

            # ==========================================
            # 9. SYSTEM CONTROL
            # ==========================================
            {
                "category": CommandCategory.SYSTEM,
                "action": "sleep",
                "patterns": [
                    r"\b(?:sleep\s+mac|mac\s+sleep|go\s+to\s+sleep)\b",
                    r"\b(?:sleep|so\s+jao)\b"
                ]
            },
            {
                "category": CommandCategory.SYSTEM,
                "action": "restart",
                "patterns": [
                    r"\b(?:restart\s+mac|mac\s+restart|restart)\b"
                ],
                "is_dangerous": True
            },
            {
                "category": CommandCategory.SYSTEM,
                "action": "shutdown",
                "patterns": [
                    r"\b(?:shutdown\s+mac|mac\s+shutdown|shutdown)\b"
                ],
                "is_dangerous": True
            },
            {
                "category": CommandCategory.SYSTEM,
                "action": "lock_screen",
                "patterns": [
                    r"\b(?:lock\s+screen|lock\s+mac|mac\s+lock|lock)\b"
                ]
            },
            {
                "category": CommandCategory.SYSTEM,
                "action": "empty_trash",
                "patterns": [
                    r"\b(?:empty\s+trash|empty\s+bin|trash\s+khali)\b"
                ],
                "is_dangerous": True
            },

            # ==========================================
            # 10. APPLICATIONS CONTROL
            # ==========================================
            {
                "category": CommandCategory.APPLICATIONS,
                "action": "open",
                "patterns": [
                    r"\bopen\s+(.+)",
                    r"(.+)\s+kholo\b",
                    r"\bactivation\s+of\s+(.+)"
                ]
            },
            {
                "category": CommandCategory.APPLICATIONS,
                "action": "close",
                "patterns": [
                    r"\b(?:close|quit)\s+(.+)",
                    r"(.+)\s+(?:close|quit|band)\s*karo\b"
                ]
            },
            {
                "category": CommandCategory.APPLICATIONS,
                "action": "force_quit",
                "patterns": [
                    r"\b(?:force\s+quit|kill)\s+(.+)"
                ]
            },
            {
                "category": CommandCategory.APPLICATIONS,
                "action": "restart",
                "patterns": [
                    r"\brestart\s+app\s+(.+)",
                    r"\brestart\s+(.+)"
                ]
            }
        ]

    def parse(self, text: str) -> MacCommand | None:
        """Parse text input into a MacCommand instance if matched, otherwise return None."""
        cleaned = self._clean_text(text)
        if not cleaned:
            return None

        # Check each rule sequentially
        for rule in self.rules:
            for pattern in rule["patterns"]:
                match = re.search(pattern, cleaned)
                if match:
                    # Resolve command parameters
                    args = dict(rule.get("args", {}))

                    # Capture specific regex group parameters
                    if match.groups():
                        captured = match.group(1).strip()
                        action = rule["action"]

                        # Handle specific argument mappings
                        if rule["category"] == CommandCategory.VOLUME and action == "set":
                            args["value"] = int(captured)
                        elif rule["category"] == CommandCategory.VOLUME and action in ("increase", "decrease"):
                            args["step"] = int(captured) if captured.isdigit() else 10
                        elif rule["category"] == CommandCategory.BRIGHTNESS and action == "set":
                            args["value"] = int(captured)
                        elif rule["category"] == CommandCategory.BRIGHTNESS and action in ("increase", "decrease"):
                            args["step"] = int(captured) if captured.isdigit() else 10
                        elif rule["category"] == CommandCategory.APPLICATIONS:
                            args["app_name"] = captured
                        elif rule["category"] == CommandCategory.BROWSER and action == "open_website":
                            args["site"] = captured
                        elif rule["category"] == CommandCategory.BROWSER and action in ("google_search", "youtube_search"):
                            args["query"] = captured
                        elif rule["category"] == CommandCategory.MEDIA and action == "play_song":
                            # Ignore "some" or generic suffixes
                            args["song"] = re.sub(r"\b(?:some|a)\b", "", captured).strip()
                        elif rule["category"] == CommandCategory.FINDER and action == "open_folder":
                            args["folder"] = captured
                        elif rule["category"] == CommandCategory.FINDER and action == "reveal_file":
                            args["path"] = captured
                        elif rule["category"] == CommandCategory.CLIPBOARD and action == "copy":
                            args["text"] = captured

                    return MacCommand(
                        category=rule["category"],
                        action=rule["action"],
                        raw_input=text,
                        args=args,
                        is_dangerous=rule.get("is_dangerous", False)
                    )
        return None

    def _clean_text(self, text: str) -> str:
        """Lowercase text and remove basic punctuation for regex matching stability."""
        text = text.lower().strip()
        text = re.sub(r"[?.,!]", "", text)
        return " ".join(text.split())
