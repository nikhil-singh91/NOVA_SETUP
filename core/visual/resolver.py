"""UI target resolution, candidate ranking, and confidence scoring for NOVA Visual Agent."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from core.logger import get_logger
from core.visual.models import (
    ScreenAnalysis,
    UIElement,
    UIElementType,
    VisualConfidence,
)

logger = get_logger(__name__)

SYNONYMS: dict[str, list[str]] = {
    "search": ["search", "find", "query", "explore", "lookup", "glass"],
    "login": ["login", "sign in", "signin", "log in", "enter account"],
    "submit": ["submit", "send", "done", "enter", "go", "proceed"],
    "close": ["close", "dismiss", "cancel", "x", "cross", "exit", "abort"],
    "download": ["download", "get", "install", "save"],
    "next": ["next", "continue", "forward", "more"],
    "previous": ["previous", "back", "prev"],
    "ok": ["ok", "okay", "yes", "confirm", "accept"],
}


class UITargetResolver:
    """Ranks and resolves natural language UI targets to specific bounding-box elements."""

    @classmethod
    def resolve_target(
        cls,
        query: str,
        analysis: ScreenAnalysis,
        target_type: UIElementType | None = None,
        ordinal_index: int | None = None,
    ) -> tuple[UIElement | None, VisualConfidence, float]:
        """Rank detected elements against user intent and return the best candidate."""
        clean_q = query.lower().strip()
        candidates: list[tuple[UIElement, float]] = []

        # 1. Handle popup close intent ("Close this popup", "Dismiss dialog")
        if any(w in clean_q for w in ["close popup", "close this popup", "dismiss popup", "close dialog", "popup band karo"]):
            close_elem, score = cls._find_popup_close_button(analysis)
            if close_elem:
                return close_elem, VisualConfidence.HIGH, score

        # 2. Extract ordinal index if specified in query ("click the 2nd result", "click second button")
        if ordinal_index is None:
            ordinal_index = cls._extract_ordinal_index(clean_q)

        # 3. Filter candidates by type or scan all elements
        pool = analysis.ui_elements
        if target_type:
            pool = [e for e in pool if e.type == target_type]

        # 4. Score each element in pool
        for elem in pool:
            score = cls._score_element_match(clean_q, elem)
            if score > 0.35:
                candidates.append((elem, score))

        # Handle ordinal selection
        if ordinal_index is not None and ordinal_index > 0:
            if candidates and ordinal_index <= len(candidates):
                chosen_elem, chosen_score = candidates[ordinal_index - 1]
                conf = VisualConfidence.HIGH if chosen_score >= 0.75 else VisualConfidence.MEDIUM
                return chosen_elem, conf, chosen_score
            elif pool:
                # Spatial top-to-bottom fallback for ordinal ("second result", "third link")
                sorted_pool = sorted(pool, key=lambda e: (e.bounding_box[1], e.bounding_box[0]))
                if ordinal_index <= len(sorted_pool):
                    chosen_elem = sorted_pool[ordinal_index - 1]
                    return chosen_elem, VisualConfidence.HIGH, 0.90

        # Sort candidates descending by score
        candidates.sort(key=lambda item: item[1], reverse=True)

        if not candidates:
            logger.debug("No candidates found matching query: '%s'", query)
            return None, VisualConfidence.LOW, 0.0

        # Best candidate
        best_elem, best_score = candidates[0]

        # Check ambiguity with second candidate
        if len(candidates) > 1:
            second_score = candidates[1][1]
            # If scores are too close and low, downgrade to medium/low
            if (best_score - second_score) < 0.08 and best_score < 0.85:
                return best_elem, VisualConfidence.MEDIUM, best_score

        if best_score >= 0.85:
            return best_elem, VisualConfidence.HIGH, best_score
        elif best_score >= 0.65:
            return best_elem, VisualConfidence.MEDIUM, best_score
        else:
            return best_elem, VisualConfidence.LOW, best_score

    @classmethod
    def _score_element_match(cls, query: str, elem: UIElement) -> float:
        """Compute matching similarity between query and element label/type."""
        label_lower = elem.label.lower().strip()
        raw_lower = elem.raw_text.lower().strip()

        # Clean query tokens
        clean_q = re.sub(r"^(?:click|press|tap|select|open|type\s+in|focus)\s+(?:the\s+|a\s+|an\s+)?", "", query).strip()
        clean_q = re.sub(r"\b(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\b", "", clean_q).strip()
        clean_q = re.sub(r"\s+(?:button|link|input|field|tab|menu|icon)$", "", clean_q).strip()

        if not clean_q:
            clean_q = query

        # Exact match
        if clean_q == label_lower or clean_q == raw_lower:
            return 1.0

        # Full containment
        if clean_q in label_lower or label_lower in clean_q:
            return 0.92

        # Synonym expansion
        for root_word, syns in SYNONYMS.items():
            if clean_q in syns or any(s in clean_q for s in syns):
                if any(s in label_lower for s in syns) or any(s in raw_lower for s in syns):
                    return 0.88

        # String similarity ratio
        seq_ratio = SequenceMatcher(None, clean_q, label_lower).ratio()
        return round(seq_ratio, 2)

    @classmethod
    def _find_popup_close_button(cls, analysis: ScreenAnalysis) -> tuple[UIElement | None, float]:
        """Find the most plausible close/dismiss button for a visible popup or sheet."""
        # 1. Look for explicit close / dismiss / x buttons
        for b in analysis.buttons:
            lbl = b.label.lower()
            if lbl in ["close", "dismiss", "x", "cancel", "done", "ok", "got it", "band karo"]:
                return b, 0.95

        # 2. Look for sheets / dialogs and their children
        for d in analysis.dialogs:
            for b in analysis.buttons:
                # Check if button is inside dialog geometry
                dx, dy, dw, dh = d.bounding_box
                bx, by, _, _ = b.bounding_box
                if dx <= bx <= dx + dw and dy <= by <= dy + dh:
                    return b, 0.90

        # Fallback: top-right close icon or any button containing 'close'
        for b in analysis.buttons:
            if "close" in b.label.lower() or "dismiss" in b.label.lower():
                return b, 0.85

        return None, 0.0

    @classmethod
    def _extract_ordinal_index(cls, query: str) -> int | None:
        """Extract ordinal index (1st, 2nd, first, second, 3rd, third) from text."""
        ordinal_map = {
            "first": 1, "1st": 1, "one": 1,
            "second": 2, "2nd": 2, "two": 2,
            "third": 3, "3rd": 3, "three": 3,
            "fourth": 4, "4th": 4, "four": 4,
            "fifth": 5, "5th": 5, "five": 5,
        }
        for word, idx in ordinal_map.items():
            if re.search(rf"\b{re.escape(word)}\b", query):
                return idx
        return None
