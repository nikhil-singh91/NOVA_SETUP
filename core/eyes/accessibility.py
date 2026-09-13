"""Native macOS Accessibility (AXUIElement) inspection and semantic element extraction.

Traverses the active window hierarchy to extract buttons, text fields, links, tabs,
dialogs, scroll areas, and media elements with exact logical screen geometry and state.
Includes event-driven NSWorkspace lifecycle observers and sensitive data detection.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import AppKit

AppKit: Any = AppKit
NSWorkspace: Any = getattr(AppKit, "NSWorkspace", None)
import ApplicationServices

AS: Any = ApplicationServices
from core.logger import get_logger

try:
    import objc
    objc: Any = objc
except ImportError:
    objc = None

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
    TABLE = "table"
    ROW = "row"
    SLIDER = "slider"
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
    is_sensitive: bool = False                      # Passwords, credentials, OTP
    source: str = "accessibility"                   # "accessibility" or "vision_ocr"
    confidence: float = 1.0
    ax_ref: Any = None                             # Native AXUIElement reference if available
    subrole: str = ""
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
        is_sensitive: bool = False,
        source: str = "accessibility",
        confidence: float = 1.0,
        ax_ref: Any = None,
        subrole: str = "",
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SemanticElement:
        # Parse positional args if passed
        if len(args) >= 2:
            first = args[0]
            is_first_type = isinstance(first, UIElementType) or (
                isinstance(first, str) and any(first == e.value for e in UIElementType)
            )
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
        etype = (
            UIElementType(element_type)
            if isinstance(element_type, str)
            else (element_type or UIElementType.UNKNOWN)
        )
        eid = element_id or f"elem_{int(time.time() * 1000)}"
        lbl = str(label or "")
        val_x = float(x if x is not None else 0.0)
        val_y = float(y if y is not None else 0.0)
        val_w = float(width if width is not None else 0.0)
        val_h = float(height if height is not None else 0.0)

        center_x = val_x + (val_w / 2.0)
        center_y = val_y + (val_h / 2.0)

        # Check sensitivity
        sensitive_kw = {"password", "passwd", "pin", "otp", "cvv", "security code", "secret"}
        check_text = f"{lbl} {value} {subrole}".lower()
        if not is_sensitive:
            is_sensitive = subrole == "AXSecureTextField" or any(kw in check_text for kw in sensitive_kw)

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
            is_sensitive=is_sensitive,
            source=source,
            confidence=confidence,
            ax_ref=ax_ref,
            subrole=subrole,
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
    "AXTable": UIElementType.TABLE,
    "AXRow": UIElementType.ROW,
    "AXSlider": UIElementType.SLIDER,
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

    def get_focused_element(self, pid: int | None = None) -> SemanticElement | None:
        """Directly query the currently focused AX element in the frontmost application."""
        if not self.is_trusted():
            return None

        if pid is None or pid <= 0:
            _, pid = self.get_frontmost_app_info()
            if pid <= 0:
                return None

        try:
            app_ref = AS.AXUIElementCreateApplication(pid)
            err, foc_node = AS.AXUIElementCopyAttributeValue(app_ref, AS.kAXFocusedUIElementAttribute, None)
            if err != 0 or not foc_node:
                return None

            return self._node_to_semantic_element(foc_node, element_id="focused_element")
        except Exception as exc:
            logger.debug("Failed to query focused AX element: %s", exc)
            return None

    def _node_to_semantic_element(self, node: Any, element_id: str) -> SemanticElement | None:
        """Convert a native AXUIElement node into a SemanticElement."""
        try:
            err, role = AS.AXUIElementCopyAttributeValue(node, AS.kAXRoleAttribute, None)
            if err != 0 or not role:
                return None

            role_str = str(role)
            err_sub, subrole = AS.AXUIElementCopyAttributeValue(node, AS.kAXSubroleAttribute, None)
            subrole_str = str(subrole or "")

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

            err_t, title_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXTitleAttribute, None)
            err_d, desc_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXDescriptionAttribute, None)
            err_v, val_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXValueAttribute, None)

            label = str(title_val or desc_val or "").strip()
            val_str = str(val_val or "").strip()

            err_f, foc_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXFocusedAttribute, None)
            err_e, en_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXEnabledAttribute, None)
            err_s, sel_val = AS.AXUIElementCopyAttributeValue(node, AS.kAXSelectedAttribute, None)

            is_focused = bool(foc_val) if err_f == 0 else False
            is_enabled = bool(en_val) if err_e == 0 else True
            is_selected = bool(sel_val) if err_s == 0 else False

            etype = ROLE_MAP.get(role_str, UIElementType.UNKNOWN)
            is_clickable = etype in (
                UIElementType.BUTTON,
                UIElementType.LINK,
                UIElementType.TAB,
                UIElementType.CHECKBOX,
                UIElementType.RADIO_BUTTON,
                UIElementType.MENU_ITEM,
            )
            is_input = etype in (UIElementType.INPUT, UIElementType.COMBO_BOX)
            is_scroll = (etype == UIElementType.SCROLL_AREA) or ("scroll" in role_str.lower())
            is_sensitive = subrole_str == "AXSecureTextField"

            return SemanticElement.create(
                element_id=element_id,
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
                is_sensitive=is_sensitive,
                source="accessibility",
                confidence=1.0,
                ax_ref=node,
                subrole=subrole_str,
            )
        except Exception:
            return None

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
            logger.debug("macOS Accessibility permission not granted. AX inspection unavailable.")
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

                elem = self._node_to_semantic_element(node, element_id=f"ax_{visited}_{depth}")
                if elem and elem.width > 4 and elem.height > 4:
                    if elem.label or elem.value or elem.is_clickable or elem.is_input or elem.is_scrollable:
                        visited += 1
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


# =============================================================================
# EVENT-DRIVEN NSWORKSPACE NOTIFICATION OBSERVER
# =============================================================================

_WorkspaceNotificationBridge: Any = None
if objc is not None:
    try:
        class _WorkspaceNotificationBridgeClass(objc.lookUpClass("NSObject")):
            """Receives NSWorkspace application and display transition notifications."""

            def initWithCallback_(self, callback: Any) -> Any:
                self = objc.super(_WorkspaceNotificationBridgeClass, self).init()
                if self is None:
                    return None
                self._callback = callback
                return self

            def workspaceEventReceived_(self, notif: Any) -> None:
                try:
                    name = str(notif.name() or "")
                    app_name = ""
                    user_info = notif.userInfo()
                    if user_info and "NSWorkspaceApplicationKey" in user_info:
                        app = user_info["NSWorkspaceApplicationKey"]
                        app_name = str(app.localizedName() or "")
                    if self._callback:
                        self._callback(name, app_name)
                except Exception as exc:
                    logger.debug("Workspace notification error: %s", exc)

        _WorkspaceNotificationBridge = _WorkspaceNotificationBridgeClass
    except Exception:
        _WorkspaceNotificationBridge = None


class WorkspaceEventsObserver:
    """Subscribes to macOS desktop lifecycle events (app activate, launch, terminate, display change)."""

    def __init__(self, on_change_callback: Callable[[str, str], None]) -> None:
        self.callback = on_change_callback
        self._bridge: Any = None
        self._is_observing = False

    def start(self) -> bool:
        """Register observers with NSWorkspace notification center."""
        if _WorkspaceNotificationBridge is None or not NSWorkspace:
            return False

        try:
            ws = NSWorkspace.sharedWorkspace()
            nc = ws.notificationCenter()
            self._bridge = _WorkspaceNotificationBridge.alloc().initWithCallback_(self.callback)

            events = [
                AppKit.NSWorkspaceDidActivateApplicationNotification,
                AppKit.NSWorkspaceDidLaunchApplicationNotification,
                AppKit.NSWorkspaceDidTerminateApplicationNotification,
                AppKit.NSWorkspaceDidHideApplicationNotification,
                AppKit.NSWorkspaceDidUnhideApplicationNotification,
            ]
            if hasattr(AppKit, "NSWorkspaceActiveDisplayDidChangeNotification"):
                events.append(AppKit.NSWorkspaceActiveDisplayDidChangeNotification)

            for ev in events:
                nc.addObserver_selector_name_object_(
                    self._bridge,
                    "workspaceEventReceived:",
                    ev,
                    None,
                )

            self._is_observing = True
            logger.info("WorkspaceEventsObserver active (event-driven desktop transitions).")
            return True
        except Exception as exc:
            logger.debug("Failed to register workspace observers: %s", exc)
            return False

    def stop(self) -> None:
        """Unregister observers cleanly."""
        if not self._is_observing or not self._bridge or not NSWorkspace:
            return

        try:
            ws = NSWorkspace.sharedWorkspace()
            nc = ws.notificationCenter()
            nc.removeObserver_(self._bridge)
        except Exception as exc:
            logger.debug("Error stopping workspace observer: %s", exc)
        finally:
            self._bridge = None
            self._is_observing = False
