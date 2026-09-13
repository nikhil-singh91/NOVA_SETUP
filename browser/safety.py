"""Permission and confirmation logic for sensitive browser operations."""

from __future__ import annotations

import re

from core.logger import get_logger

from browser.models import BrowserActionPlan

logger = get_logger(__name__)

# Keywords that indicate sensitive, irreversible, or financial operations
SENSITIVE_KEYWORDS = {
    "buy",
    "purchase",
    "checkout",
    "pay",
    "order now",
    "delete account",
    "delete post",
    "remove item",
    "transfer money",
    "send payment",
    "change password",
    "enter card",
    "credit card",
    "cvv",
    "download exe",
    "download file",
    "install software",
    "submit payment",
    "send message",
    "post message",
}


class BrowserSafetyPolicy:
    """Evaluates browser actions for safety, sensitivity, and confirmation requirements."""

    @classmethod
    def evaluate(cls, plan: BrowserActionPlan) -> BrowserActionPlan:
        """Inspect the plan and set confirmation flags if sensitive."""
        query_lower = (plan.query or "").lower().strip()
        raw_lower = (plan.raw_prompt or "").lower().strip()
        combined = f"{query_lower} {raw_lower}"

        # 1. Check for sensitive financial or destructive keywords
        for keyword in SENSITIVE_KEYWORDS:
            if re.search(r"\b" + re.escape(keyword) + r"\b", combined):
                plan.is_sensitive = True
                plan.requires_confirmation = True
                plan.confirmation_prompt = (
                    f"Boss, this action involves '{keyword}' which may have financial or permanent consequences. "
                    "Are you sure you want me to proceed?"
                )
                logger.warning(
                    "Sensitive browser action detected (%s) for query: '%s'",
                    keyword,
                    plan.raw_prompt,
                )
                return plan

        # Public navigation, searches, and media playback are safe
        plan.is_sensitive = False
        plan.requires_confirmation = False
        return plan
