"""Central Natural Language Intent Engine coordinating normalization, linguistic matching, and AI fallback."""

from __future__ import annotations

import os
from typing import Any
from config.settings import settings
from core.logger import get_logger
from intent.fallback import AIIntentClassifier
from intent.matcher import LinguisticIntentMatcher
from intent.models import CanonicalIntent, StructuredAction
from intent.normalizer import NormalizedInput, TextNormalizer

logger = get_logger(__name__)


def log_intent_diagnostics(action: StructuredAction) -> None:
    """Log structured intent diagnostics and execution plan for every processed command."""
    from intent.router import get_routing_domain
    domain = get_routing_domain(action.intent)

    # Extract target and query if present
    params = action.parameters or {}
    target = params.get("site") or params.get("app_name") or params.get("entity") or params.get("folder_name") or params.get("target_name") or params.get("target_url") or ""
    query = params.get("query") or params.get("text") or ""
    
    # Map executor
    executor_name = {
        "screen_recording": "ScreenRecordingManager",
        "system": "ScreenshotService / MacControlManager" if action.intent == CanonicalIntent.SCREEN_CAPTURE else "SystemManager",
        "browser": "BrowserManager",
        "desktop_app": "AppLauncher",
        "filesystem": "FileSystemManager / DesktopActionManager",
        "document_writing": "DocumentEditor",
        "visual": "ComputerAgent",
        "task_agent": "TaskPlanner / TaskExecutor",
    }.get(domain.value, "GeneralConversation / Chat")

    # Generate action plan description
    plan_lines: list[str] = []
    if action.intent == CanonicalIntent.SEARCH_WEBSITE:
        plan_lines.append(f"1. Open {target or 'target site'}")
        plan_lines.append(f"2. Search \"{query}\"")
    elif action.intent == CanonicalIntent.SEARCH_WEB:
        plan_lines.append(f"1. Open search engine")
        plan_lines.append(f"2. Query \"{query}\"")
    elif action.intent == CanonicalIntent.PLAY_MEDIA:
        plan_lines.append("1. Open YouTube")
        plan_lines.append(f"2. Play media \"{query}\"")
    elif action.intent == CanonicalIntent.LAUNCH_APP:
        plan_lines.append(f"1. Launch application '{target}'")
    elif action.intent == CanonicalIntent.CLOSE_APP:
        plan_lines.append(f"1. Terminate application '{target}'")
    elif action.intent == CanonicalIntent.OPEN_WEBSITE:
        plan_lines.append(f"1. Navigate to website '{target}'")
    elif action.intent == CanonicalIntent.SCREEN_CAPTURE:
        plan_lines.append("1. Capture full screen screenshot")
        plan_lines.append("2. Save to Desktop")
    elif action.intent == CanonicalIntent.START_SCREEN_RECORDING:
        plan_lines.append("1. Start screen recording (screencapture)")
        plan_lines.append("2. Save to ~/Desktop/NOVA Recordings/")
    elif action.intent == CanonicalIntent.STOP_SCREEN_RECORDING:
        plan_lines.append("1. Stop active screen recording")
        plan_lines.append("2. Finalize video file")
    elif action.intent == CanonicalIntent.NEXT_TAB:
        plan_lines.append("1. Switch to next browser tab")
    elif action.intent == CanonicalIntent.PREVIOUS_TAB:
        plan_lines.append("1. Switch to previous browser tab")
    elif action.intent == CanonicalIntent.OPEN_NEW_TAB:
        plan_lines.append("1. Open new browser tab")
    elif action.intent == CanonicalIntent.CLOSE_CURRENT_TAB:
        plan_lines.append("1. Close active browser tab")
    elif action.intent == CanonicalIntent.SCROLL_DOWN:
        plan_lines.append("1. Scroll page down")
    elif action.intent == CanonicalIntent.SCROLL_UP:
        plan_lines.append("1. Scroll page up")
    else:
        plan_lines.append(f"1. Execute canonical action '{action.intent.value}'")

    plan_str = "\n".join(f"  {line}" for line in plan_lines)
    entities_str = f"Target: \"{target}\", Query: \"{query}\"" if (target or query) else "(none)"

    logger.info(
        "\n====================================================\n"
        "🔍 NOVA COMMAND TRACE\n"
        "RAW TRANSCRIPT:       \"%s\"\n"
        "PREPROCESSED COMMAND: \"%s\"\n"
        "DETECTED INTENT:      %s\n"
        "EXTRACTED ENTITIES:   %s\n"
        "CANONICAL ACTION:     %s\n"
        "EXECUTOR SELECTED:    %s\n"
        "FINAL ACTION PLAN:\n%s\n"
        "====================================================",
        action.raw_input,
        action.normalized_input,
        action.intent.value,
        entities_str,
        action.intent.value,
        executor_name,
        plan_str,
    )


class NaturalLanguageIntentEngine:
    """Multi-layer intent classification system converting natural spoken phrases into structured canonical actions."""

    def __init__(self) -> None:
        self.normalizer = TextNormalizer()
        self.matcher = LinguisticIntentMatcher()
        self.ai_classifier = AIIntentClassifier()

    def parse(
        self,
        text: str,
        allow_ai_fallback: bool = True,
        candidates: list[str] | None = None,
    ) -> StructuredAction:
        """Parse natural speech input through the 5-layer understanding pipeline, optionally evaluating N-best candidates."""
        if not text or not text.strip():
            return StructuredAction(
                intent=CanonicalIntent.GENERAL_CONVERSATION,
                confidence=1.0,
                raw_input=text,
                normalized_input="",
            )

        # If alternative candidates provided, check if primary or any alternative resolves to a structured action
        all_candidates = [text]
        if candidates:
            for c in candidates:
                if c and c.strip() and c not in all_candidates:
                    all_candidates.append(c)

        # Layer 1: Normalization & Preprocessing of primary text
        norm: NormalizedInput = self.normalizer.normalize(text)
        if not norm.cleaned_lower:
            return StructuredAction(
                intent=CanonicalIntent.GENERAL_CONVERSATION,
                confidence=1.0,
                raw_input=text,
                normalized_input="",
            )

        # Layer 2 & 3: Fast Linguistic Pattern & Semantic Paraphrase Matching
        matched_action = self.matcher.match(norm)
        if matched_action and matched_action.confidence >= 0.85:
            log_intent_diagnostics(matched_action)
            return matched_action

        # If primary candidate was ambiguous or conversational, test other hypotheses
        if len(all_candidates) > 1:
            for cand in all_candidates[1:]:
                cand_norm = self.normalizer.normalize(cand)
                cand_action = self.matcher.match(cand_norm)
                if cand_action and cand_action.confidence >= 0.85 and cand_action.intent != CanonicalIntent.GENERAL_CONVERSATION:
                    cand_action.raw_input = text
                    log_intent_diagnostics(cand_action)
                    return cand_action

        # If matched with medium confidence, or no deterministic match
        if matched_action and matched_action.confidence >= 0.50:
            log_intent_diagnostics(matched_action)
            return matched_action

        # Check if text is obviously general conversation without action verbs
        action_indicators = [
            "tab", "page", "website", "scroll", "open", "launch", "start", "run",
            "play", "close", "quit", "exit", "search", "browse", "shut", "stop",
            "cancel", "mute", "unmute", "volume", "sound", "audio", "brightness",
            "dim", "brighter", "dimmer", "darker", "record", "screenshot", "capture",
            "wifi", "bluetooth", "clipboard", "type", "click", "write", "create",
            "delete", "lock", "camera", "photo", "restart",
        ]
        has_action_keyword = any(k in norm.cleaned_lower for k in action_indicators)

        if not has_action_keyword or not allow_ai_fallback:
            conv_action = StructuredAction(
                intent=CanonicalIntent.GENERAL_CONVERSATION,
                confidence=1.0,
                raw_input=norm.raw,
                normalized_input=norm.normalized,
            )
            log_intent_diagnostics(conv_action)
            return conv_action

        # Layer 4: Structured AI Classification Fallback
        logger.debug("Routing ambiguous input to Layer 4 AI Intent Classifier: '%s'", norm.normalized)
        ai_action = self.ai_classifier.classify(norm)
        log_intent_diagnostics(ai_action)
        return ai_action
