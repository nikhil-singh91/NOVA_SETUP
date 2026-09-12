"""Unified screen state world model combining semantic Accessibility and visual OCR.

Maintains an in-memory, structured representation of the user's active screen
including visible text, interactive elements, focused targets, dialogs, and errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.eyes.accessibility import SemanticElement, UIElementType
from core.eyes.capture import DisplayMetrics


@dataclass
class ScreenState:
    """Instantaneous world model of the screen currently visible to NOVA Eyes."""

    timestamp: datetime
    active_application: str
    active_window: str
    metrics: DisplayMetrics
    visual_hash: str
    elements: list[SemanticElement] = field(default_factory=list)
    buttons: list[SemanticElement] = field(default_factory=list)
    inputs: list[SemanticElement] = field(default_factory=list)
    links: list[SemanticElement] = field(default_factory=list)
    tabs: list[SemanticElement] = field(default_factory=list)
    dialogs: list[SemanticElement] = field(default_factory=list)
    scroll_areas: list[SemanticElement] = field(default_factory=list)
    visible_texts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    focused_element: SemanticElement | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()

    def is_fresh(self, max_age_seconds: float = 3.0) -> bool:
        return self.age_seconds <= max_age_seconds

    def has_changed_from(self, previous: ScreenState | None) -> bool:
        """Determine whether the screen has experienced a meaningful change."""
        if previous is None:
            return True

        # Application or window title change
        if self.active_application != previous.active_application:
            return True
        if self.active_window != previous.active_window:
            return True

        # Visual hash change
        if self.visual_hash and previous.visual_hash and self.visual_hash != previous.visual_hash:
            return True

        # Element count change
        if abs(len(self.elements) - len(previous.elements)) > 2:
            return True

        return False

    def find_elements_by_label(
        self,
        label: str,
        element_type: UIElementType | None = None,
    ) -> list[SemanticElement]:
        """Search detected elements by label substring and optional type."""
        norm_label = label.lower().strip()
        matches: list[SemanticElement] = []
        for elem in self.elements:
            if element_type and elem.element_type != element_type:
                continue
            if norm_label in elem.label.lower() or norm_label in elem.value.lower():
                matches.append(elem)
        return matches

    def get_natural_screen_description(self, is_hinglish: bool = False) -> str:
        """Produce a natural, human-friendly conversational description of the current screen."""
        app = (self.active_application or "Desktop").strip()
        win = (self.active_window or "").strip()

        # 1. Error state takes priority if present
        if self.errors:
            err = self.errors[0]
            if len(err) > 100:
                err = err[:97] + "..."
            if is_hinglish:
                return f"Screen par ek error message dikh raha hai: '{err}'."
            return f"There's an error on your screen: '{err}'."

        app_lower = app.lower()
        win_lower = win.lower()

        # 2. Browser detection
        if any(b in app_lower for b in ("chrome", "safari", "brave", "edge", "firefox", "browser")):
            if "youtube" in win_lower or any("youtube" in t.lower() for t in self.visible_texts[:5]):
                if "/shorts" in win_lower or "shorts" in win_lower:
                    return "Aap abhi YouTube Shorts dekh rahe ho." if is_hinglish else "You're on YouTube Shorts right now."
                # Extract probable video title from visible text
                title_candidates = [
                    t for t in self.visible_texts
                    if len(t) > 10 and not any(k in t.lower() for k in ("youtube", "subscribers", "views", "share", "save", "download", "home", "explore", "subscribe", "notification"))
                ]
                if title_candidates:
                    vid_title = title_candidates[0]
                    return f"Aap abhi YouTube par '{vid_title}' dekh rahe ho." if is_hinglish else f"You're on YouTube right now, looking at '{vid_title}'."
                clean_win = win.replace(" - YouTube", "").strip()
                return f"Aap abhi YouTube par '{clean_win}' par ho." if is_hinglish else f"You're on YouTube right now looking at '{clean_win}'."
            
            clean_win = win.split(" - ")[0].strip() if " - " in win else win
            return f"Aap browser mein '{clean_win}' dekh rahe ho." if is_hinglish else f"You're in your browser looking at '{clean_win}'."

        # 3. Code Editor / Terminal detection
        if any(ide in app_lower for ide in ("code", "cursor", "sublime", "pycharm", "intellij", "terminal", "iterm", "xcode")):
            clean_win = win.split(" — ")[0].split(" - ")[0].strip() if win else app
            return f"Aap {app} mein ho, aur '{clean_win}' open hai." if is_hinglish else f"You're in {app}, and I can see your workspace open with '{clean_win}'."

        # 4. Finder / Files detection
        if "finder" in app_lower:
            return f"Aap Finder mein '{win}' folder dekh rahe ho." if is_hinglish else f"You're in Finder looking at the '{win}' folder."

        # 5. General window description
        if win and win.lower() != app_lower:
            return f"Aap abhi {app} mein '{win}' dekh rahe ho." if is_hinglish else f"You're currently in {app}, looking at '{win}'."
        return f"Aap abhi {app} dekh rahe ho." if is_hinglish else f"You're currently looking at {app}."

    def get_summary(self) -> str:
        """Compact conversational description of the current screen for AI context."""
        app_str = self.active_application or "Unknown App"
        win_str = self.active_window or "Active Window"
        elem_count = len(self.elements)
        button_count = len(self.buttons)
        input_count = len(self.inputs)

        error_str = f" | Errors: {', '.join(self.errors)}" if self.errors else ""
        return (
            f"{app_str} - '{win_str}' ({elem_count} UI elements: "
            f"{button_count} buttons, {input_count} fields{error_str})"
        )

    @classmethod
    def build_from_sources(
        cls,
        timestamp: datetime,
        active_app: str,
        active_win: str,
        metrics: DisplayMetrics,
        visual_hash: str,
        ax_elements: list[SemanticElement],
        ocr_elements: list[SemanticElement],
    ) -> ScreenState:
        """Fuse Accessibility elements and Vision OCR elements into a unified state without duplicates."""
        all_elements: list[SemanticElement] = list(ax_elements)
        existing_centers = [e.center_point for e in ax_elements]

        # Merge OCR elements if not closely overlapping an existing AX element
        for ocr_elem in ocr_elements:
            ox, oy = ocr_elem.center_point
            is_duplicate = False
            for ex, ey in existing_centers:
                # If center point is within 25 pixels, consider duplicate
                if abs(ox - ex) < 25 and abs(oy - ey) < 20:
                    is_duplicate = True
                    break

            if not is_duplicate:
                all_elements.append(ocr_elem)
                existing_centers.append((ox, oy))

        buttons = [e for e in all_elements if e.element_type in (UIElementType.BUTTON, UIElementType.MENU_ITEM)]
        inputs = [e for e in all_elements if e.is_input or e.element_type == UIElementType.INPUT]
        links = [e for e in all_elements if e.element_type == UIElementType.LINK]
        tabs = [e for e in all_elements if e.element_type == UIElementType.TAB]
        dialogs = [e for e in all_elements if e.element_type in (UIElementType.DIALOG, UIElementType.POPUP)]
        scroll_areas = [e for e in all_elements if e.is_scrollable]

        focused = next((e for e in all_elements if e.is_focused), None)

        # Extract sorted unique visible text lines
        sorted_texts = sorted(
            [e.label.strip() for e in all_elements if e.label.strip()],
            key=lambda s: len(s),
            reverse=True,
        )
        unique_texts: list[str] = []
        for t in sorted_texts:
            if t not in unique_texts and len(t) > 1:
                unique_texts.append(t)

        # Detect error patterns
        err_keywords = ["error", "fatal", "exception", "failed", "warning", "traceback", "cannot", "denied", "not found", "404"]
        errors: list[str] = []
        for t in unique_texts:
            t_low = t.lower()
            if any(k in t_low for k in err_keywords) and len(t) > 4:
                errors.append(t)

        return cls(
            timestamp=timestamp,
            active_application=active_app,
            active_window=active_win,
            metrics=metrics,
            visual_hash=visual_hash,
            elements=all_elements,
            buttons=buttons,
            inputs=inputs,
            links=links,
            tabs=tabs,
            dialogs=dialogs,
            scroll_areas=scroll_areas,
            visible_texts=unique_texts[:30],
            errors=errors,
            focused_element=focused,
        )
