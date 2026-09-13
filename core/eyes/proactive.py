"""Proactive Computer Awareness and Assistance Engine for NOVA Eyes.

Evaluates current computer state to identify high-value opportunities to offer
assistance (e.g. comparing visible shopping items, identifying visible terminal errors)
with strict privacy guardrails, cooldown timers, and non-intrusive, friend-like phrasing.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.eyes.state import PageCategory, ScreenState
from core.logger import get_logger

logger = get_logger(__name__)


class ProactiveTriggerType(str, Enum):
    """Classification of the proactive opportunity detected."""

    SHOPPING_COMPARISON = "shopping_comparison"
    ERROR_ALERT = "error_alert"
    SEARCH_FOLLOWUP = "search_followup"
    DOCS_NAVIGATION = "docs_navigation"


@dataclass
class ProactiveOpportunity:
    """A qualified suggestion to speak or offer assistance to the user."""

    trigger_type: ProactiveTriggerType
    confidence: float
    spoken_suggestion_en: str
    spoken_suggestion_hi: str
    context_data: dict[str, Any]
    timestamp: float = 0.0

    def get_spoken_text(self, is_hinglish: bool = False) -> str:
        return self.spoken_suggestion_hi if is_hinglish else self.spoken_suggestion_en


class ProactiveAssistanceEngine:
    """Evaluates real-time ScreenState and generates gentle, non-creepy assistance offers."""

    def __init__(
        self,
        cooldown_seconds: float = 120.0,
        min_confidence: float = 0.85,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.min_confidence = min_confidence
        self._lock = threading.Lock()
        self._last_trigger_time: float = 0.0
        self._last_trigger_type: ProactiveTriggerType | None = None
        self._last_context_signature: str = ""

    def evaluate_state(self, state: ScreenState) -> ProactiveOpportunity | None:
        """Inspect current ScreenState and determine if proactive assistance is appropriate."""
        if state is None:
            return None

        # 1. Privacy guardrail: NEVER proactively trigger on sensitive or authentication screens
        if state.contains_sensitive_data or state.page_category == PageCategory.AUTH_LOGIN:
            logger.debug("Proactive engine suppressed: sensitive/auth screen detected.")
            return None

        now = time.time()
        with self._lock:
            # 2. Cooldown guardrail: enforce minimum gap between proactive remarks
            if (now - self._last_trigger_time) < self.cooldown_seconds:
                return None

        # 3. Shopping Comparison Opportunity
        if state.page_category == PageCategory.SHOPPING and len(state.product_candidates) >= 2:
            candidates = state.product_candidates
            sig = f"shopping_{candidates[0].title[:15]}_{candidates[1].title[:15]}"
            with self._lock:
                if sig == self._last_context_signature:
                    return None

            p_type = "products"
            win_low = state.active_window.lower()
            if "shoe" in win_low or any("shoe" in p.title.lower() for p in candidates):
                p_type = "shoes"
            elif "laptop" in win_low or any("laptop" in p.title.lower() for p in candidates):
                p_type = "laptops"
            elif "phone" in win_low or any("phone" in p.title.lower() for p in candidates):
                p_type = "phones"

            en = f"I can see you're comparing {p_type}. Want me to compare the visible ones and tell you which looks better?"
            hi = f"Main dekh sakta hoon aap {p_type} compare kar rahe ho. Kya main screen par visible options ko compare karoon?"

            opp = ProactiveOpportunity(
                trigger_type=ProactiveTriggerType.SHOPPING_COMPARISON,
                confidence=0.90,
                spoken_suggestion_en=en,
                spoken_suggestion_hi=hi,
                context_data={
                    "product_count": len(candidates),
                    "product_type": p_type,
                    "products": [p.title for p in candidates[:3]],
                },
                timestamp=now,
            )

            with self._lock:
                self._last_trigger_time = now
                self._last_trigger_type = ProactiveTriggerType.SHOPPING_COMPARISON
                self._last_context_signature = sig

            logger.info("Proactive opportunity identified: shopping comparison for %s", p_type)
            return opp

        # 4. Critical Error Encountered
        if state.errors and len(state.errors) > 0:
            err = state.errors[0]
            sig = f"error_{err[:30]}"
            with self._lock:
                if sig == self._last_context_signature:
                    return None

            en = f"I noticed an error message in {state.active_application}. Want me to take a look and help resolve it?"
            hi = f"{state.active_application} mein ek error dikha hai. Kya main ise check karke fix karne mein help karoon?"

            opp = ProactiveOpportunity(
                trigger_type=ProactiveTriggerType.ERROR_ALERT,
                confidence=0.88,
                spoken_suggestion_en=en,
                spoken_suggestion_hi=hi,
                context_data={"error": err, "app": state.active_application},
                timestamp=now,
            )

            with self._lock:
                self._last_trigger_time = now
                self._last_trigger_type = ProactiveTriggerType.ERROR_ALERT
                self._last_context_signature = sig

            logger.info("Proactive opportunity identified: error in %s", state.active_application)
            return opp

        return None

    def reset_cooldown(self) -> None:
        """Reset cooldown timer for testing or immediate user action."""
        with self._lock:
            self._last_trigger_time = 0.0
            self._last_context_signature = ""
