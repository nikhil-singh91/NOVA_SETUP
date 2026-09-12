"""Central Response Orchestrator for NOVA.

Receives user input, detected intent, execution results, screen perception,
and conversation context to synthesize warm, friend-like, context-aware responses.
Guarantees:
- Zero internal reasoning/metadata leakage.
- Strict isolation of TTS text (speech-safe, no markdown/emojis spoken) vs Dashboard text (rich, expressive).
- Elimination of repetitive 'Boss' spam.
- Natural language adaptation (English vs Hinglish).
- Dynamic response length based on task type.
- Zero generic customer-support filler clichés.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.logger import get_logger
from core.response_cleaner import clean_model_response
from intent.models import CanonicalIntent, StructuredAction

logger = get_logger(__name__)


@dataclass
class OrchestratedResponse:
    """Unified response container containing display and speech representations."""
    display_text: str
    spoken_text: str
    intent: CanonicalIntent
    success: bool = True
    metadata: dict[str, Any] | None = None


class ResponseOrchestrator:
    """Orchestrates natural human responses derived from real action execution and world observation."""

    BANNED_SUPPORT_PHRASES = [
        "how may i assist you today",
        "how can i help you today",
        "i understand your concern",
        "i apologize for the inconvenience",
        "certainly",
        "let me help you with that",
        "because i try to keep things concise",
        "is there anything else i can assist you with",
        "as an ai",
        "i do not have feelings",
    ]

    HINGLISH_INDICATORS = frozenset({
        "kya", "hai", "batao", "baja", "bajao", "bhajao", "chala", "chalao",
        "chalu", "sunao", "lagao", "kholo", "dikhao", "dekh", "dekho", "padho",
        "samjhao", "band", "gaana", "gaane", "pe", "par", "mein", "mera", "meri",
        "mere", "aaj", "kal", "scene", "yaar", "arre", "haan", "nahi", "thoda",
        "accha", "badhiya", "karo", "kar", "do", "dijiye", "ho", "raha", "rahi",
    })

    @classmethod
    def detect_is_hinglish(cls, text: str) -> bool:
        """Detect whether the user utterance contains prominent Hindi/Hinglish vocabulary."""
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return False
        match_count = sum(1 for t in tokens if t in cls.HINGLISH_INDICATORS)
        return (match_count / len(tokens) >= 0.20) or match_count >= 2

    @classmethod
    def format_action_response(
        cls,
        action: StructuredAction,
        result: Any,
        user_text: str,
        screen_desc: str | None = None,
    ) -> OrchestratedResponse:
        """Generate a natural response based on the actual result of an executed action."""
        is_hi = cls.detect_is_hinglish(user_text)
        success = getattr(result, "success", True)
        metadata = getattr(result, "metadata", {}) or {}
        spoken_override = getattr(result, "spoken_response", None)

        # 0A. Search Current Browser Tab Intent
        if action.intent == CanonicalIntent.SEARCH_CURRENT_TAB:
            q = action.parameters.get("query", "")
            if success:
                if is_hi:
                    disp = f"Haan, us tab mein '{q}' search kar diya! 🔍"
                    spk = f"Haan, us tab mein {q} search kar diya."
                else:
                    disp = f"Yep, searched for {q} in that tab. 🔍"
                    spk = f"Yep, searched for {q} in that tab."
                return OrchestratedResponse(disp, spk, action.intent, success=True, metadata=metadata)
            else:
                disp = f"Could not search for {q} in the active tab." if not is_hi else f"Active tab mein {q} search nahi ho paya."
                return OrchestratedResponse(disp, disp, action.intent, success=False, metadata=metadata)

        # 0B. Open New Tab Intent
        if action.intent == CanonicalIntent.OPEN_NEW_TAB:
            browser = action.parameters.get("browser") or metadata.get("browser", "Chrome")
            if success:
                if is_hi:
                    disp = f"Naya tab open kar diya {browser} mein! 🌐"
                    spk = f"Naya tab open kar diya {browser} mein."
                else:
                    disp = f"Opened a new tab in {browser}. 🌐"
                    spk = f"Opened a new tab in {browser}."
                return OrchestratedResponse(disp, spk, action.intent, success=True, metadata=metadata)
            else:
                disp = f"Could not open a new tab in {browser}." if not is_hi else f"{browser} mein naya tab open nahi ho paya."
                return OrchestratedResponse(disp, disp, action.intent, success=False, metadata=metadata)

        # 1. Media Playback Intent
        if action.intent == CanonicalIntent.PLAY_MEDIA:
            title = metadata.get("clean_title") or metadata.get("video_title") or action.parameters.get("query", "music")
            verified = metadata.get("verified", success)

            if success and verified:
                if is_hi:
                    disp = f"Haan, mil gaya — {title} play kar raha hoon. 🎵"
                    spk = f"Haan, mil gaya — {title} play kar raha hoon."
                else:
                    disp = f"Yep, found it — playing {title} now. 🎵"
                    spk = f"Yep, found it — playing {title} now."
                return OrchestratedResponse(disp, spk, action.intent, success=True, metadata=metadata)
            elif metadata.get("clarification_needed"):
                candidates = metadata.get("candidates", [])
                c_name = candidates[0].split("|")[0].strip() if candidates else title
                if is_hi:
                    disp = f"YouTube par kuch milte-julte videos mile hain jaise '{c_name}'. Aap kaunsa play karna chahte ho?"
                    spk = f"YouTube par kuch milte-julte videos mile hain jaise {c_name}. Aap kaunsa play karna chahte ho?"
                else:
                    disp = f"I found a few close matches like '{c_name}', but which one did you want to hear?"
                    spk = f"I found a few close matches like {c_name}, but which one did you want to hear?"
                return OrchestratedResponse(disp, spk, action.intent, success=False, metadata=metadata)
            else:
                if is_hi:
                    disp = f"YouTube search to open ho gaya, par sahi video start hona confirm nahi hua."
                    spk = f"YouTube search to open ho gaya, par sahi video start hona confirm nahi hua."
                else:
                    disp = f"I opened YouTube search for {title}, but couldn't verify the video started."
                    spk = f"I opened YouTube search for {title}, but couldn't verify the video started."
                return OrchestratedResponse(disp, spk, action.intent, success=False, metadata=metadata)

        # 2. YouTube Shorts Intent
        if action.intent == CanonicalIntent.WATCH_SHORTS:
            q = action.parameters.get("query", "")
            if success:
                if q:
                    disp = f"Here are {q} Shorts on YouTube! 📱" if not is_hi else f"Aapke liye {q} Shorts open kar diye hain! 📱"
                    spk = f"Here are {q} Shorts on YouTube." if not is_hi else f"Aapke liye {q} Shorts open kar diye hain."
                else:
                    disp = "Opened YouTube Shorts for you. 📱" if not is_hi else "YouTube Shorts open kar diye hain. 📱"
                    spk = "Opened YouTube Shorts for you." if not is_hi else "YouTube Shorts open kar diye hain."
                return OrchestratedResponse(disp, spk, action.intent, success=True, metadata=metadata)
            else:
                disp = "Couldn't open YouTube Shorts right now." if not is_hi else "Abhi YouTube Shorts open nahi ho paya."
                return OrchestratedResponse(disp, disp, action.intent, success=False, metadata=metadata)

        # 3. Screen Awareness Intent
        if action.intent in (CanonicalIntent.WHAT_AM_I_LOOKING_AT, CanonicalIntent.READ_CURRENT_PAGE, CanonicalIntent.SUMMARIZE_CURRENT_PAGE):
            if screen_desc:
                disp = f"{screen_desc} 👀"
                spk = screen_desc
                return OrchestratedResponse(disp, spk, action.intent, success=True, metadata=metadata)
            elif spoken_override:
                clean = cls.clean_for_display(spoken_override)
                return OrchestratedResponse(clean, cls.clean_for_speech(clean), action.intent, success=success, metadata=metadata)
            else:
                msg = "I can't see the screen right now — Eyes isn't available." if not is_hi else "Screen abhi access nahi ho pa rahi — Eyes available nahi hai."
                return OrchestratedResponse(msg, msg, action.intent, success=False, metadata=metadata)

        # 4. Standard deterministic actions (volume, brightness, wifi, apps)
        if spoken_override:
            disp = cls.clean_for_display(spoken_override)
            spk = cls.clean_for_speech(disp)
            return OrchestratedResponse(disp, spk, action.intent, success=success, metadata=metadata)

        # Generic fallback
        action_name = action.intent.value.replace("_", " ")
        disp = f"Done — executed {action_name}." if success else f"Could not complete {action_name}."
        return OrchestratedResponse(disp, disp, action.intent, success=success, metadata=metadata)

    @classmethod
    def clean_for_display(cls, text: str) -> str:
        """Sanitize text for Dashboard display: removes reasoning blocks, bans repetitive 'Boss'."""
        if not text:
            return ""
        clean = clean_model_response(text, default_fallback="")
        # Remove repetitive "Boss" prefixing
        clean = re.sub(r"^(?:(?:yes|okay|sure)\s*,?\s*)?boss\s*[,:]*\s*", "", clean, flags=re.IGNORECASE).strip()
        # Cap multiple "Boss" occurrences to at most 1
        parts = clean.split("Boss")
        if len(parts) > 2:
            clean = "Boss".join(parts[:2]) + "".join(parts[2:])

        # Ban robotic support clichés
        for b in cls.BANNED_SUPPORT_PHRASES:
            clean = re.sub(rf"\b{re.escape(b)}\b", "", clean, flags=re.IGNORECASE)

        clean = re.sub(r"\s{2,}", " ", clean).strip()
        return clean

    @classmethod
    def clean_for_speech(cls, text: str) -> str:
        """Sanitize text for Text-to-Speech: removes markdown, emojis, asterisks, URLs."""
        from voice.speaker import clean_text_for_speech
        return clean_text_for_speech(text)
