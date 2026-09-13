"""Data models and schemas for NOVA Computer Agent V2 Visual Interaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class UIElementType(str, Enum):
    """Categorized types of graphical user interface elements."""

    BUTTON = "button"
    INPUT = "input"
    LINK = "link"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    DIALOG = "dialog"
    POPUP = "popup"
    CHECKBOX = "checkbox"
    RADIO_BUTTON = "radio_button"
    COMBO_BOX = "combo_box"
    TAB = "tab"
    ERROR_BANNER = "error_banner"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


class VisualConfidence(str, Enum):
    """Confidence tiers for visual target resolution and action safety."""

    HIGH = "high"        # >= 0.85 (Safe to execute automatically)
    MEDIUM = "medium"    # 0.65 - 0.84 (Requires fallback check or re-observation)
    LOW = "low"          # < 0.65 (Requires user clarification)


class VisualActionType(str, Enum):
    """Atomic computer interaction actions performed by the visual agent."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MOVE_TO = "move_to"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    KEY_COMBINATION = "key_combination"
    SCROLL = "scroll"
    CLOSE_POPUP = "close_popup"
    EXPLAIN_ERROR = "explain_error"
    EXPLAIN_SCREEN = "explain_screen"
    SCROLL_UNTIL_VISIBLE = "scroll_until_visible"


@dataclass
class UIElement:
    """Represents an identified on-screen UI element with bounding geometry."""

    type: UIElementType
    label: str
    bounding_box: tuple[int, int, int, int]  # (x, y, width, height) in screen pixels
    center_point: tuple[int, int]            # (center_x, center_y)
    confidence: float = 1.0                  # 0.0 to 1.0
    source: str = "accessibility"            # "accessibility", "vision", "heuristic"
    raw_text: str = ""
    is_clickable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        element_type: UIElementType | str,
        label: str,
        x: int,
        y: int,
        w: int,
        h: int,
        confidence: float = 1.0,
        source: str = "accessibility",
        raw_text: str = "",
        is_clickable: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> UIElement:
        """Helper to create a UIElement with calculated center point."""
        etype = UIElementType(element_type) if isinstance(element_type, str) else element_type
        center_x = x + (w // 2)
        center_y = y + (h // 2)
        return cls(
            type=etype,
            label=label.strip(),
            bounding_box=(x, y, w, h),
            center_point=(center_x, center_y),
            confidence=max(0.0, min(1.0, confidence)),
            source=source,
            raw_text=raw_text or label,
            is_clickable=is_clickable,
            metadata=metadata or {},
        )


@dataclass
class ScreenSnapshot:
    """Represents an instantaneous on-demand snapshot of the active screen or window."""

    snapshot_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    image_path: Path | None = None
    screen_width: int = 1470
    screen_height: int = 956
    active_application: str = ""
    active_window: str = ""
    screen_hash: str = ""
    is_window_only: bool = False

    @property
    def age_seconds(self) -> float:
        """Seconds elapsed since this snapshot was captured."""
        now = datetime.now(UTC)
        return (now - self.timestamp).total_seconds()

    def is_fresh(self, max_age_seconds: float = 5.0) -> bool:
        """Check if snapshot is recent enough to act upon safely."""
        return self.age_seconds <= max_age_seconds


@dataclass
class ScreenAnalysis:
    """Structured understanding of on-screen elements, text, dialogs, and errors."""

    snapshot: ScreenSnapshot
    description: str = ""
    visible_text: list[str] = field(default_factory=list)
    ui_elements: list[UIElement] = field(default_factory=list)
    buttons: list[UIElement] = field(default_factory=list)
    inputs: list[UIElement] = field(default_factory=list)
    menus: list[UIElement] = field(default_factory=list)
    dialogs: list[UIElement] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    candidate_targets: list[UIElement] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def find_elements_by_label(self, label: str, element_type: UIElementType | None = None) -> list[UIElement]:
        """Search detected elements by label substring and optional type."""
        norm_label = label.lower().strip()
        matches = []
        for elem in self.ui_elements:
            if element_type and elem.type != element_type:
                continue
            if norm_label in elem.label.lower() or norm_label in elem.raw_text.lower():
                matches.append(elem)
        return matches


@dataclass
class VisualActionPlan:
    """A planned visual action ready for execution and verification."""

    action_type: VisualActionType
    target_element: UIElement | None = None
    coordinates: tuple[int, int] | None = None
    text_to_type: str = ""
    key_code: int | None = None
    key_combination: list[str] = field(default_factory=list)
    scroll_direction: str = "down"
    scroll_lines: int = 5
    confidence: VisualConfidence = VisualConfidence.HIGH
    confidence_score: float = 1.0
    raw_prompt: str = ""
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    snapshot: ScreenSnapshot | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VisualResult:
    """Outcome of a visual action and its post-execution verification."""

    success: bool
    action_type: VisualActionType
    message: str = ""
    spoken_response: str = ""
    verified: bool = False
    verification_detail: str = ""
    confidence_score: float = 1.0
    error: str | None = None
    target_element: UIElement | None = None
    before_snapshot: ScreenSnapshot | None = None
    after_snapshot: ScreenSnapshot | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
