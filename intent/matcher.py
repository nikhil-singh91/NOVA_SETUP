"""Linguistic pattern and semantic paraphrase matcher for canonical NOVA intents."""

from __future__ import annotations

import re
from typing import Any
from core.environment import environment_observer, ContextResolver
from core.logger import get_logger
from intent.models import CanonicalIntent, StructuredAction
from intent.normalizer import NormalizedInput

logger = get_logger(__name__)


class LinguisticIntentMatcher:
    """Matches normalized user text against generalized linguistic patterns and extracts entities."""

    def match(self, norm: NormalizedInput | str) -> StructuredAction | None:
        """Attempt deterministic and paraphrase matching on normalized input."""
        if isinstance(norm, str):
            from intent.normalizer import TextNormalizer
            norm = TextNormalizer.normalize(norm)
        txt = norm.cleaned_lower
        raw = norm.raw
        clean_text = norm.normalized

        # 1. System Shutdown, Confirmation, Cancellation & Lock Screen
        res = self._match_system_commands(txt, raw, clean_text)
        if res:
            return res

        # 1A-1. Brightness Hardware Control
        res = self._match_brightness_commands(txt, raw, clean_text)
        if res:
            return res

        # 1A-2. Volume Hardware Control
        res = self._match_volume_commands(txt, raw, clean_text)
        if res:
            return res

        # 1B. Screenshot Capture Actions ("Take a screenshot", "Capture my screen", "Save what I am seeing")
        res = self._match_screenshot_commands(txt, raw, clean_text)
        if res:
            return res

        # 1C. Camera Actions ("Open camera", "Take a picture")
        res = self._match_camera_commands(txt, raw, clean_text)
        if res:
            return res

        # 1D. Clipboard Actions ("What is in my clipboard?", "Clear clipboard")
        res = self._match_clipboard_commands(txt, raw, clean_text)
        if res:
            return res

        # 1E. Hardware Controls (Wi-Fi, Bluetooth)
        res = self._match_hardware_commands(txt, raw, clean_text)
        if res:
            return res

        # 2. Screen Recording ("Record screen", "Stop screen recording")
        res = self._match_screen_recording(txt, raw, clean_text)
        if res:
            return res

        # 3. Screen / Visual Awareness ("What am I looking at?", "What is on my screen?")
        res = self._match_screen_awareness(txt, raw, clean_text)
        if res:
            return res

        # 3B. Error Explanation ("What error is on my screen?", "Explain this error")
        res = self._match_error_explanation(txt, raw, clean_text)
        if res:
            return res

        # 3C. Popup Dismissal ("Close this popup", "Dismiss dialog")
        res = self._match_popup_commands(txt, raw, clean_text)
        if res:
            return res

        # 3D. Scroll Until Visible ("Scroll until you find contact us", "Scroll until you find pricing")
        res = self._match_scroll_until_visible(txt, raw, clean_text)
        if res:
            return res

        # 3E. UI Typing ("Type hello", "Type DSA roadmap", "Enter my search query")
        res = self._match_ui_typing(txt, raw, clean_text)
        if res:
            return res

        # 3F. UI Clicking & Selection ("Click search", "Click login", "Click the second result", "Select C++")
        res = self._match_ui_clicking(txt, raw, clean_text)
        if res:
            return res

        # 4. Delete Safety ("Delete this", "Delete that", "Delete it")
        res = self._match_delete_commands(txt, raw, clean_text)
        if res:
            return res

        # 5. Document Writing ("Write an application for college leave", "Write a leave application")
        res = self._match_document_writing(txt, raw, clean_text)
        if res:
            return res

        # 5B. Multi-Step Autonomous Goals (Task Agent V3)
        res = self._match_autonomous_tasks(txt, raw, clean_text)
        if res:
            return res

        # 6. Folder & File Operations ("Create a folder on Desktop", "Open DSA folder", "Create main.cpp inside it")
        res = self._match_folder_and_file_commands(txt, raw, clean_text)
        if res:
            return res

        # 7. Reminder & Scheduling Intent ("I want to go to the market at 8 PM")
        res = self._match_reminder_intent(txt, raw, clean_text)
        if res:
            return res

        # 8. YouTube Shorts ("Play Shorts", "Open YouTube Shorts", "Show me YouTube Shorts")
        res = self._match_shorts_commands(txt, raw, clean_text)
        if res:
            return res

        # 9. In-Site Search & Current Site Search ("In Flipkart search mobile phones", "Search iPhone here")
        res = self._match_in_site_search(txt, raw, clean_text)
        if res:
            return res

        # 10. Tab Navigation (Next, Previous, New, Switch, Close)
        res = self._match_tab_commands(txt, raw, clean_text)
        if res:
            return res

        # 11. Page Reading & Understanding (Read, Summarize, Explain)
        res = self._match_page_understanding(txt, raw, clean_text)
        if res:
            return res

        # 12. Scrolling & History (Scroll Down, Up, Top, Bottom, Back, Forward)
        res = self._match_scrolling_and_history(txt, raw, clean_text)
        if res:
            return res

        # 13. Ordinal Result Selection ("Open the second one")
        res = self._match_ordinal_selection(txt, raw, clean_text)
        if res:
            return res

        # 14. Media Playback & YouTube ("Play song Mere Liye", "I want to watch Motu Patlu")
        res = self._match_media_playback(txt, raw, clean_text)
        if res:
            return res

        # 15A. Desktop Application Launching ("Open VS Code", "Start code editor")
        res = self._match_app_launch(txt, raw, clean_text)
        if res:
            return res

        # 15B. Desktop Application Closing ("Close Sublime Text", "Quit VS Code")
        res = self._match_app_close(txt, raw, clean_text)
        if res:
            return res

        # 16. Web Search & Research ("Search Google for ...", "Search for most important books", "Browse internet and search for ...")
        res = self._match_search_and_research(txt, raw, clean_text)
        if res:
            return res

        # 17. Website Opening & Discovery ("Go to AKTU website", "Open Flipkart", "Open Mirai School of Technology")
        res = self._match_website_opening(txt, raw, clean_text)
        if res:
            return res

        return None

    def _match_system_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # Confirmations
        if txt in ["yes", "ha", "haan", "sure", "do it", "confirm", "proceed", "yes please", "haan kar do", "theek hai"]:
            return StructuredAction(
                intent=CanonicalIntent.CONFIRM_ACTION,
                confidence=1.0,
                raw_input=raw,
                normalized_input=norm_text,
            )

        # Denials
        if txt in ["no", "nah", "nahi", "cancel it", "don't do it", "mat karo"]:
            return StructuredAction(
                intent=CanonicalIntent.DENY_ACTION,
                confidence=1.0,
                raw_input=raw,
                normalized_input=norm_text,
            )

        # Cancellation / Stop
        if txt in [
            "cancel", "stop", "nevermind", "never mind", "roko", "band karo",
            "stop research", "stop scrolling", "stop auto shorts", "abort",
            "stop doing that", "don't continue", "dont continue", "stop task",
            "cancel task", "रहने दो", "रुको"
        ]:
            return StructuredAction(
                intent=CanonicalIntent.CANCEL_ACTION,
                confidence=1.0,
                raw_input=raw,
                normalized_input=norm_text,
            )

        # System Shutdown
        if re.search(r"^(?:shut\s*down|power\s*off|turn\s*off)(?:\s+(?:nova|system|computer|mac))?$", txt):
            return StructuredAction(
                intent=CanonicalIntent.SYSTEM_SHUTDOWN,
                confidence=1.0,
                raw_input=raw,
                normalized_input=norm_text,
            )

        # Lock Screen
        if txt in ["lock screen", "lock my screen", "lock mac", "lock my mac", "lock computer", "screen lock karo"]:
            return StructuredAction(
                intent=CanonicalIntent.LOCK_SCREEN,
                confidence=0.98,
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_brightness_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        if any(q in txt for q in ["how to", "how do i", "how can i", "why", "what does brightness mean"]):
            return None

        # 0. Status / Get query: "what is the brightness", "check brightness", "get brightness", "current brightness"
        if re.search(r"^(?:what\s+is|get|check|show|current)\s+(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|screen|display))?$|^brightness\s+(?:check|status|show)$", txt):
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_BRIGHTNESS,
                confidence=0.98,
                parameters={"action": "get", "target": "system brightness"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 1. Relative Increase By: "increase brightness by 10%", "increase brightness by 20"
        m_bri_rel_inc = re.search(
            r"^(?:increase|raise|turn\s+up)\s+(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness\s+by\s+(\d+)(?:\s*(?:percent|%))?(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|screen|display))?$",
            txt,
        )
        if m_bri_rel_inc:
            step = max(1, min(100, int(m_bri_rel_inc.group(1))))
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_BRIGHTNESS,
                confidence=0.98,
                parameters={"action": "increase", "step": step, "is_relative": True, "unit": "percent", "target": "system brightness"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 2. Relative Decrease By: "decrease brightness by 10%", "lower brightness by 20 percent"
        m_bri_rel_dec = re.search(
            r"^(?:decrease|lower|turn\s+down)\s+(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness\s+by\s+(\d+)(?:\s*(?:percent|%))?(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|screen|display))?$",
            txt,
        )
        if m_bri_rel_dec:
            step = max(1, min(100, int(m_bri_rel_dec.group(1))))
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_BRIGHTNESS,
                confidence=0.98,
                parameters={"action": "decrease", "step": step, "is_relative": True, "unit": "percent", "target": "system brightness"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 3. Absolute Set / Increase To / Decrease To / Value Expressions:
        # "set brightness to 80%", "set my brightness to 50 percent", "increase brightness to 80%", "set my Mac brightness to 80",
        # "increase the brightness to 80 percent", "make brightness 70%", "brightness 100%", "make it 80 percent brighter",
        # "make screen 80 percent bright", "decrease brightness to 30%", "lower brightness to 40%"
        m_bri_set = re.search(
            r"^(?:(?:set|make|change)\s+(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness\s+(?:to\s+)?(\d+)(?:\s*(?:percent|%))?(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|screen|display))?|"
            r"(?:set|make)\s+(?:my\s+)?mac\s+brightness\s+(?:to\s+)?(\d+)(?:\s*(?:percent|%))?|"
            r"(?:increase|raise|turn\s+up)\s+(?:(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness\s+to\s+(\d+)(?:\s*(?:percent|%))?|(\d+)(?:\s*(?:percent|%))\s*(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness)|"
            r"(?:decrease|lower|turn\s+down)\s+(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness\s+to\s+(\d+)(?:\s*(?:percent|%))?|"
            r"(?:brightness|screen\s+brightness)\s+(?:to\s+|at\s+)?(\d+)(?:\s*(?:percent|%))?|"
            r"(\d+)(?:\s*(?:percent|%))\s*(?:brightness|screen\s+brightness|display\s+brightness)|"
            r"make\s+(?:the\s+|my\s+|it\s+)?(?:screen\s+|display\s+|brightness\s+)?(\d+)(?:\s*(?:percent|%))\s*bright(?:er|ness)?)$",
            txt,
        )
        if m_bri_set:
            val_str = next(g for g in m_bri_set.groups() if g is not None)
            val = max(0, min(100, int(val_str)))
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_BRIGHTNESS,
                confidence=0.98,
                parameters={"action": "set", "value": val, "unit": "percent", "target": "system brightness"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 4. Basic Increase / Make Brighter:
        # "increase brightness", "increase the brightness", "increase brightness of my Mac", "make the screen brighter",
        # "make screen brighter", "please make my screen brighter", "make it brighter", "brightness up", "brighter",
        # "turn the brightness up", "turn brightness up", "turn up the brightness"
        m_bri_inc = re.search(
            r"^(?:increase|raise|turn\s+up|more)\s+(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|screen|display))?$|"
            r"^turn\s+(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness\s+(?:up|brighter)(?:\s+(?:for\s+me|now))?$|"
            r"^make\s+(?:the\s+|my\s+|it\s+)?(?:screen|it|display|brightness)\s+brighter(?:\s+(?:for\s+me|now))?$|"
            r"^(?:brightness\s+up|screen\s+brighter|brighter)$",
            txt,
        )
        if m_bri_inc:
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_BRIGHTNESS,
                confidence=0.98,
                parameters={"action": "increase", "step": 10, "target": "system brightness"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 5. Basic Decrease / Make Dimmer / Darker:
        # "decrease brightness", "decrease the brightness", "lower screen brightness", "lower brightness",
        # "make screen darker", "make the screen darker", "make screen dimmer", "dim screen", "dim the screen", "brightness down", "dimmer", "darker",
        # "turn the brightness down", "turn brightness down", "turn down the brightness"
        m_bri_dec = re.search(
            r"^(?:decrease|lower|turn\s+down|less|dim|reduce)\s+(?:the\s+|my\s+)?(?:screen\s+brightness|display\s+brightness|brightness|screen|display)(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|screen|display))?$|"
            r"^turn\s+(?:the\s+|my\s+)?(?:mac\s+|screen\s+|display\s+)?brightness\s+(?:down|dimmer|darker|lower)(?:\s+(?:for\s+me|now))?$|"
            r"^make\s+(?:the\s+|my\s+|it\s+)?(?:screen|it|display|brightness)\s+(?:dimmer|darker|less\s+bright)(?:\s+(?:for\s+me|now))?$|"
            r"^(?:brightness\s+down|dimmer|darker)$",
            txt,
        )
        if m_bri_dec:
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_BRIGHTNESS,
                confidence=0.98,
                parameters={"action": "decrease", "step": 10, "target": "system brightness"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_volume_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        if any(q in txt for q in ["how to", "how do i", "how can i", "why", "what does volume mean"]):
            return None

        # 0. Mute / Unmute
        m_vol_mute = re.search(
            r"^(?:mute|silence)(?:\s+(?:the\s+|my\s+)?(?:volume|sound|audio))?(?:\s+(?:of|on|my)?\s*(?:my\s+)?(?:mac|laptop|system|computer))?$",
            txt,
        )
        if m_vol_mute:
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_VOLUME,
                confidence=0.98,
                parameters={"action": "mute", "target": "system volume"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        m_vol_unmute = re.search(
            r"^unmute(?:\s+(?:the\s+|my\s+)?(?:volume|sound|audio))?(?:\s+(?:of|on|my)?\s*(?:my\s+)?(?:mac|laptop|system|computer))?$",
            txt,
        )
        if m_vol_unmute:
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_VOLUME,
                confidence=0.98,
                parameters={"action": "unmute", "target": "system volume"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 1. Status / Get query: "what is the volume", "get volume", "check volume", "volume status"
        if re.search(r"^(?:what\s+is|get|check|show|current)\s+(?:the\s+|my\s+)?(?:mac\s+|laptop\s+|system\s+)?(?:volume|sound|audio)(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|laptop|system))?$|^volume\s+(?:check|status|show)$", txt):
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_VOLUME,
                confidence=0.98,
                parameters={"action": "get", "target": "system volume"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 2. Relative Increase By: "increase volume by 20%", "increase volume by 20"
        m_vol_rel_inc = re.search(
            r"^(?:increase|raise|turn\s+up)\s+(?:the\s+|my\s+)?(?:mac\s+|laptop\s+|system\s+)?(?:volume|sound|audio)\s+by\s+(\d+)(?:\s*(?:percent|%))?(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|laptop|system))?$",
            txt,
        )
        if m_vol_rel_inc:
            step = max(1, min(100, int(m_vol_rel_inc.group(1))))
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_VOLUME,
                confidence=0.98,
                parameters={"action": "increase", "step": step, "is_relative": True, "unit": "percent", "target": "system volume"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 3. Relative Decrease By: "decrease volume by 10%", "lower volume by 20 percent"
        m_vol_rel_dec = re.search(
            r"^(?:decrease|lower|turn\s+down)\s+(?:the\s+|my\s+)?(?:mac\s+|laptop\s+|system\s+)?(?:volume|sound|audio)\s+by\s+(\d+)(?:\s*(?:percent|%))?(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|laptop|system))?$",
            txt,
        )
        if m_vol_rel_dec:
            step = max(1, min(100, int(m_vol_rel_dec.group(1))))
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_VOLUME,
                confidence=0.98,
                parameters={"action": "decrease", "step": step, "is_relative": True, "unit": "percent", "target": "system volume"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 4. Absolute Set / Increase To / Decrease To / Value Expressions:
        # "set volume to 70%", "set volume to 100%", "set volume to 30%", "increase volume to 80%",
        # "increase volume to 70 percent", "make volume 80", "set my Mac volume to 80", "volume 100%", "decrease volume to 30%"
        m_vol_set = re.search(
            r"^(?:(?:set|make|change)\s+(?:the\s+|my\s+)?(?:mac\s+|laptop\s+|system\s+)?(?:volume|sound|audio)\s+(?:to\s+)?(\d+)(?:\s*(?:percent|%))?(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|laptop|system))?|"
            r"(?:set|make)\s+(?:my\s+)?mac\s+volume\s+(?:to\s+)?(\d+)(?:\s*(?:percent|%))?|"
            r"(?:increase|raise|turn\s+up)\s+(?:(?:the\s+|my\s+)?(?:volume|sound|audio)\s+to\s+(\d+)(?:\s*(?:percent|%))?|(\d+)(?:\s*(?:percent|%))\s*(?:the\s+|my\s+)?(?:volume|sound|audio))|"
            r"(?:decrease|lower|turn\s+down)\s+(?:the\s+|my\s+)?(?:volume|sound|audio)\s+to\s+(\d+)(?:\s*(?:percent|%))?|"
            r"(?:volume|sound|audio)\s+(?:to\s+|at\s+)?(\d+)(?:\s*(?:percent|%))?|"
            r"(\d+)(?:\s*(?:percent|%))\s*(?:volume|sound|audio)|"
            r"make\s+(?:the\s+|my\s+|it\s+)?(?:volume|sound|audio)\s+(\d+)(?:\s*(?:percent|%))?)$",
            txt,
        )
        if m_vol_set:
            val_str = next(g for g in m_vol_set.groups() if g is not None)
            val = max(0, min(100, int(val_str)))
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_VOLUME,
                confidence=0.98,
                parameters={"action": "set", "value": val, "unit": "percent", "target": "system volume"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 5. Basic Increase:
        # "increase volume", "now increase volume", "volume up", "turn up volume", "increase my volume", "make it louder", "make volume louder", "louder",
        # "turn the volume up", "turn the sound up", "turn volume up", "increase my Mac volume"
        m_vol_inc = re.search(
            r"^(?:increase|raise|turn\s+up|more)\s+(?:the\s+|my\s+)?(?:mac\s+|laptop\s+|system\s+)?(?:volume|sound|audio)(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|laptop|system))?$|"
            r"^turn\s+(?:the\s+|my\s+)?(?:mac\s+|laptop\s+|system\s+)?(?:volume|sound|audio)\s+(?:up|louder|higher)(?:\s+(?:for\s+me|now))?$|"
            r"^make\s+(?:the\s+|my\s+|it\s+)?(?:volume\s+|sound\s+|audio\s+)?louder(?:\s+(?:for\s+me|now))?$|"
            r"^(?:volume|awaaz|sound)\s+(?:thoda\s+|thodi\s+)?(?:badha\s*do|badhao|tez\s*karo|tez\s*kar\s*do|up\s*karo|up\s*kar\s*do)$|"
            r"^(?:volume\s+up|sound\s+up|audio\s+up|louder)$",
            txt,
        )
        if m_vol_inc:
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_VOLUME,
                confidence=0.98,
                parameters={"action": "increase", "step": 10, "target": "system volume"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 6. Basic Decrease:
        # "decrease volume", "volume down", "turn volume down", "lower volume", "make it quieter", "make it softer", "quieter", "softer",
        # "turn the volume down", "turn the sound down", "turn volume down", "decrease my Mac volume"
        m_vol_dec = re.search(
            r"^(?:decrease|lower|turn\s+down|less|reduce)\s+(?:the\s+|my\s+)?(?:mac\s+|laptop\s+|system\s+)?(?:volume|sound|audio)(?:\s+(?:of|on)\s+(?:my\s+)?(?:mac|laptop|system))?$|"
            r"^turn\s+(?:the\s+|my\s+)?(?:mac\s+|laptop\s+|system\s+)?(?:volume|sound|audio)\s+(?:down|quieter|softer|lower)(?:\s+(?:for\s+me|now))?$|"
            r"^make\s+(?:the\s+|my\s+|it\s+)?(?:volume\s+|sound\s+|audio\s+)?(?:quieter|softer|lower)(?:\s+(?:for\s+me|now))?$|"
            r"^(?:volume|awaaz|sound)\s+(?:thoda\s+|thodi\s+)?(?:kam\s*karo|kam\s*kar\s*do|ghatao|down\s*karo|down\s*kar\s*do)$|"
            r"^(?:volume\s+down|sound\s+down|audio\s+down|softer|quieter)$",
            txt,
        )
        if m_vol_dec:
            return StructuredAction(
                intent=CanonicalIntent.CONTROL_VOLUME,
                confidence=0.98,
                parameters={"action": "decrease", "step": 10, "target": "system volume"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_screenshot_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        """Match screenshot, screen capture, and screen snapshot requests."""
        # 1. Exact / Direct keyword checks
        screenshot_phrases = [
            "take a screenshot",
            "take screenshot",
            "take a screen shot",
            "take screen shot",
            "take screen capture",
            "take a screen capture",
            "capture my screen",
            "capture the screen",
            "capture screen",
            "screenshot this",
            "screen shot this",
            "screen capture this",
            "save what i am seeing",
            "save what im seeing",
            "save what i'm seeing",
            "capture what i am looking at",
            "capture what im looking at",
            "capture what i'm looking at",
            "take a picture of my screen",
            "take a picture of the screen",
            "take picture of my screen",
            "take picture of the screen",
            "take a photo of my screen",
            "take photo of my screen",
            "take a photo of the screen",
            "take photo of the screen",
            "photo of my screen",
            "picture of my screen",
            "save my screen",
            "save the screen",
            "save screen",
            "snap my screen",
            "snap the screen",
            "snap screen",
            "snap a screenshot",
            "snap screenshot",
            "grab my screen",
            "grab the screen",
            "grab screen",
            "grab a screenshot",
            "grab screenshot",
            "take a snapshot of my screen",
            "take a snapshot of the screen",
            "take snapshot of my screen",
            "take snapshot of the screen",
            "snapshot my screen",
            "snapshot the screen",
            "snapshot screen",
            "snapshot this",
            "save current screen",
            "capture current screen",
            "print screen",
            "save what is on my screen",
            "save what's on my screen",
            "capture what is on my screen",
            "capture what's on my screen",
            "screenshot lo",
            "screenshot le lo",
            "screen ka screenshot lo",
            "screen capture karo",
            "screen ki photo lo",
            "screen ki picture lo",
            "screenshot",
            "screen shot",
            "screen capture",
        ]

        if txt in screenshot_phrases:
            return StructuredAction(
                intent=CanonicalIntent.SCREEN_CAPTURE,
                confidence=1.0,
                parameters={"action": "capture_full"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 2. Generalized Regular Expression Matchers
        regex_patterns = [
            r"^(?:take|capture|grab|snap|save|record|get|click)?\s*(?:a\s+|the\s+|my\s+|current\s+)?(?:screenshot|screen\s+shot|screen\s+capture|snapshot)(?:\s+(?:of\s+)?(?:the\s+|my\s+|current\s+)?screen|\s+this|\s+now)?$",
            r"^(?:take|capture|grab|snap|save)\s+(?:a\s+|the\s+)?(?:screen\s+capture|snapshot)(?:\s+(?:of\s+)?(?:the\s+|my\s+|current\s+)?screen|\s+this)?$",
            r"^(?:capture|save|grab|snap)\s+(?:the\s+|my\s+|current\s+)?screen$",
            r"^(?:save|capture)\s+what\s+(?:i\s+am|i\'?m)\s+(?:seeing|looking\s+at)$",
            r"^(?:save|capture)\s+what(?:\'?s|\s+is)\s+(?:on\s+)?(?:the\s+|my\s+)?screen$",
            r"^(?:take|capture|click|get)\s+(?:a\s+|the\s+)?(?:picture|photo|snapshot)\s+of\s+(?:the\s+|my\s+|current\s+)?screen$",
            r"^(?:screenshot|screen\s+shot|screen\s+capture)(?:\s+this|\s+lo|\s+le\s+lo|\s+karo)?$",
        ]

        for pat in regex_patterns:
            if re.search(pat, txt):
                return StructuredAction(
                    intent=CanonicalIntent.SCREEN_CAPTURE,
                    confidence=0.98,
                    parameters={"action": "capture_full"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        return None

    def _match_camera_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # Guard: If command mentions screen, let screenshot matcher handle it
        if "screen" in txt:
            return None

        # 1. Take Photo
        if any(p in txt for p in [
            "take a picture", "take a photo", "take photo", "take picture",
            "take my photo", "take my picture", "click a photo", "click a picture",
            "click photo", "click my photo", "capture photo", "capture a photo",
            "photo kheencho", "tasveer lo", "picture lo"
        ]):
            return StructuredAction(
                intent=CanonicalIntent.TAKE_PHOTO,
                confidence=0.98,
                parameters={"action": "take_photo"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 2. Open Camera
        if txt in [
            "open camera", "launch camera", "start camera", "open the camera", "launch the camera", "start the camera",
            "camera kholo", "camera open karo", "open photo booth", "launch photo booth"
        ]:
            return StructuredAction(
                intent=CanonicalIntent.OPEN_CAMERA,
                confidence=0.98,
                parameters={"action": "open_camera"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_clipboard_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # 1. Clear Clipboard
        if txt in [
            "clear my clipboard", "clear clipboard", "empty my clipboard",
            "empty the clipboard", "clipboard saaf karo", "clear the clipboard"
        ]:
            return StructuredAction(
                intent=CanonicalIntent.CLEAR_CLIPBOARD,
                confidence=0.98,
                parameters={"action": "clear"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 2. Get / Read Clipboard
        if txt in [
            "what is in my clipboard", "what's in my clipboard", "whats in my clipboard",
            "what is on my clipboard", "what's on my clipboard", "whats on my clipboard",
            "show my clipboard", "show clipboard", "get clipboard", "read clipboard",
            "what did i copy", "check clipboard", "clipboard content", "clipboard check karo"
        ]:
            return StructuredAction(
                intent=CanonicalIntent.GET_CLIPBOARD,
                confidence=0.98,
                parameters={"action": "get"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 3. Set / Copy to Clipboard
        m_copy = re.search(r"^(?:copy\s+)(.+?)(?:\s+to\s+clipboard)?$", txt)
        if m_copy and ("clipboard" in txt or txt.startswith("copy ")):
            val = m_copy.group(1).strip()
            if val in ("this", "it", "selection", "selected text"):
                return StructuredAction(
                    intent=CanonicalIntent.SET_CLIPBOARD,
                    confidence=0.95,
                    parameters={"action": "set", "use_context": True},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            elif "to clipboard" in txt:
                return StructuredAction(
                    intent=CanonicalIntent.SET_CLIPBOARD,
                    confidence=0.95,
                    parameters={"action": "set", "text": val},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        return None

    def _match_hardware_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # Guard: Ignore troubleshooting / informational questions / statements about wifi or bluetooth
        troubleshooting_guards = [
            r"\bwhy\b",
            r"\bhow\s+come\b",
            r"\bwhat(?:'s|\s+is)\s+wrong\b",
            r"\bwhat\s+happened\b",
            r"\bnot\s+working\b",
            r"\bisn't\s+working\b",
            r"\bnot\s+connecting\b",
            r"\bisn't\s+connecting\b",
            r"\bwon't\s+connect\b",
            r"\bwont\s+connect\b",
            r"\bdisconnecting\b",
            r"\bkeeps?\b",
            r"\bacting\s+(?:up|weird)\b",
            r"\btroubleshoot\b",
            r"\bproblem\b",
            r"\bissue\b",
            r"\bslow\b",
            r"\bterrible\b",
            r"\bannoying\b",
            r"\bhow\s+does\b",
            r"\btell\s+me\s+about\b",
            r"\btell\s+me\s+why\b",
        ]
        if any(re.search(pat, txt) for pat in troubleshooting_guards):
            return None

        # 1. Wi-Fi Commands
        if any(w in txt for w in ["wifi", "wi-fi", "wi fi"]) or ("network" in txt and any(k in txt for k in ["what", "which", "check", "connected", "status", "am i", "ip", "details", "info"])) or any(w in txt for w in ["local ip", "wifi ip", "connected to the internet", "internet status", "am i connected to the internet"]):
            # Power ON
            if any(k in txt for k in ["turn on", "turn wifi on", "turn wi-fi on", "enable", "chalu", "start", "on karo", "switch on", "switch wifi on", "switch wi-fi on"]) or txt in ["wifi on", "wi-fi on"]:
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_WIFI,
                    confidence=0.98,
                    parameters={"action": "on", "target": "wifi"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            # Power OFF
            if any(k in txt for k in ["turn off", "turn wifi off", "turn wi-fi off", "disable", "band", "stop", "off karo", "switch off", "switch wifi off", "switch wi-fi off"]) or txt in ["wifi off", "wi-fi off"]:
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_WIFI,
                    confidence=0.98,
                    parameters={"action": "off", "target": "wifi"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            # Full Network Details / IP / Internet query
            if any(k in txt for k in ["ip", "local ip", "wifi ip", "network status", "gateway", "interface", "internet status", "internet", "details"]):
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_WIFI,
                    confidence=0.98,
                    parameters={"action": "details", "target": "wifi"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            # Specific SSID / Network Name query
            if any(k in txt for k in ["what wifi", "which wifi", "what network", "which network", "connected to", "current wifi", "current network", "am i connected to wifi", "am i connected to a network"]):
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_WIFI,
                    confidence=0.98,
                    parameters={"action": "ssid", "target": "wifi"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            # Explicit status check
            if (
                any(k in txt or k in raw.lower() for k in ["status", "check", "state", "tell me my wifi", "what's my wifi", "whats my wifi"])
                or re.search(r"\b(?:is\s+(?:the\s+|my\s+)?wi-?fi\s+(?:on|connected|working)|wi-?fi\s+(?:state|status|check|on\s+or\s+off))\b", txt)
                or re.search(r"\bwi-?fi\b.*\b(?:on\s+or\s+off|turned\s+on)\b", txt)
                or re.search(r"\bis\s+(?:my\s+|the\s+)?wi-?fi\s+on\b", txt)
            ):
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_WIFI,
                    confidence=0.95,
                    parameters={"action": "status", "target": "wifi"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            return None

        # 2. Bluetooth Commands
        if "bluetooth" in txt or any(w in txt for w in ["airpods connected", "bluetooth device", "bluetooth devices"]):
            # Power ON
            if any(k in txt for k in ["turn on", "turn bluetooth on", "enable", "chalu", "start", "on karo", "switch on", "switch bluetooth on", "connect bluetooth"]) or txt in ["bluetooth on"]:
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_BLUETOOTH,
                    confidence=0.98,
                    parameters={"action": "on", "target": "bluetooth"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            # Power OFF
            if any(k in txt for k in ["turn off", "turn bluetooth off", "disable", "band", "stop", "off karo", "switch off", "switch bluetooth off", "disconnect bluetooth"]) or txt in ["bluetooth off"]:
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_BLUETOOTH,
                    confidence=0.98,
                    parameters={"action": "off", "target": "bluetooth"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            # Connected Devices query
            if any(k in txt for k in ["device", "devices", "airpods", "headphones", "what is connected", "who is connected", "which is connected", "connected to bluetooth", "connected through bluetooth", "what devices", "which devices"]):
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_BLUETOOTH,
                    confidence=0.98,
                    parameters={"action": "devices", "target": "bluetooth"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            # Explicit status check
            if (
                any(k in txt for k in ["status", "check", "state", "what's my bluetooth", "whats my bluetooth", "tell me bluetooth"])
                or re.search(r"\b(?:is\s+(?:the\s+|my\s+)?bluetooth\s+(?:on|connected|working)|bluetooth\s+(?:state|status|check|on\s+or\s+off))\b", txt)
                or re.search(r"\bbluetooth\b.*\b(?:on\s+or\s+off|turned\s+on)\b", txt)
                or re.search(r"\bis\s+(?:my\s+|the\s+)?bluetooth\s+on\b", txt)
            ):
                return StructuredAction(
                    intent=CanonicalIntent.CONTROL_BLUETOOTH,
                    confidence=0.95,
                    parameters={"action": "status", "target": "bluetooth"},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            return None

        return None

    def _match_screen_recording(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # STOP RECORDING PATTERNS
        stop_phrases = [
            "stop recording",
            "stop screen recording",
            "stop screenrecording",
            "stop the screen recording",
            "stop the screenrecording",
            "stop recording my screen",
            "stop recording the screen",
            "end screen recording",
            "end screenrecording",
            "end recording",
            "finish recording my screen",
            "finish screen recording",
            "finish screenrecording",
            "finish recording",
            "recording roko",
            "screen recording band karo",
            "recording band karo",
        ]
        if any(txt == p or re.search(rf"^(?:can you\s+|please\s+)?{re.escape(p)}$", txt) for p in stop_phrases) or re.search(
            r"^(?:stop|end|finish|terminate|cancel|halt)\s+(?:the\s+)?(?:screen\s*recording|recording(?:\s+(?:my\s+|the\s+)?screen)?)$",
            txt,
        ) or re.search(
            r"^(?:stop|end|finish)\s+recording\s+(?:my\s+|the\s+)?screen$",
            txt,
        ):
            return StructuredAction(
                intent=CanonicalIntent.STOP_SCREEN_RECORDING,
                confidence=1.0,
                raw_input=raw,
                normalized_input=norm_text,
            )

        # START RECORDING PATTERNS
        start_phrases = [
            "record screen",
            "record the screen",
            "start screen recording",
            "start screenrecording",
            "start recording the screen",
            "start recording my screen",
            "record my screen",
            "begin screen recording",
            "begin recording my screen",
            "capture my screen as video",
            "capture screen as video",
            "capture screen video",
            "start recording",
            "record what i am doing",
            "record what i'm doing",
            "screen record",
            "screenrecord",
            "screenrecording",
            "take screen recording",
            "take screenrecording",
            "screen recording shuru karo",
            "screen record karo",
        ]
        if any(txt == p or re.search(rf"^(?:can you\s+|please\s+)?{re.escape(p)}$", txt) for p in start_phrases) or re.search(
            r"^(?:start|begin|initiate|launch)\s+(?:a\s+|the\s+)?(?:screen\s*recording|recording\s+(?:my\s+|the\s+)?screen|recording)$",
            txt,
        ) or re.search(
            r"^(?:record|capture)\s+(?:my\s+|the\s+)?screen(?:\s+as\s+video)?$",
            txt,
        ) or re.search(
            r"^(?:record|capture)\s+what\s+(?:i\s+am|i\'?m)\s+doing$",
            txt,
        ) or re.search(
            r"^(?:i\s+want\s+to|i\'?d\s+like\s+to|can\s+you)\s+(?:record|capture)\s+(?:my\s+|the\s+)?screen$",
            txt,
        ):
            return StructuredAction(
                intent=CanonicalIntent.START_SCREEN_RECORDING,
                confidence=1.0,
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_screen_awareness(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        patterns = [
            r"^(?:what\s+(?:am\s+i|are\s+we)\s+looking\s+at|what\s+is\s+on\s+(?:my\s+)?screen|explain\s+(?:my\s+)?screen|what\'?s\s+on\s+(?:my\s+)?screen)$",
            r"^(?:screen\s+pe\s+kya\s+hai|kya\s+chal\s+raha\s+hai|yeh\s+kya\s+hai)$",
        ]
        for pat in patterns:
            if re.search(pat, txt):
                return StructuredAction(
                    intent=CanonicalIntent.WHAT_AM_I_LOOKING_AT,
                    confidence=0.98,
                    raw_input=raw,
                    normalized_input=norm_text,
                )
        return None

    def _match_error_explanation(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        patterns = [
            r"^(?:what\s+error\s+is\s+(?:on\s+my\s+screen|showing)|explain\s+(?:this\s+)?error|what\'?s\s+this\s+error)$",
            r"^(?:kya\s+error\s+hai|error\s+samjhao|yeh\s+error\s+kya\s+hai)$",
        ]
        for pat in patterns:
            if re.search(pat, txt):
                return StructuredAction(
                    intent=CanonicalIntent.EXPLAIN_SCREEN_ERROR,
                    confidence=0.98,
                    raw_input=raw,
                    normalized_input=norm_text,
                )
        return None

    def _match_popup_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        patterns = [
            r"^(?:close|dismiss|hatao|band\s+karo)\s+(?:this\s+|the\s+)?(?:popup|dialog|modal|sheet|alert)$",
            r"^(?:popup|dialog)\s+(?:band\s+karo|hatao|close\s+karo)$",
        ]
        for pat in patterns:
            if re.search(pat, txt):
                return StructuredAction(
                    intent=CanonicalIntent.CLOSE_POPUP,
                    confidence=0.98,
                    raw_input=raw,
                    normalized_input=norm_text,
                )
        return None

    def _match_scroll_until_visible(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        m = re.search(r"^scroll\s+(?:down\s+)?until\s+you\s+find\s+(.+)$", txt)
        if m:
            target = m.group(1).strip()
            return StructuredAction(
                intent=CanonicalIntent.SCROLL_UNTIL_VISIBLE,
                confidence=0.98,
                parameters={"target_text": target},
                raw_input=raw,
                normalized_input=norm_text,
            )
        return None

    def _match_ui_typing(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        m_type = re.search(r"^(?:type|enter|write\s+text)\s+(.+?)(?:\s+in\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+))?$", txt)
        if m_type and not any(w in txt for w in ["application", "code", "file", "leave", "email", "letter", "python", "c++"]):
            text_val = m_type.group(1).strip()
            target_field = m_type.group(2).strip() if m_type.group(2) else None
            # Strip quotes if present
            text_val = text_val.strip("\"'")
            return StructuredAction(
                intent=CanonicalIntent.TYPE_UI_TEXT,
                confidence=0.95,
                parameters={"text": text_val, "target_label": target_field, "submit": False},
                raw_input=raw,
                normalized_input=norm_text,
            )
        return None

    def _match_ui_clicking(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # Exclude specific non-UI actions like "click picture" or "open app"
        if any(w in txt for w in ["picture", "photo", "tab", "folder", "app", "application", "shorts", "website", "leave application", "vs code"]):
            return None

        # Standalone action words ("Search", "Submit", "Login")
        if txt in ("search", "submit", "login", "sign in", "sign up", "download", "enter"):
            return StructuredAction(
                intent=CanonicalIntent.CLICK_UI_ELEMENT,
                confidence=0.92,
                parameters={"target_label": txt, "raw_target": txt},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # "Click search", "Click login", "Click the login button", "Click the second result", "Select C++", "Open the download menu", "Find the download button"
        patterns = [
            r"^(?:click|press|tap)\s+(?:on\s+)?(?:the\s+)?(.+?)(?:\s+button|\s+link|\s+icon)?$",
            r"^(?:select|choose)\s+(?:the\s+)?(.+?)$",
            r"^open\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)\s+menu$",
            r"^find\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)\s+button$",
        ]
        for pat in patterns:
            m = re.search(pat, txt)
            if m:
                target = m.group(1).strip()
                if target and target not in ("this", "that", "it", "here"):
                    return StructuredAction(
                        intent=CanonicalIntent.CLICK_UI_ELEMENT,
                        confidence=0.92,
                        parameters={"target_label": target, "raw_target": target},
                        raw_input=raw,
                        normalized_input=norm_text,
                    )
        return None

    def _match_delete_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        m_del = re.search(
            r"^(?:please\s+)?(?:delete|remove|trash|hatao|delete\s+karo)\s+(?:my\s+|the\s+)?(.+?)(?:\s+from\s+(?:the\s+|my\s+)?(desktop|documents|downloads))?$",
            txt,
        )
        if m_del:
            target = m_del.group(1).strip()
            loc = m_del.group(2).strip() if m_del.group(2) else ""
            for suffix in [" folder", " directory", " file"]:
                if target.endswith(suffix):
                    target = target[:-len(suffix)].strip()

            if target in ["this", "that", "it", "the selected file", "this file", "this folder"]:
                ctx = environment_observer.get_context()
                target_res = ContextResolver.resolve_target("this", ctx, target_type="any")
                return StructuredAction(
                    intent=CanonicalIntent.DELETE_ITEM,
                    confidence=0.95,
                    parameters={
                        "target_path": str(target_res["target"]) if target_res["resolved"] else None,
                        "target_description": target_res["description"],
                        "requires_confirmation": True,
                    },
                    raw_input=raw,
                    normalized_input=norm_text,
                )
            elif target and target not in ("recording", "screen recording", "nova tabs", "tabs", "tab"):
                return StructuredAction(
                    intent=CanonicalIntent.DELETE_ITEM,
                    confidence=0.95,
                    parameters={"target_name": target, "location": loc, "requires_confirmation": True},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
        return None

    def _match_document_writing(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        if any(q in txt for q in ["how to write", "how do i write", "how can i write", "why write"]):
            return None

        m = re.search(
            r"^(?:open\s+(?:the\s+)?(?:notepad|textedit|text\s+editor)\s+and\s+)?write\s+(?:a\s+|an\s+)?(.+?)(?:\s+in\s+notepad|\s+in\s+textedit)?$",
            txt,
        )
        if m:
            topic = m.group(1).strip()
            # If topic ends with "in notepad" or "in textedit", strip it and resolve destination
            dest = "Notepad/TextEdit"
            m_trailing_dest = re.search(r"\s+in\s+(notepad|textedit|text\s+editor)$", topic, re.IGNORECASE)
            if m_trailing_dest:
                d_str = m_trailing_dest.group(1).lower()
                dest = "TEXTEDIT" if "textedit" in d_str else "NOTEPAD"
                topic = topic[:m_trailing_dest.start()].strip()
            elif "in notepad" in txt:
                dest = "NOTEPAD"
            elif "in textedit" in txt:
                dest = "TEXTEDIT"

            t_lower = topic.lower()
            if "bubble sort" in t_lower:
                fname = "bubble_sort.cpp" if "c++" in t_lower or "cpp" in t_lower else ("bubble_sort.py" if "python" in t_lower else "bubble_sort.txt")
            elif "reverse" in t_lower and "string" in t_lower:
                fname = "reverse_string.py" if "python" in t_lower else "reverse_string.txt"
            elif "reverse" in t_lower and "array" in t_lower:
                fname = "reverse_array.cpp" if "c++" in t_lower or "cpp" in t_lower else "reverse_array.txt"
            elif "leave" in t_lower:
                fname = "leave_application.txt"
            else:
                clean_name = re.sub(r"[^a-zA-Z0-9_]+", "_", topic)[:20].strip("_") or "notes"
                fname = f"{clean_name}.txt"

            return StructuredAction(
                intent=CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT,
                confidence=0.98,
                parameters={
                    "topic": topic,
                    "content": topic,
                    "filename": fname,
                    "open_in_editor": True,
                    "destination": dest,
                },
                raw_input=raw,
                normalized_input=norm_text,
            )
        return None

    def _match_autonomous_tasks(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # Pattern 1: Folder on Desktop with subfolders / files
        if re.search(r"create\s+(?:a\s+)?(?:folder|project).+?with.+?(?:folders|directories|files|\.cpp|\.html|\.js)", txt):
            return StructuredAction(
                intent=CanonicalIntent.AUTONOMOUS_TASK,
                confidence=0.98,
                parameters={"user_request": raw},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # Pattern 2: Project with multiple files and optional open in VS Code
        if re.search(r"create\s+(?:a\s+)?(?:[a-zA-Z0-9_\-\+]+)\s+project.+", txt) or ("create" in txt and "inside" in txt and ("open" in txt or "vs code" in txt)):
            return StructuredAction(
                intent=CanonicalIntent.AUTONOMOUS_TASK,
                confidence=0.98,
                parameters={"user_request": raw},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # Pattern 3: Search web and save link in file
        if ("find" in txt or "search" in txt) and ("save" in txt or "write" in txt) and ("link" in txt or "file" in txt):
            return StructuredAction(
                intent=CanonicalIntent.AUTONOMOUS_TASK,
                confidence=0.95,
                parameters={"user_request": raw},
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_folder_and_file_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # 1. RENAME FILE / FOLDER ("Rename my DSA folder to DSA Practice", "Rename a.cpp to tree.cpp", "Change the name of Test to TestProject")
        m_rename = re.search(
            r"^(?:rename|change\s+(?:the\s+)?name\s+of)\s+(?:my\s+|the\s+)?(.+?)\s+(?:to|into|as)\s+([a-zA-Z0-9_\-\.\s]+)$",
            txt,
        )
        if m_rename:
            old_name = m_rename.group(1).strip()
            new_name = m_rename.group(2).strip()
            for suffix in [" folder", " directory", " file"]:
                if old_name.endswith(suffix):
                    old_name = old_name[:-len(suffix)].strip()
            return StructuredAction(
                intent=CanonicalIntent.RENAME_ITEM,
                confidence=0.98,
                parameters={"target_name": old_name, "new_name": new_name},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 2. OPEN FILE IN APPLICATION ("Open a.cpp in VS Code", "Open index.html in VS Code", "Open my resume in Preview")
        m_open_in = re.search(
            r"^open\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\-\.]+)\s+in\s+([a-zA-Z0-9_\-\s]+)$",
            txt,
        )
        if m_open_in:
            fname = m_open_in.group(1).strip()
            app = m_open_in.group(2).strip()
            if fname not in ("tab", "new tab", "browser", "folder", "camera", "photo", "screen"):
                return StructuredAction(
                    intent=CanonicalIntent.OPEN_FILE,
                    confidence=0.98,
                    parameters={"filename": fname, "app_name": app},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        # 3. FIND ITEM / WHERE IS ("Find my DSA folder", "Find NOVA_SETUP", "Where is my resume PDF?", "Find a.cpp", "Find my Python files")
        m_find = re.search(
            r"^(?:find\s+(?:and\s+open\s+)?|where\s+is\s+|show\s+me\s+(?:where\s+is\s+)?|locate\s+)(?:my\s+|the\s+)?(.+?)(?:\s+folder|\s+file)?(?:\?)?$",
            txt,
        )
        if m_find:
            query = m_find.group(1).strip()
            is_and_open = "and open" in txt or txt.startswith("show me ")
            if query and not any(w in query for w in ["website", "site", "webpage", "google", "youtube", "weather", "news", "meaning", "tab", "next tab", "previous tab", "new tab"]):
                if is_and_open:
                    if "folder" in txt or query in ["downloads", "desktop", "documents"]:
                        return StructuredAction(
                            intent=CanonicalIntent.OPEN_FOLDER,
                            confidence=0.95,
                            parameters={"target_name": query},
                            raw_input=raw,
                            normalized_input=norm_text,
                        )
                    return StructuredAction(
                        intent=CanonicalIntent.OPEN_FILE,
                        confidence=0.95,
                        parameters={"filename": query},
                        raw_input=raw,
                        normalized_input=norm_text,
                    )
                return StructuredAction(
                    intent=CanonicalIntent.FIND_ITEM,
                    confidence=0.95,
                    parameters={"query": query},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        # 4. CREATE MULTIPLE FILES / SINGLE FILE AT LOCATION
        # "Create three files a.cpp, b.cpp and c.cpp inside Test"
        # "Create index.html, style.css and app.js inside my project folder"
        # "Create a.cpp on Desktop"
        m_create_files_loc = re.search(
            r"^(?:create|make)\s+(?:(?:three|four|five|two|\d+)\s+files?\s+|file\s+|files?\s+)?(.+?)\s+(?:inside|in|on)\s+(?:the\s+|my\s+)?(.+?)(?:\s+folder|\s+directory)?$",
            norm_text,
            re.IGNORECASE,
        )
        if m_create_files_loc:
            files_part = m_create_files_loc.group(1).strip()
            loc_part = m_create_files_loc.group(2).strip()
            tokens = [t.strip().strip(",") for t in re.split(r"[\s,]+|and\s+", files_part) if t.strip() and "." in t]
            if not tokens and ("." in files_part or "python file" in files_part.lower()):
                if "python file" in files_part.lower():
                    m_py = re.search(r"called\s+([a-zA-Z0-9_\-\.]+)", files_part, re.IGNORECASE)
                    tokens = [m_py.group(1).strip()] if m_py else ["main.py"]
                else:
                    tokens = [files_part.replace("called", "").replace("named", "").strip()]

            if tokens and tokens[0].lower() not in ("folder", "directory", "project", "website"):
                on_desktop = loc_part.lower() in ("desktop", "the desktop", "my desktop")
                return StructuredAction(
                    intent=CanonicalIntent.CREATE_DESKTOP_FILE,
                    confidence=0.98,
                    parameters={
                        "file_names": tokens,
                        "filename": tokens[0] if tokens else "",
                        "location": loc_part,
                        "on_desktop": on_desktop,
                        "parent_target": loc_part,
                    },
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        # "Create README.md", "Create index.html", "Create a.cpp"
        m_single_file = re.search(r"^(?:create|make)\s+(?:a\s+)?(?:file\s+(?:called|named)\s+|python\s+file\s+(?:called|named)\s+)?([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)$", norm_text, re.IGNORECASE)
        if m_single_file:
            fname = m_single_file.group(1).strip()
            return StructuredAction(
                intent=CanonicalIntent.CREATE_DESKTOP_FILE,
                confidence=0.95,
                parameters={"file_names": [fname], "filename": fname},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 5. CREATE FOLDER WITH LOCATION
        # "Create a folder called DSA on Desktop", "Make a folder named College in Documents", "Create a folder called Trees inside my DSA folder"
        m_folder_loc = re.search(
            r"^(?:create|make)\s+(?:a\s+|a\s+new\s+)?(?:folder|directory)(?:\s+(?:called|named)\s+([a-zA-Z0-9_\-\s]+?))?\s+(?:on|in|inside)\s+(?:the\s+|my\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+folder|\s+directory)?$",
            norm_text,
            re.IGNORECASE,
        )
        if m_folder_loc:
            fname = m_folder_loc.group(1).strip() if m_folder_loc.group(1) else "NewFolder"
            loc = m_folder_loc.group(2).strip()
            on_desktop = loc.lower() in ("desktop", "the desktop", "my desktop")
            return StructuredAction(
                intent=CanonicalIntent.CREATE_DESKTOP_FOLDER,
                confidence=0.98,
                parameters={"folder_name": fname, "location": loc, "on_desktop": on_desktop},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # General Folder Creation ("Create a folder called DSA", "Make a folder named Test")
        m_fld = re.search(
            r"^(?:create|make)\s+(?:a\s+|a\s+new\s+)?(?:folder|directory)\s+(?:called|named)\s+([a-zA-Z0-9_\-\s]+)$",
            norm_text,
            re.IGNORECASE,
        )
        if m_fld:
            fname = m_fld.group(1).strip()
            return StructuredAction(
                intent=CanonicalIntent.CREATE_DESKTOP_FOLDER,
                confidence=0.95,
                parameters={"folder_name": fname, "on_desktop": True},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 6. OPEN FOLDER ("Open my DSA folder", "Open the Downloads folder", "Open DSA folder", "Open it")
        if txt in ["open the folder i just created", "open the created folder", "open it", "open that folder"]:
            ctx = environment_observer.get_context()
            target_res = ContextResolver.resolve_target("it", ctx, target_type="folder")
            return StructuredAction(
                intent=CanonicalIntent.OPEN_FOLDER,
                confidence=0.95,
                parameters={
                    "target_path": str(target_res["target"]) if target_res["resolved"] else None,
                    "target_name": target_res["target"].name if target_res["resolved"] and hasattr(target_res["target"], "name") else "folder",
                    "use_context": True,
                },
                raw_input=raw,
                normalized_input=norm_text,
            )

        m_open_fld = re.search(r"^(?:open|show\s+me)\s+(?:the\s+|my\s+)?([a-zA-Z0-9_\-\s]+?)\s+(?:folder|directory)$", norm_text, re.IGNORECASE)
        if m_open_fld:
            fld_name = m_open_fld.group(1).strip()
            return StructuredAction(
                intent=CanonicalIntent.OPEN_FOLDER,
                confidence=0.95,
                parameters={"target_name": fld_name},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # 7. OPEN FILE ("Open a.cpp", "Open my resume.pdf")
        m_open_file = re.search(r"^open\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)$", norm_text, re.IGNORECASE)
        if m_open_file:
            fname = m_open_file.group(1).strip()
            return StructuredAction(
                intent=CanonicalIntent.OPEN_FILE,
                confidence=0.95,
                parameters={"filename": fname},
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_reminder_intent(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        m_time = re.search(r"(?:at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))|(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+(?:ko|par))", txt)
        if m_time and ("want to" in txt or "remind" in txt or "reminder" in txt or "schedule" in txt or "go to the" in txt):
            time_str = (m_time.group(1) or m_time.group(2)).strip().upper()
            return StructuredAction(
                intent=CanonicalIntent.REMINDER_REQUEST,
                confidence=0.90,
                parameters={"time_str": time_str, "original_request": raw},
                requires_clarification=True,
                clarification_prompt=f"Do you want me to remind you at {time_str}?",
                raw_input=raw,
                normalized_input=norm_text,
            )
        return None

    def _match_shorts_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        if txt in ["play shorts", "open shorts", "show me shorts", "open youtube shorts", "show me youtube shorts", "play youtube shorts", "shorts"]:
            return StructuredAction(
                intent=CanonicalIntent.WATCH_SHORTS,
                confidence=0.98,
                parameters={"platform": "youtube", "query": ""},
                raw_input=raw,
                normalized_input=norm_text,
            )

        m_funny = re.search(r"^(?:play|show|watch|open)\s+(.+?)\s+shorts$", txt)
        if m_funny:
            q = m_funny.group(1).strip()
            if q not in ("youtube", "the", "me"):
                return StructuredAction(
                    intent=CanonicalIntent.WATCH_SHORTS,
                    confidence=0.95,
                    parameters={"platform": "youtube", "query": q},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        return None

    def _match_in_site_search(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # 1. Multi-Action: Open Site/App and Search Query
        # "Go to Flipkart website and search for mobile phones"
        # "Open Google and search DSA roadmap"
        # "Open Amazon and search for headphones"
        # "Go to Flipkart and search mobile phones"
        m_open_search = re.search(
            r"^(?:open|go\s+to|visit|navigate\s+to|bring\s+up)\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+?)(?:\s+website|\s+site|\s+webpage|\s+app|\s+application)?\s+(?:and|\&|then)\s+(?:search\s+(?:for\s+|in\s+)?|find\s+(?:for\s+)?|look\s+for\s+)(.+)$",
            txt,
            re.IGNORECASE,
        )
        if m_open_search:
            site = m_open_search.group(1).strip()
            q = m_open_search.group(2).strip()
            q = re.sub(r"^(?:for\s+|about\s+)", "", q).strip()
            q = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", q).strip()
            if site and q:
                return StructuredAction(
                    intent=CanonicalIntent.SEARCH_WEBSITE,
                    confidence=0.98,
                    parameters={"site": site, "query": q},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        # 2. In-Site Search
        m_in = re.search(r"^in\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+?)(?:\s+website|\s+site|\s+app)?\s+(?:search\s+(?:for\s+)?|find\s+(?:for\s+)?)(.+)$", txt)
        if m_in:
            site = m_in.group(1).strip()
            q = m_in.group(2).strip()
            q = re.sub(r"^(?:for\s+|about\s+)", "", q).strip()
            return StructuredAction(
                intent=CanonicalIntent.SEARCH_WEBSITE,
                confidence=0.98,
                parameters={"site": site, "query": q},
                raw_input=raw,
                normalized_input=norm_text,
            )

        m_search_in = re.search(r"^(?:search|find)\s+(?:for\s+)?(.+?)\s+in\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+?)(?:\s+website|\s+site|\s+app)?$", txt)
        if m_search_in:
            q = m_search_in.group(1).strip()
            site = m_search_in.group(2).strip()
            return StructuredAction(
                intent=CanonicalIntent.SEARCH_WEBSITE,
                confidence=0.98,
                parameters={"site": site, "query": q},
                raw_input=raw,
                normalized_input=norm_text,
            )

        m_here = re.search(r"^(?:search|find)\s+(?:for\s+)?(.+?)\s+(?:here|on\s+this\s+site|on\s+this\s+page)$", txt)
        if m_here:
            q = m_here.group(1).strip()
            return StructuredAction(
                intent=CanonicalIntent.SEARCH_CURRENT_SITE,
                confidence=0.95,
                parameters={"query": q},
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_tab_commands(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # NEXT TAB
        pat_next = r"^(?:go\s+to\s+|switch\s+to\s+|move\s+to\s+|show\s+(?:me\s+)?|open\s+|take\s+me\s+(?:back\s+)?to\s+)?(?:the\s+)?next\s+tab$"
        if re.search(pat_next, txt) or txt in ["next tab", "agla tab", "next tab pe jao"]:
            return StructuredAction(
                intent=CanonicalIntent.NEXT_TAB,
                confidence=0.98,
                parameters={"direction": "next"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # PREVIOUS TAB
        pat_prev = r"^(?:go\s+(?:back\s+)?to\s+|switch\s+(?:back\s+)?to\s+|move\s+(?:back\s+)?to\s+|show\s+(?:me\s+)?|take\s+me\s+(?:back\s+)?to\s+)?(?:the\s+)?(?:previous|prev|last)\s+tab$"
        if re.search(pat_prev, txt) or txt in ["previous tab", "prev tab", "switch back", "go back to the last tab", "pichhla tab", "take me to the previous tab"]:
            return StructuredAction(
                intent=CanonicalIntent.PREVIOUS_TAB,
                confidence=0.98,
                parameters={"direction": "previous"},
                raw_input=raw,
                normalized_input=norm_text,
            )

        # OPEN NEW TAB
        pat_new = r"^(?:open\s+(?:a\s+|the\s+|another\s+)?|create\s+(?:a\s+|the\s+)?|make\s+(?:a\s+|the\s+)?|launch\s+(?:a\s+|the\s+)?)?(?:new\s+tab|another\s+tab)$"
        if re.search(pat_new, txt) or txt in ["open new tab", "new tab please", "new tab", "create new tab", "make a new tab", "open another tab", "can you open a new tab", "open a new tab"]:
            return StructuredAction(
                intent=CanonicalIntent.OPEN_NEW_TAB,
                confidence=0.98,
                raw_input=raw,
                normalized_input=norm_text,
            )

        # CLOSE CURRENT TAB
        if re.search(r"^(?:close|quit|shut|exit)\s+(?:the\s+|this\s+|current\s+|the\s+current\s+)?tab$", txt) or txt in ["close tab", "close current tab", "close this tab", "tab band karo"]:
            return StructuredAction(
                intent=CanonicalIntent.CLOSE_CURRENT_TAB,
                confidence=0.98,
                raw_input=raw,
                normalized_input=norm_text,
            )

        # CLOSE ALL RESEARCH TABS
        if any(txt == p for p in ["close all research tabs", "close research tabs", "close nova tabs"]):
            return StructuredAction(
                intent=CanonicalIntent.CLOSE_NOVA_TABS,
                confidence=0.98,
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_page_understanding(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        pat_read = r"^(?:read|what\s+is\s+written\s+on|tell\s+me\s+what\s+is\s+on|what\s+does\s+this\s+page\s+say|can\s+you\s+read)\s+(?:the\s+|this\s+|my\s+)?(?:current\s+)?(?:page|website|article|screen)$"
        if re.search(pat_read, txt) or txt in ["read this page", "read page", "read the page", "page padho", "what is on this page", "what is written on this page", "read the current page", "what is written on my current page", "what does this page say", "tell me what is on this page", "can you read this website"]:
            return StructuredAction(
                intent=CanonicalIntent.READ_CURRENT_PAGE,
                confidence=0.98,
                raw_input=raw,
                normalized_input=norm_text,
            )

        if txt in ["summarize this page", "summarize the page", "summarize this article", "summarize page"]:
            return StructuredAction(
                intent=CanonicalIntent.SUMMARIZE_CURRENT_PAGE,
                confidence=0.98,
                raw_input=raw,
                normalized_input=norm_text,
            )

        return None

    def _match_scrolling_and_history(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # 1. Scroll to Bottom
        pat_bottom = (
            r"^(?:scroll\s+(?:all\s+the\s+way\s+)?(?:to\s+(?:the\s+)?)?bottom|"
            r"scroll\s+to\s+(?:the\s+)?end|"
            r"go\s+to\s+(?:the\s+)?bottom|"
            r"take\s+me\s+to\s+(?:the\s+)?bottom|"
            r"scroll\s+all\s+the\s+way\s+down|"
            r"scroll\s+to\s+(?:the\s+)?bottom\s+of\s+(?:the\s+)?(?:page|screen)|"
            r"bottom)$"
        )
        if re.search(pat_bottom, txt) or txt in ["scroll to the bottom", "scroll to bottom", "go to bottom", "scroll all the way down", "take me to the bottom"]:
            return StructuredAction(intent=CanonicalIntent.SCROLL_TO_BOTTOM, confidence=0.98, raw_input=raw, normalized_input=norm_text)

        # 2. Scroll to Top
        pat_top = (
            r"^(?:scroll\s+(?:all\s+the\s+way\s+)?(?:to\s+(?:the\s+)?)?top|"
            r"scroll\s+to\s+(?:the\s+)?(?:start|beginning)|"
            r"go\s+to\s+(?:the\s+)?top|"
            r"take\s+me\s+to\s+(?:the\s+)?top|"
            r"scroll\s+all\s+the\s+way\s+up|"
            r"scroll\s+to\s+(?:the\s+)?top\s+of\s+(?:the\s+)?(?:page|screen)|"
            r"top)$"
        )
        if re.search(pat_top, txt) or txt in ["scroll to the top", "scroll to top", "go to top", "scroll all the way up", "take me to the top"]:
            return StructuredAction(intent=CanonicalIntent.SCROLL_TO_TOP, confidence=0.98, raw_input=raw, normalized_input=norm_text)

        # 3. Scroll Down
        pat_down = r"^(?:scroll\s+(?:the\s+page\s+|the\s+screen\s+)?down|scroll\s+down(?:\s+the\s+page|\s+the\s+screen)?|go\s+down|move\s+down|show\s+more|take\s+me\s+lower|scroll\s+a\s+little\s+down|scroll\s+down)$"
        if re.search(pat_down, txt) or txt in ["scroll down", "down", "neeche scroll karo"]:
            return StructuredAction(intent=CanonicalIntent.SCROLL_DOWN, confidence=0.98, raw_input=raw, normalized_input=norm_text)

        # 4. Scroll Up
        pat_up = r"^(?:scroll\s+(?:the\s+page\s+|the\s+screen\s+)?up|scroll\s+up(?:\s+the\s+page|\s+the\s+screen)?|go\s+up|move\s+up|show\s+previous\s+section|scroll\s+a\s+little\s+up|scroll\s+up)$"
        if re.search(pat_up, txt) or txt in ["scroll up", "up", "upar scroll karo"]:
            return StructuredAction(intent=CanonicalIntent.SCROLL_UP, confidence=0.98, raw_input=raw, normalized_input=norm_text)

        if txt in ["go back", "back", "navigate back", "pichhe jao"]:
            return StructuredAction(intent=CanonicalIntent.GO_BACK, confidence=0.98, raw_input=raw, normalized_input=norm_text)

        if txt in ["go forward", "forward", "navigate forward", "aage jao"]:
            return StructuredAction(intent=CanonicalIntent.GO_FORWARD, confidence=0.98, raw_input=raw, normalized_input=norm_text)

        return None

    def _match_ordinal_selection(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        m = re.search(r"^(?:open|click|select)\s+(?:the\s+)?(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th)(?:\s+one|\s+result|\s+link)?$", txt)
        if m:
            ord_map = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5}
            idx = ord_map.get(m.group(1), 1)
            return StructuredAction(
                intent=CanonicalIntent.OPEN_RESULT,
                confidence=0.98,
                parameters={"target_index": idx},
                raw_input=raw,
                normalized_input=norm_text,
            )
        return None

    def _match_media_playback(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # Conversational check guard: "listen to me", "can you listen to me", "can you hear me", "are you listening"
        if re.search(r"^(?:can\s+you\s+)?(?:listen\s+to\s+me|hear\s+me|are\s+you\s+listening)\b", txt, re.IGNORECASE) or txt in ("listen to me", "listen"):
            return None

        # Ignore past-tense or casual conversation mentioning listening
        if re.search(r"\b(?:listened|heard|was\s+listening)\b", txt, re.IGNORECASE):
            return None

        non_media_queries = frozenset({
            "me", "us", "him", "her", "them", "someone", "people", "myself",
            "what i say", "what i am saying", "this", "that", "it", "to me", "to us",
            "shorts", "video", "song", "music", "audio",
        })

        # Multi-Action: "Go to YouTube and play Kesariya", "Open YouTube and play song Mere Liye"
        m_yt_play = re.search(
            r"^(?:open|go\s+to|visit|navigate\s+to)\s+(?:the\s+)?(?:youtube|yt)(?:\s+website|\s+site|\s+app)?\s+(?:and|\&|then)\s+(?:play|watch|listen\s+to)\s+(?:the\s+)?(?:song\s+|video\s+|track\s+|episode\s+)?(.+)$",
            txt,
            re.IGNORECASE,
        )
        if m_yt_play:
            q = m_yt_play.group(1).strip()
            q = re.sub(r"\s+on\s+youtube$", "", q).strip()
            q = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", q).strip()
            if q and q.lower() not in non_media_queries:
                return StructuredAction(
                    intent=CanonicalIntent.PLAY_MEDIA,
                    confidence=0.98,
                    parameters={"platform": "youtube", "query": q},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        m = re.search(r"^(?:play|watch|listen\s+to|i\s+want\s+to\s+(?:watch|listen\s+to|hear))\s+(?:the\s+)?(?:song\s+|video\s+|track\s+|episode\s+)?(.+?)(?:\s+on\s+youtube)?$", txt)
        if m:
            q = m.group(1).strip()
            q = re.sub(r"\s+on\s+youtube$", "", q).strip()
            q = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", q).strip()
            if q and q.lower() not in non_media_queries:
                return StructuredAction(
                    intent=CanonicalIntent.PLAY_MEDIA,
                    confidence=0.98,
                    parameters={"platform": "youtube", "query": q},
                    raw_input=raw,
                    normalized_input=norm_text,
                )
        return None

    def _match_app_launch(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        from desktop.apps import AppLauncher

        # 1. Explicit app requests: "Open YouTube app", "Open Telegram app", "Launch Telegram", "Start Spotify app"
        m_explicit = re.search(r"^(?:open|launch|start|run)\s+(?:the\s+)?(?:my\s+)?(?:app\s+|application\s+)?(.+?)(?:\s+app|\s+application)$", txt)
        if m_explicit:
            app_raw = m_explicit.group(1).strip()
            app_raw = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", app_raw).strip()
            if app_raw and app_raw not in ("camera", "photo", "tab", "website", "folder", "screen recording", "screenrecording", "recording"):
                canonical = AppLauncher.resolve_app_name(app_raw)
                return StructuredAction(
                    intent=CanonicalIntent.LAUNCH_APP,
                    confidence=0.98,
                    parameters={"app_name": canonical, "raw_alias": app_raw, "explicit_app": True},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        # 2. Commands starting with "launch", "start", or "run"
        m_launch = re.search(r"^(?:launch|start|run)\s+(?:the\s+)?(?:my\s+)?(?:app\s+|application\s+)?(.+)$", txt)
        if m_launch:
            app_raw = m_launch.group(1).strip()
            app_raw = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", app_raw).strip()
            if app_raw and app_raw not in ("camera", "photo", "tab", "website", "folder", "screen recording", "screenrecording", "recording", "auto shorts", "shorts"):
                canonical = AppLauncher.resolve_app_name(app_raw)
                return StructuredAction(
                    intent=CanonicalIntent.LAUNCH_APP,
                    confidence=0.98,
                    parameters={"app_name": canonical, "raw_alias": app_raw, "explicit_app": True},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        # 3. Known desktop application aliases or installed apps: "Open VS Code", "Open Chrome", "Open Telegram"
        m_open = re.search(r"^(?:open)\s+(?:the\s+)?(?:my\s+)?(.+)$", txt)
        if m_open:
            candidate = m_open.group(1).strip()
            candidate = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", candidate).strip()
            clean_cand = candidate.lower()

            # Ignore web / folder / tab keywords
            if not any(k in clean_cand for k in ["website", "site", "webpage", "folder", "tab", "camera", "photo", "recording", "screen recording", "screenrecording"]):
                # Check ALIAS_MAP or installed applications
                if clean_cand in AppLauncher.ALIAS_MAP and clean_cand not in ("youtube", "flipkart", "aktu", "amazon"):
                    canonical = AppLauncher.ALIAS_MAP[clean_cand]
                    return StructuredAction(
                        intent=CanonicalIntent.LAUNCH_APP,
                        confidence=0.98,
                        parameters={"app_name": canonical, "raw_alias": candidate, "explicit_app": False},
                        raw_input=raw,
                        normalized_input=norm_text,
                    )
                # Check if installed on system
                installed = AppLauncher.find_installed_app(candidate)
                if installed and clean_cand not in ("youtube", "flipkart", "aktu", "amazon", "github", "google"):
                    canonical = AppLauncher.resolve_app_name(candidate)
                    return StructuredAction(
                        intent=CanonicalIntent.LAUNCH_APP,
                        confidence=0.98,
                        parameters={"app_name": canonical, "raw_alias": candidate, "explicit_app": False},
                        raw_input=raw,
                        normalized_input=norm_text,
                    )

        # 4. Hinglish app launch patterns: "Telegram open kar do", "Telegram open karo", "Telegram kholo"
        m_hinglish = re.search(r"^(.+?)\s+(?:open\s+kar\s+do|open\s+karo|kholo)$", txt)
        if m_hinglish:
            candidate = m_hinglish.group(1).strip()
            candidate = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", candidate).strip()
            clean_cand = candidate.lower()
            if not any(k in clean_cand for k in ["website", "site", "webpage", "folder", "tab", "camera", "photo", "recording"]):
                if clean_cand in AppLauncher.ALIAS_MAP and clean_cand not in ("youtube", "flipkart", "aktu", "amazon"):
                    canonical = AppLauncher.ALIAS_MAP[clean_cand]
                    return StructuredAction(
                        intent=CanonicalIntent.LAUNCH_APP,
                        confidence=0.98,
                        parameters={"app_name": canonical, "raw_alias": candidate, "explicit_app": False},
                        raw_input=raw,
                        normalized_input=norm_text,
                    )
                installed = AppLauncher.find_installed_app(candidate)
                if installed and clean_cand not in ("youtube", "flipkart", "aktu", "amazon", "github", "google"):
                    canonical = AppLauncher.resolve_app_name(candidate)
                    return StructuredAction(
                        intent=CanonicalIntent.LAUNCH_APP,
                        confidence=0.98,
                        parameters={"app_name": canonical, "raw_alias": candidate, "explicit_app": False},
                        raw_input=raw,
                        normalized_input=norm_text,
                    )

        return None

    def _match_app_close(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        from desktop.apps import AppLauncher

        # "Close Sublime Text", "Close Sublime Text app", "Quit VS Code", "Exit Terminal"
        m_close = re.search(r"^(?:close|quit|exit|shut\s+down|terminate|kill)\s+(?:the\s+)?(?:my\s+)?(?:app\s+|application\s+)?(.+?)(?:\s+app|\s+application)?$", txt)
        if m_close:
            app_raw = m_close.group(1).strip()
            app_raw = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", app_raw).strip()
            if app_raw and app_raw not in ("tab", "tabs", "new tab", "window", "browser", "this", "it", "screen", "recording", "screen recording", "screenrecording", "camera", "photo", "popup", "dialog"):
                canonical = AppLauncher.resolve_app_name(app_raw)
                return StructuredAction(
                    intent=CanonicalIntent.CLOSE_APP,
                    confidence=0.98,
                    parameters={"app_name": canonical, "raw_alias": app_raw},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        # Hinglish close: "Telegram band kar do", "Telegram band karo", "Telegram close kar do"
        m_close_h = re.search(r"^(.+?)\s+(?:band\s+kar\s+do|band\s+karo|close\s+kar\s+do|close\s+karo)$", txt)
        if m_close_h:
            app_raw = m_close_h.group(1).strip()
            app_raw = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", app_raw).strip()
            if app_raw and app_raw not in ("tab", "tabs", "new tab", "window", "browser", "this", "it", "screen", "recording"):
                canonical = AppLauncher.resolve_app_name(app_raw)
                return StructuredAction(
                    intent=CanonicalIntent.CLOSE_APP,
                    confidence=0.98,
                    parameters={"app_name": canonical, "raw_alias": app_raw},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        return None

    def _match_search_and_research(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        # In-site explicit: "search flipkart for mobile phones"
        m_site = re.search(r"^search\s+([a-zA-Z0-9_\-\.]+)\s+for\s+(.+)$", txt)
        if m_site:
            site = m_site.group(1).strip()
            if site not in ("the", "google", "web", "internet", "online"):
                return StructuredAction(
                    intent=CanonicalIntent.SEARCH_WEBSITE,
                    confidence=0.95,
                    parameters={"site": site, "query": m_site.group(2).strip()},
                    raw_input=raw,
                    normalized_input=norm_text,
                )

        # Web search variations:
        # "browse the internet and search for most important books"
        # "search the internet for most important books"
        # "search the web for most important books"
        # "browse the web for most important books"
        # "look up most important books online"
        # "look up most important books on the internet"
        # "look up most important books"
        # "search for most important books"
        # "search on google for most important books"
        # "search google for most important books"
        # "google most important books"
        search_patterns = [
            r"^(?:browse\s+(?:the\s+)?(?:internet|web)\s+(?:and\s+)?(?:search\s+for|look\s+up|find)|search\s+(?:the\s+)?(?:internet|web)\s+for|browse\s+(?:the\s+)?(?:internet|web)\s+for)\s+(.+)$",
            r"^(?:look\s+up|search\s+for|search\s+online\s+for|find\s+online|search\s+google\s+for|search\s+on\s+google\s+for|google)\s+(.+?)(?:\s+(?:online|on\s+the\s+web|on\s+the\s+internet|on\s+google))?$",
            r"^(?:look\s+up)\s+(.+?)(?:\s+(?:online|on\s+the\s+web|on\s+the\s+internet|on\s+google))$",
            r"^search\s+(?:for\s+)?(.+)$",
        ]
        for pat in search_patterns:
            m = re.search(pat, txt)
            if m:
                q = m.group(1).strip()
                q = re.sub(r"\s+(?:online|on\s+the\s+web|on\s+the\s+internet|on\s+google)$", "", q).strip()
                if q and q not in ("tab", "tabs", "folder", "camera", "photo", "recording", "screen recording", "screenrecording", "this", "it"):
                    return StructuredAction(
                        intent=CanonicalIntent.SEARCH_WEB,
                        confidence=0.95,
                        parameters={"query": q},
                        raw_input=raw,
                        normalized_input=norm_text,
                    )

        return None

    def _match_website_opening(self, txt: str, raw: str, norm_text: str) -> StructuredAction | None:
        if txt.startswith("http://") or txt.startswith("https://") or txt.startswith("www."):
            return StructuredAction(
                intent=CanonicalIntent.OPEN_WEBSITE,
                confidence=1.0,
                parameters={"target_url": norm_text.strip(), "entity": norm_text.strip()},
                raw_input=raw,
                normalized_input=norm_text,
            )

        if "tab" in txt or any(w in txt for w in ["next tab", "previous tab", "prev tab", "new tab", "folder", "screen recording"]):
            return None

        patterns = [
            r"^(?:open|take\s+me\s+to|go\s+to|go\s+on|visit|navigate\s+to|bring\s+up|find|show\s+(?:me\s+)?(?:the\s+)?website\s+(?:of|for)|find\s+(?:the\s+)?official\s+website\s+(?:of|for)|show\s+(?:me\s+)?(?:the\s+)?official\s+website\s+(?:of|for)|show\s+(?:me\s+)?(?:the\s+)?website\s+(?:of|for))\s+(?:the\s+)?(?:official\s+)?(?:website\s+of\s+|website\s+for\s+|site\s+of\s+|site\s+for\s+)?(.+?)(?:\s+website|\s+site|\s+webpage)?$",
            r"^(?:open|take\s+me\s+to|go\s+to|go\s+on|visit|navigate\s+to|bring\s+up|find)\s+(?:the\s+)?(.+?)(?:\s+website|\s+site|\s+webpage)$",
            r"^show\s+(?:me\s+)?(?:the\s+)?(.+?)\s+(?:website|site|webpage)$",
            r"^(.+?)\s+(?:website\s+kholo|site\s+kholo|website\s+open\s+karo|site\s+open\s+karo)$",
        ]
        for pat in patterns:
            m = re.search(pat, txt)
            if m:
                entity = m.group(1).strip()
                entity = re.sub(r"^(?:the\s+)?(?:official\s+)?(?:website\s+of\s+|website\s+for\s+|site\s+of\s+|site\s+for\s+)?", "", entity).strip()
                entity = re.sub(r"\s+(?:website|site|webpage)$", "", entity).strip()
                entity = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", entity).strip()
                entity = re.sub(r"^the\s+", "", entity).strip()

                if entity and entity not in ("new tab", "tab", "page", "browser", "it", "this", "app", "application", "folder", "camera", "screenshot"):
                    return StructuredAction(
                        intent=CanonicalIntent.OPEN_WEBSITE,
                        confidence=0.95,
                        parameters={"entity": entity, "website_requested": True},
                        raw_input=raw,
                        normalized_input=norm_text,
                    )

        return None
