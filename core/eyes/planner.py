"""Natural language target resolution and action planning for NOVA Eyes.

Maps high-level user commands and natural intent to precise SemanticElements
extracted dynamically from Accessibility and Vision OCR, scoring candidates
with synonym expansion, ordinals, and spatial relationships.
Zero hardcoded coordinates.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

from core.eyes.accessibility import SemanticElement, UIElementType
from core.eyes.state import ScreenState
from core.logger import get_logger

logger = get_logger(__name__)


class ActionType(str, Enum):
    """Types of dynamic actions NOVA Eyes can plan and execute."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE_TEXT = "type_text"
    SCROLL = "scroll"
    SCROLL_UNTIL_VISIBLE = "scroll_until_visible"
    CLOSE_POPUP = "close_popup"
    PRESS_KEY = "press_key"
    HOVER = "hover"
    EXPLAIN_SCREEN = "explain_screen"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


SYNONYM_GROUPS: dict[str, list[str]] = {
    "search": ["search", "find", "query", "explore", "lookup", "glass", "khojo", "dhoondo"],
    "login": ["login", "sign in", "signin", "log in", "enter account", "logon"],
    "submit": ["submit", "send", "done", "enter", "go", "proceed", "apply"],
    "close": ["close", "dismiss", "cancel", "x", "cross", "exit", "abort", "band karo", "hatao"],
    "download": ["download", "get", "install", "save"],
    "next": ["next", "continue", "forward", "more", "aage"],
    "previous": ["previous", "back", "prev", "piche"],
    "play": ["play", "start", "resume", "chalao"],
    "pause": ["pause", "stop", "rok"],
    "cart": ["cart", "bag", "basket", "checkout"],
    "profile": ["profile", "account", "user", "me", "avatar"],
    "settings": ["settings", "preferences", "config", "options", "gear"],
}

ORDINALS: dict[str, int] = {
    "first": 1,
    "1st": 1,
    "second": 2,
    "2nd": 2,
    "third": 3,
    "3rd": 3,
    "fourth": 4,
    "4th": 4,
    "fifth": 5,
    "5th": 5,
    "pehle": 1,
    "pehla": 1,
    "dusra": 2,
    "teesra": 3,
}


class EyesTargetResolver:
    """Ranks and resolves natural language UI targets to specific SemanticElements."""

    @classmethod
    def resolve(
        cls,
        query: str,
        state: ScreenState,
        preferred_type: UIElementType | None = None,
        ordinal_index: int | None = None,
    ) -> tuple[SemanticElement | None, ConfidenceLevel, float]:
        """Rank detected elements in screen state against user intent."""
        clean_q = query.lower().strip()
        candidates: list[tuple[SemanticElement, float]] = []

        # 1. Close popup intent ("close dialog", "dismiss popup", "x button")
        if any(w in clean_q for w in ["close popup", "dismiss popup", "close dialog", "close window", "popup band"]):
            close_elem = cls._find_popup_close_button(state)
            if close_elem:
                return close_elem, ConfidenceLevel.HIGH, 0.95

        # 2. Extract ordinal index if specified in query ("click the 2nd result", "click second button")
        if ordinal_index is None:
            ordinal_index = cls._extract_ordinal_index(clean_q)

        # 3. Filter candidates by type or scan all elements
        pool = state.elements
        if preferred_type:
            pool = [e for e in pool if e.element_type == preferred_type]
            if not pool:
                pool = state.elements  # Fallback to all if preferred type has none

        # 4. Score each element in pool
        for elem in pool:
            score = cls._score_element_match(clean_q, elem)
            if score > 0.30:
                candidates.append((elem, score))

        # 5. Handle ordinal selection
        if ordinal_index is not None and ordinal_index > 0:
            if candidates and ordinal_index <= len(candidates):
                chosen_elem, chosen_score = candidates[ordinal_index - 1]
                conf = ConfidenceLevel.HIGH if chosen_score >= 0.70 else ConfidenceLevel.MEDIUM
                return chosen_elem, conf, chosen_score
            elif pool:
                # Spatial top-to-bottom fallback for ordinals
                sorted_pool = sorted(pool, key=lambda e: (e.bounds[1], e.bounds[0]))
                if ordinal_index <= len(sorted_pool):
                    chosen_elem = sorted_pool[ordinal_index - 1]
                    return chosen_elem, ConfidenceLevel.HIGH, 0.85

        # Sort candidates descending by score
        candidates.sort(key=lambda item: item[1], reverse=True)

        if not candidates:
            logger.debug("No candidate elements found matching query: '%s'", query)
            return None, ConfidenceLevel.LOW, 0.0

        best_elem, best_score = candidates[0]

        # Check for ambiguity if second candidate is very close in score
        if len(candidates) > 1:
            second_score = candidates[1][1]
            if (best_score - second_score) < 0.06 and best_score < 0.80:
                return best_elem, ConfidenceLevel.MEDIUM, best_score

        if best_score >= 0.80:
            return best_elem, ConfidenceLevel.HIGH, best_score
        elif best_score >= 0.60:
            return best_elem, ConfidenceLevel.MEDIUM, best_score
        else:
            return best_elem, ConfidenceLevel.LOW, best_score

    @classmethod
    def _score_element_match(cls, query: str, elem: SemanticElement) -> float:
        """Calculate match score [0.0 - 1.0] between query and SemanticElement."""
        elem_label = (elem.label or "").lower().strip()
        elem_value = (elem.value or "").lower().strip()
        elem_help = (elem.help_text or "").lower().strip()

        combined_text = f"{elem_label} {elem_value} {elem_help}".strip()
        if not combined_text:
            return 0.0

        # Exact match
        if query == elem_label:
            return 1.0

        # Substring containment
        if query in elem_label:
            return 0.90 + 0.10 * (len(query) / max(len(elem_label), 1))
        if elem_label and elem_label in query:
            return 0.85

        # Token set overlap
        query_words = set(re.findall(r"\w+", query))
        elem_words = set(re.findall(r"\w+", combined_text))

        # Filter common filler words
        stop_words = {"the", "a", "an", "on", "in", "to", "for", "click", "tap", "press", "button", "box", "field", "link"}
        meaningful_query = query_words - stop_words
        if not meaningful_query:
            meaningful_query = query_words

        intersection = meaningful_query & elem_words
        if intersection:
            overlap_ratio = len(intersection) / len(meaningful_query)
            if overlap_ratio >= 1.0:
                return 0.88
            elif overlap_ratio >= 0.5:
                return 0.70

        # Synonym matching
        for syn_key, syn_list in SYNONYM_GROUPS.items():
            query_has_syn = any(syn in query for syn in syn_list)
            elem_has_syn = any(syn in combined_text for syn in syn_list)
            if query_has_syn and elem_has_syn:
                return 0.85
            # Check if query matches synonym key and element matches UI role (e.g. search -> search field)
            if query_has_syn and syn_key == "search" and elem.element_type == UIElementType.INPUT:
                if any(syn in combined_text for syn in ["search", "query", "find"]):
                    return 0.90
                return 0.80

        # Fuzzy string similarity
        sim = SequenceMatcher(None, query, elem_label).ratio()
        return sim * 0.70

    @classmethod
    def _extract_ordinal_index(cls, query: str) -> int | None:
        """Detect ordinal references like 'second result', '3rd link'."""
        for word, index in ORDINALS.items():
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, query):
                return index
        return None

    @classmethod
    def _find_popup_close_button(cls, state: ScreenState) -> SemanticElement | None:
        """Find a close/dismiss button on active dialogs, popups, or windows."""
        # 1. Look within detected dialogs
        for dialog in state.dialogs:
            dx, dy, dw, dh = dialog.bounding_box
            for child in state.buttons:
                cx, cy = child.center_point
                if dx <= cx <= (dx + dw) and dy <= cy <= (dy + dh):
                    lbl = (child.label or "").lower()
                    if lbl in ("close", "cancel", "dismiss", "x", "cross", "done"):
                        return child

        # 2. Look for any standalone close button
        for elem in state.buttons:
            lbl = (elem.label or "").lower()
            if lbl in ("close", "cancel", "dismiss", "x"):
                return elem
            # Often close buttons are small and located top-right
            if lbl == "" and elem.bounds[2] <= 30 and elem.bounds[3] <= 30:
                # Check if it's near top of a window
                if elem.bounds[1] < 200:
                    return elem

        return None
