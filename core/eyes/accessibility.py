"""Native macOS Accessibility (AXUIElement) inspection and semantic element extraction.

Traverses the active window hierarchy to extract buttons, text fields, links, tabs,
dialogs, and scroll areas with exact logical screen geometry and state.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import AppKit
NSWorkspace: Any = getattr(AppKit, "NSWorkspace", None)
import ApplicationServices
AS: Any = ApplicationServices
from core.logger import get_logger

logger = get_logger(__name__)


class UIElementType(str, Enum):
    """Normalized graphical user interface element classification."""

    BUTTON = "button"
    INPUT = "input"
    LINK = "link"
    TAB = "tab"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    DIALOG = "dialog"
    POPUP = "popup"
    CHECKBOX = "checkbox"
    RADIO_BUTTON = "radio_button"
    COMBO_BOX = "combo_box"
    SCROLL_AREA = "scroll_area"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class SemanticElement:
    """A rich, semantically labeled UI element identified on the screen."""

    element_id: str
    element_type: UIElementType
    role: str
    label: str
    value: str
    bounding_box: tuple[float, float, float, float]  # (x, y, width, height) logical screen coords
    center_point: tuple[float, float]               # (center_x, center_y) logical screen coords
    is_clickable: bool = True
    is_input: bool = False
    is_focused: bool = False
    is_enabled: bool = True
    is_selected: bool = False
    is_scrollable: bool = False
    source: str = "accessibility"  # "accessibility" or "vision_ocr"
    confidence: float = 1.0
    ax_ref: Any = None  # Native AXUIElement reference if available
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.bounding_box

    @property
    def help_text(self) -> str:
        return str(self.metadata.get("help", ""))

    @property
    def x(self) -> float:
        return self.bounding_box[0]

    @property
    def y(self) -> float:
        return self.bounding_box[1]

    @property
    def width(self) -> float:
        return self.bounding_box[2]

    @property
    def height(self) -> float:
        return self.bounding_box[3]

    @classmethod
    def create(
        cls,
        *args: Any,
        element_id: str | None = None,
        element_type: UIElementType | str | None = None,
        label: str | None = None,
        x: float | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
        role: str = "",
        value: str = "",
        is_clickable: bool = True,
        is_input: bool = False,
        is_focused: bool = False,
        is_enabled: bool = True,
        is_selected: bool = False,
        is_scrollable: bool = False,
        source: str = "accessibility",
        confidence: float = 1.0,
        ax_ref: Any = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SemanticElement:
        # Parse positional args if passed
        if len(args) >= 2:
            first = args[0]
            is_first_type = isinstance(first, UIElementType) or (isinstance(first, str) and any(first == e.value for e in UIElementType))
            if is_first_type:
                element_type = first
                label = str(args[1] or "")
                if len(args) > 2:
                    x = float(args[2])
                if len(args) > 3:
                    y = float(args[3])
                if len(args) > 4:
                    width = float(args[4])
                if len(args) > 5:
                    height = float(args[5])
            else:
                element_id = str(first)
                element_type = args[1]
                if len(args) > 2:
                    label = str(args[2] or "")
                if len(args) > 3:
                    x = float(args[3])
                if len(args) > 4:
                    y = float(args[4])
                if len(args) > 5:
                    width = float(args[5])
                if len(args) > 6:
                    height = float(args[6])

        # Resolve defaults
        etype = UIElementType(element_type) if isinstance(element_type, str) else (element_type or UIElementType.UNKNOWN)
        eid = element_id or f"elem_{int(time.time() * 1000)}"
        lbl = str(label or "")
        val_x = float(x if x is not None else 0.0)
        val_y = float(y if y is not None else 0.0)
        val_w = float(width if width is not None else 0.0)
        val_h = float(height if height is not None else 0.0)

        center_x = val_x + (val_w / 2.0)
        center_y = val_y + (val_h / 2.0)
        return cls(
            element_id=eid,
            element_type=etype,
            role=role,
            label=lbl.strip(),
            value=value.strip(),
            bounding_box=(val_x, val_y, val_w, val_h),
            center_point=(round(center_x), round(center_y)),
            is_clickable=is_clickable,
            is_input=is_input,
            is_focused=is_focused,
            is_enabled=is_enabled,
            is_selected=is_selected,
            is_scrollable=is_scrollable,
            source=source,
            confidence=confidence,
            ax_ref=ax_ref,
            metadata=metadata or {},
        )


ROLE_MAP: dict[str, UIElementType] = {
    "AXButton": UIElementType.BUTTON,
    "AXPopUpButton": UIElementType.BUTTON,
    "AXMenuButton": UIElementType.BUTTON,
    "AXTextField": UIElementType.INPUT,
    "AXTextArea": UIElementType.INPUT,
    "AXSearchField": UIElementType.INPUT,
    "AXLink": UIElementType.LINK,
    "AXTab": UIElementType.TAB,
    "AXRadioButton": UIElementType.RADIO_BUTTON,
    "AXCheckBox": UIElementType.CHECKBOX,
    "AXComboBox": UIElementType.COMBO_BOX,
    "AXMenu": UIElementType.MENU,
    "AXMenuItem": UIElementType.MENU_ITEM,
    "AXSheet": UIElementType.POPUP,
    "AXDialog": UIElementType.DIALOG,
    "AXScrollArea": UIElementType.SCROLL_AREA,
    "AXStaticText": UIElementType.TEXT,
    "AXImage": UIElementType.IMAGE,
}


class AccessibilityInspector:
    """Deep accessibility tree traversal using native macOS ApplicationServices."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @staticmethod
    def is_trusted() -> bool:
        """Return True if NOVA has macOS Accessibility permissions."""
        try:
            return bool(AS.AXIsProcessTrusted())
        except Exception:
            return False

    @staticmethod
    def get_frontmost_app_info() -> tuple[str, int]:
        """Return (localized_name, pid) of frontmost macOS application."""
        try:
            ws = NSWorkspace.sharedWorkspace()
            front_app = ws.frontmostApplication()
            if front_app:
                return str(front_app.localizedName() or ""), int(front_app.processIdentifier())
        except Exception as exc:
            logger.debug("Failed to query frontmost application: %s", exc)
        return "", 0

    def inspect_frontmost_window(
        self,
        max_elements: int = 150,
        max_depth: int = 6,
    ) -> tuple[str, str, list[SemanticElement]]:
        """Extract structured semantic UI elements from frontmost application window.

        Returns:
            (app_name, window_title, elements)
        """
        app_name, pid = self.get_frontmost_app_info()
        if pid <= 0:
            return app_name, "", []

        if not self.is_trusted():
            logger.warning("macOS Accessibility permission not granted. AX inspection unavailable.")
            return app_name, "", []

        try:
            app_ref = AS.AXUIElementCreateApplication(pid)
            err, win_list = AS.AXUIElementCopyAttributeValue(app_ref, AS.kAXWindowsAttribute, None)
            if err != 0 or not win_list:
                return app_name, "", []

            front_win = win_list[0]
            err, win_title = AS.AXUIElementCopyAttributeValue(front_win, AS.kAXTitleAttribute, None)
            win_title = str(win_title or "")

            elements: list[SemanticElement] = []
            visited = 0

            def _traverse(node: Any, depth: int) -> None:
                nonlocal visited
                if depth > max_depth or visited >= max_elements:
                    return

                # Extract attributes of node
                err, role = AS.AXUIElementCopyAttributeValue(node, AS.kAXRoleAttribute, None)
                if err != 0 or not role:
                    return

                role_str = str(role)

                # Geometry extraction
                err_pos, pos_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXPositionAttribute, None)
                err_size, size_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXSizeAttribute, None)

                x, y, w, h = 0.0, 0.0, 0.0, 0.0
                if err_pos == 0 and pos_val:
                    succ, pt = AS.AXValueGetValue(pos_val, AS.kAXValueCGPointType, None)
                    if succ:
                        x, y = float(pt.x), float(pt.y)

                if err_size == 0 and size_val:
                    succ, sz = AS.AXValueGetValue(size_val, AS.kAXValueCGSizeType, None)
                    if succ:
                        w, h = float(sz.width), float(sz.height)

                # Extract label / title / description / value
                err_t, title_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXTitleAttribute, None)
                err_d, desc_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXDescriptionAttribute, None)
                err_v, val_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXValueAttribute, None)

                label = str(title_val or desc_val or "").strip()
                val_str = str(val_val or "").strip()

                # Extract states
                err_f, foc_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXFocusedAttribute, None)
                err_e, en_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXEnabledAttribute, None)
                err_s, sel_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXSelectedAttribute, None)

                is_focused = bool(foc_val) if err_f == 0 else False
                is_enabled = bool(en_val) if err_e == 0 else True
                is_selected = bool(sel_val) if err_s == 0 else False

                etype = ROLE_MAP.get(role_str, UIElementType.UNKNOWN)
                is_clickable = etype in (UIElementType.BUTTON, UIElementType.LINK, UIElementType.TAB, UIElementType.CHECKBOX, UIElementType.RADIO_BUTTON, UIElementType.MENU_ITEM)
                is_input = etype in (UIElementType.INPUT, UIElementType.COMBO_BOX)
                is_scroll = (etype == UIElementType.SCROLL_AREA) or ("scroll" in role_str.lower())

                # If element has valid geometry and is meaningful, store it
                if w > 4 and h > 4 and (label or val_str or is_clickable or is_input or is_scroll):
                    visited += 1
                    elem = SemanticElement.create(
                        element_id=f"ax_{visited}_{role_str}",
                        element_type=etype,
                        label=label or val_str or role_str,
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                        role=role_str,
                        value=val_str,
                        is_clickable=is_clickable,
                        is_input=is_input,
                        is_focused=is_focused,
                        is_enabled=is_enabled,
                        is_selected=is_selected,
                        is_scrollable=is_scroll,
                        source="accessibility",
                        confidence=1.0,
                        ax_ref=node,
                    )
                    elements.append(elem)

                # Traverse children
                err_c, children = AS.AXUIElementCopyAttributeValue(node, AS.kAXChildrenAttribute, None)
                if err_c == 0 and children:
                    for child in children:
                        _traverse(child, depth + 1)

            _traverse(front_win, 0)
            return app_name, win_title, elements

        except Exception as exc:
            logger.debug("Exception inspecting accessibility tree: %s", exc)
            return app_name, "", []

    @staticmethod
    def perform_action_on_element(elem: SemanticElement, action: str = "AXPress") -> bool:
        """Trigger native accessibility action directly on the element."""
        if not elem.ax_ref:
            return False
        try:
            err = AS.AXUIElementPerformAction(elem.ax_ref, action)
            return err == 0
        except Exception as exc:
            logger.debug("AX action failed on %s: %s", elem.label, exc)
            return False
