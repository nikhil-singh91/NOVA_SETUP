"""Structured AI fallback classifier for ambiguous or complex natural language actions."""

from __future__ import annotations

import json
import re
from typing import Any

from core.logger import get_logger
from core.registry import registry
from intent.models import CanonicalIntent, StructuredAction
from intent.normalizer import NormalizedInput

logger = get_logger(__name__)


class AIIntentClassifier:
    """Invokes AI reasoning models to classify complex or ambiguous speech inputs into validated structured actions."""

    ALLOWED_INTENTS = [i.value for i in CanonicalIntent if i != CanonicalIntent.GENERAL_CONVERSATION]

    SYSTEM_PROMPT = f"""You are NOVA's Intent Classification Engine.
Your task is to classify the user's natural spoken input into one of the allowed canonical action intents and extract parameters.

ALLOWED INTENTS:
{json.dumps(ALLOWED_INTENTS, indent=2)}

RULES:
1. Output ONLY a valid JSON object. No other text or markdown formatting.
2. If the user input is a general conversational chat, coding question, or greeting, return intent: "general_conversation" with confidence: 1.0.
3. If the user is expressing a clear action intent, pick the matching canonical intent and extract parameters.
4. If the intent is ambiguous (e.g. "Take me back" could mean previous page or previous tab), set confidence to 0.4 and specify a clarification prompt.

JSON SCHEMA:
{{
  "intent": "<canonical_intent_name>",
  "confidence": <float between 0.0 and 1.0>,
  "parameters": {{}},
  "requires_clarification": <bool>,
  "clarification_prompt": "<string or null>"
}}
"""

    def classify(self, norm: NormalizedInput) -> StructuredAction:
        """Call AI provider to classify ambiguous query."""
        if not registry.exists("provider_manager"):
            logger.debug("Provider manager unavailable for AI fallback.")
            return StructuredAction(
                intent=CanonicalIntent.GENERAL_CONVERSATION,
                confidence=0.5,
                raw_input=norm.raw,
                normalized_input=norm.normalized,
            )

        try:
            provider_mgr = registry.get("provider_manager")
            user_prompt = f"User Spoken Input: \"{norm.normalized}\""
            full_prompt = f"{self.SYSTEM_PROMPT}\n\n{user_prompt}"

            res = provider_mgr.generate(full_prompt)
            if not res or not res.text:
                return StructuredAction(
                    intent=CanonicalIntent.GENERAL_CONVERSATION,
                    confidence=0.5,
                    raw_input=norm.raw,
                    normalized_input=norm.normalized,
                )

            clean_json_str = res.text.strip()
            # Remove potential markdown code blocks
            clean_json_str = re.sub(r"^```json\s*", "", clean_json_str)
            clean_json_str = re.sub(r"\s*```$", "", clean_json_str)

            data = json.loads(clean_json_str)
            raw_intent = data.get("intent", "").lower().strip()
            confidence = float(data.get("confidence", 0.7))
            params = data.get("parameters", {})
            requires_clarification = bool(data.get("requires_clarification", False))
            clarification_prompt = data.get("clarification_prompt")

            # Validate against CanonicalIntent enum
            if raw_intent in [i.value for i in CanonicalIntent]:
                matched_intent = CanonicalIntent(raw_intent)
            else:
                matched_intent = CanonicalIntent.GENERAL_CONVERSATION

            return StructuredAction(
                intent=matched_intent,
                confidence=confidence,
                parameters=params if isinstance(params, dict) else {},
                raw_input=norm.raw,
                normalized_input=norm.normalized,
                requires_clarification=requires_clarification,
                clarification_prompt=clarification_prompt,
            )

        except Exception as exc:
            logger.debug("AI fallback classification failed: %s", exc)
            return StructuredAction(
                intent=CanonicalIntent.GENERAL_CONVERSATION,
                confidence=0.5,
                raw_input=norm.raw,
                normalized_input=norm.normalized,
            )
