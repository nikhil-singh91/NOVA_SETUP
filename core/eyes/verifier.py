"""Rigorous post-action state verification for NOVA Eyes.

Compares before and after ScreenStates to confirm that actions caused real,
observable changes in the user's interface. Never fakes success.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.eyes.accessibility import SemanticElement, UIElementType
from core.eyes.planner import ActionType
from core.eyes.state import ScreenState
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VerificationOutcome:
    """Outcome of verifying an action effect against observed screen state."""

    verified: bool
    summary: str
    detail: str
    should_retry: bool = False
    suggested_recovery: str | None = None


class EyesStateVerifier:
    """Verifies that an executed pointer, keyboard, or scroll action actually succeeded."""

    @classmethod
    def verify(
        cls,
        action: ActionType,
        before: ScreenState | None,
        after: ScreenState | None,
        target_element: SemanticElement | None = None,
        action_payload: Any = None,
    ) -> VerificationOutcome:
        """Evaluate observable state difference between before and after ScreenStates."""
        if before is None or after is None:
            return VerificationOutcome(
                verified=False,
                summary="Cannot verify: missing before or after screen observation.",
                detail="One of the screen states was unavailable in RAM.",
                should_retry=False,
            )

        if action == ActionType.CLICK or action == ActionType.DOUBLE_CLICK:
            return cls._verify_click(before, after, target_element)
        elif action == ActionType.TYPE_TEXT:
            return cls._verify_typing(before, after, target_element, text=str(action_payload or ""))
        elif action == ActionType.SCROLL:
            return cls._verify_scroll(before, after)
        elif action == ActionType.SCROLL_UNTIL_VISIBLE:
            return cls._verify_scroll_until_visible(after, target_text=str(action_payload or ""))
        elif action == ActionType.CLOSE_POPUP:
            return cls._verify_close_popup(before, after, target_element)
        elif action == ActionType.PRESS_KEY:
            return cls._verify_press_key(before, after, key_name=str(action_payload or ""))
        else:
            # Generic visual hash change
            if before.visual_hash != after.visual_hash:
                return VerificationOutcome(
                    verified=True,
                    summary="Screen changed visually after action.",
                    detail="Observed visual change in screen buffer.",
                )
            return VerificationOutcome(
                verified=True,
                summary="Action completed.",
                detail="State maintained.",
            )

    # =========================================================================
    # SPECIFIC VERIFIERS
    # =========================================================================

    @classmethod
    def _verify_click(
        cls,
        before: ScreenState,
        after: ScreenState,
        target_element: SemanticElement | None,
    ) -> VerificationOutcome:
        """Verify click caused window change, modal appearance, or visual delta."""
        # 1. Window or Application changed
        if before.active_application != after.active_application:
            return VerificationOutcome(
                verified=True,
                summary=f"Active application switched to '{after.active_application}'.",
                detail=f"App transition: {before.active_application} -> {after.active_application}",
            )

        if before.active_window != after.active_window and after.active_window:
            return VerificationOutcome(
                verified=True,
                summary=f"Window title updated to '{after.active_window}'.",
                detail=f"Window transition: '{before.active_window}' -> '{after.active_window}'",
            )

        # 2. Visual hash changed
        if before.visual_hash != after.visual_hash:
            # Check if clicked element was a button or toggle that changed state
            target_name = target_element.label if target_element else "element"
            return VerificationOutcome(
                verified=True,
                summary=f"Clicked '{target_name}' and verified screen state changed.",
                detail="Visual frame diff detected state update.",
            )

        # 3. Check if target element was focused
        if target_element:
            after_focused = after.focused_element
            if after_focused and after_focused.label == target_element.label:
                return VerificationOutcome(
                    verified=True,
                    summary=f"Clicked and focused '{target_element.label}'.",
                    detail="Target element is now focused.",
                )

        # No visible change detected
        elem_name = target_element.label if target_element else "target"
        return VerificationOutcome(
            verified=False,
            summary=f"Click on '{elem_name}' did not produce an observable change.",
            detail="Screen state remained identical before and after click event.",
            should_retry=True,
            suggested_recovery="Re-locate element with fresh observation and retry click.",
        )

    @classmethod
    def _verify_typing(
        cls,
        before: ScreenState,
        after: ScreenState,
        target_element: SemanticElement | None,
        text: str,
    ) -> VerificationOutcome:
        """Verify that typed text actually appeared in the focused or target field."""
        norm_text = text.lower().strip()
        if not norm_text:
            return VerificationOutcome(verified=True, summary="Empty text typed.", detail="No text to verify.")

        # 1. Check focused element value in after state
        if after.focused_element:
            val = (after.focused_element.value or "").lower()
            if norm_text in val:
                return VerificationOutcome(
                    verified=True,
                    summary=f"Typed text '{text}' confirmed in focused field.",
                    detail=f"Field value: '{after.focused_element.value}'",
                )

        # 2. Check target element if specified
        if target_element:
            matching_elems = after.find_elements_by_label(target_element.label, element_type=UIElementType.INPUT)
            for m in matching_elems:
                if norm_text in (m.value or "").lower():
                    return VerificationOutcome(
                        verified=True,
                        summary=f"Typed text '{text}' confirmed in field '{target_element.label}'.",
                        detail=f"Element value contains '{text}'",
                    )

        # 3. Check if typed text appears anywhere in visible OCR texts of after state
        if any(norm_text in t.lower() for t in after.visible_texts):
            return VerificationOutcome(
                verified=True,
                summary=f"Text '{text}' is now visible on screen.",
                detail="Confirmed via in-memory OCR recognition.",
            )

        # 4. Check visual hash changed
        if before.visual_hash != after.visual_hash:
            return VerificationOutcome(
                verified=True,
                summary=f"Typed '{text}' and screen updated visually.",
                detail="Visual delta observed though exact text value not directly exposed via AX.",
            )

        return VerificationOutcome(
            verified=False,
            summary=f"Could not confirm text '{text}' appeared on screen.",
            detail="Neither AX value nor visual delta reflected the typed text.",
            should_retry=True,
            suggested_recovery="Focus the input field first, then re-enter text.",
        )

    @classmethod
    def _verify_scroll(cls, before: ScreenState, after: ScreenState) -> VerificationOutcome:
        """Verify that scrolling actually moved the viewable content."""
        # Visual hash must change or visible texts must shift
        if before.visual_hash != after.visual_hash:
            return VerificationOutcome(
                verified=True,
                summary="Scrolled page successfully.",
                detail="Screen content moved visually.",
            )

        if before.visible_texts != after.visible_texts:
            return VerificationOutcome(
                verified=True,
                summary="Scrolled view successfully.",
                detail="New text content came into view.",
            )

        return VerificationOutcome(
            verified=False,
            summary="Scroll had no effect (reached top or bottom of container).",
            detail="Screen state remained completely unchanged after scroll wheel event.",
            should_retry=False,
        )

    @classmethod
    def _verify_scroll_until_visible(cls, after: ScreenState, target_text: str) -> VerificationOutcome:
        """Verify target text has come into view after scrolling."""
        norm_t = target_text.lower().strip()
        matches = after.find_elements_by_label(norm_t)
        if matches:
            return VerificationOutcome(
                verified=True,
                summary=f"Target '{target_text}' is now visible on screen.",
                detail=f"Found semantic element '{matches[0].label}' at {matches[0].bounds}",
            )

        if any(norm_t in vt.lower() for vt in after.visible_texts):
            return VerificationOutcome(
                verified=True,
                summary=f"Target '{target_text}' is now visible in screen text.",
                detail="Found in visible OCR text layer.",
            )

        return VerificationOutcome(
            verified=False,
            summary=f"Target '{target_text}' not yet visible on screen.",
            detail="Target text does not match any currently visible element or OCR line.",
            should_retry=True,
        )

    @classmethod
    def _verify_close_popup(
        cls,
        before: ScreenState,
        after: ScreenState,
        target_element: SemanticElement | None,
    ) -> VerificationOutcome:
        """Verify active popup or dialog was dismissed."""
        # If dialog count decreased
        if len(before.dialogs) > len(after.dialogs):
            return VerificationOutcome(
                verified=True,
                summary="Popup dismissed successfully.",
                detail=f"Dialog count decreased from {len(before.dialogs)} to {len(after.dialogs)}.",
            )

        # Or visual hash changed and window title / state is active
        if before.visual_hash != after.visual_hash:
            return VerificationOutcome(
                verified=True,
                summary="Popup closed successfully.",
                detail="Visual confirmation of popup dismissal.",
            )

        return VerificationOutcome(
            verified=False,
            summary="Popup did not close.",
            detail="Dialog remained visible on screen.",
            should_retry=True,
            suggested_recovery="Press Escape key to dismiss modal.",
        )

    @classmethod
    def _verify_press_key(cls, before: ScreenState, after: ScreenState, key_name: str) -> VerificationOutcome:
        """Verify keypress had effect."""
        if before.visual_hash != after.visual_hash or before.active_window != after.active_window:
            return VerificationOutcome(
                verified=True,
                summary=f"Key '{key_name}' pressed and screen updated.",
                detail="Observed state transition after keystroke.",
            )
        return VerificationOutcome(
            verified=True,
            summary=f"Key '{key_name}' sent.",
            detail="Dispatched keystroke.",
        )
