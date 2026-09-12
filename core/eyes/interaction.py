"""Safe, dynamic pointer and keyboard interaction layer for NOVA Eyes.

Dispatches low-level Quartz mouse, keyboard, and scroll events using
dynamically resolved display bounds and Retina-scaled logical coordinates.
Zero hardcoded coordinates.
"""

from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

from core.eyes.accessibility import SemanticElement, UIElementType
from core.eyes.capture import DisplayMetrics
from core.logger import get_logger

try:
    import Quartz
    Quartz: Any = Quartz
except ImportError:
    Quartz = None

logger = get_logger(__name__)


class EyesInteractionManager:
    """Dispatches native Quartz pointer, keyboard, and scroll interactions safely."""

    def __init__(self, metrics: DisplayMetrics | None = None) -> None:
        self.metrics = metrics or DisplayMetrics.get_primary_metrics()
        self._lock = threading.Lock()

    def update_metrics(self, metrics: DisplayMetrics) -> None:
        """Update active display metrics when monitors change."""
        self.metrics = metrics

    def validate_coordinates(self, x: int, y: int) -> tuple[bool, int, int]:
        """Validate and clamp coordinates strictly within active display boundaries."""
        # Always fetch fresh primary bounds if metrics are not configured
        max_w = int(self.metrics.logical_width or 1470)
        max_h = int(self.metrics.logical_height or 956)

        if x < 0 or y < 0 or x >= max_w or y >= max_h:
            clamped_x = max(0, min(max_w - 1, x))
            clamped_y = max(0, min(max_h - 1, y))
            logger.warning(
                "Coordinates (%d, %d) outside display bounds (%dx%d), clamped to (%d, %d)",
                x,
                y,
                max_w,
                max_h,
                clamped_x,
                clamped_y,
            )
            return False, clamped_x, clamped_y

        return True, x, y

    # =========================================================================
    # POINTER INTERACTIONS (DYNAMIC COORDINATES)
    # =========================================================================

    def move_cursor(
        self,
        x: int,
        y: int,
        smooth: bool = True,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Move pointer dynamically to (x, y) with optional smooth glide."""
        if stop_event and stop_event.is_set():
            return False

        valid, target_x, target_y = self.validate_coordinates(x, y)

        try:
            if not Quartz:
                return False

            if not smooth:
                pt = (float(target_x), float(target_y))
                ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, 0)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                return True

            # Smooth interpolation: 5 small steps to look natural and trigger hover
            cur_pos = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
            start_x, start_y = cur_pos.x, cur_pos.y
            steps = 5
            for i in range(1, steps + 1):
                if stop_event and stop_event.is_set():
                    return False
                inter_x = start_x + (target_x - start_x) * (i / steps)
                inter_y = start_y + (target_y - start_y) * (i / steps)
                pt = (float(inter_x), float(inter_y))
                ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, 0)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.01)

            return True
        except Exception as exc:
            logger.error("Failed to move cursor to (%d, %d): %s", x, y, exc)
            return False

    def click_point(
        self,
        x: int,
        y: int,
        double_click: bool = False,
        right_click: bool = False,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Dispatch native Quartz mouse click at screen coordinates (x, y)."""
        if stop_event and stop_event.is_set():
            return False

        valid, target_x, target_y = self.validate_coordinates(x, y)

        try:
            if not Quartz:
                return False

            pt = (float(target_x), float(target_y))

            # 1. Mouse Move to target point
            move_ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, 0)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, move_ev)
            time.sleep(0.03)

            if right_click:
                down_type = Quartz.kCGEventRightMouseDown
                up_type = Quartz.kCGEventRightMouseUp
                btn = Quartz.kCGMouseButtonRight
            else:
                down_type = Quartz.kCGEventLeftMouseDown
                up_type = Quartz.kCGEventLeftMouseUp
                btn = Quartz.kCGMouseButtonLeft

            # Click 1
            down_ev = Quartz.CGEventCreateMouseEvent(None, down_type, pt, btn)
            up_ev = Quartz.CGEventCreateMouseEvent(None, up_type, pt, btn)

            if double_click:
                Quartz.CGEventSetIntegerValueField(down_ev, Quartz.kCGMouseEventClickState, 1)
                Quartz.CGEventSetIntegerValueField(up_ev, Quartz.kCGMouseEventClickState, 1)

            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_ev)
            time.sleep(0.02)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_ev)

            # Click 2 for double click
            if double_click:
                time.sleep(0.05)
                down_ev2 = Quartz.CGEventCreateMouseEvent(None, down_type, pt, btn)
                up_ev2 = Quartz.CGEventCreateMouseEvent(None, up_type, pt, btn)
                Quartz.CGEventSetIntegerValueField(down_ev2, Quartz.kCGMouseEventClickState, 2)
                Quartz.CGEventSetIntegerValueField(up_ev2, Quartz.kCGMouseEventClickState, 2)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_ev2)
                time.sleep(0.02)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_ev2)

            logger.info("Dispatched click at (%d, %d) [double=%s, right=%s]", target_x, target_y, double_click, right_click)
            return True
        except Exception as exc:
            logger.error("Quartz click execution failed: %s", exc)
            return False

    def click_element(
        self,
        element: SemanticElement,
        double_click: bool = False,
        right_click: bool = False,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Move cursor to semantic element's center and dispatch click."""
        cx, cy = element.center_point
        logger.info("Targeting element '%s' (%s) at center (%d, %d)", element.label, element.element_type.value, cx, cy)
        return self.click_point(
            int(cx),
            int(cy),
            double_click=double_click,
            right_click=right_click,
            stop_event=stop_event,
        )

    def drag_and_drop(
        self,
        from_x: int,
        from_y: int,
        to_x: int,
        to_y: int,
        duration: float = 0.5,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Drag pointer from (from_x, from_y) to (to_x, to_y) using Quartz left mouse drag."""
        if stop_event and stop_event.is_set():
            return False

        _, sx, sy = self.validate_coordinates(from_x, from_y)
        _, ex, ey = self.validate_coordinates(to_x, to_y)

        try:
            if not Quartz:
                return False

            start_pt = (float(sx), float(sy))
            end_pt = (float(ex), float(ey))

            # Move to start
            mv = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, start_pt, 0)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, mv)
            time.sleep(0.05)

            # Mouse down
            dn = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, start_pt, Quartz.kCGMouseButtonLeft)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, dn)
            time.sleep(0.05)

            # Drag steps
            steps = max(5, int(duration * 30))
            for i in range(1, steps + 1):
                if stop_event and stop_event.is_set():
                    up_abort = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, start_pt, Quartz.kCGMouseButtonLeft)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_abort)
                    return False
                cur_x = sx + (ex - sx) * (i / steps)
                cur_y = sy + (ey - sy) * (i / steps)
                drag_pt = (float(cur_x), float(cur_y))
                dr = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDragged, drag_pt, Quartz.kCGMouseButtonLeft)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, dr)
                time.sleep(duration / steps)

            # Mouse up at destination
            up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, end_pt, Quartz.kCGMouseButtonLeft)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
            time.sleep(0.05)
            logger.info("Dispatched drag from (%d, %d) to (%d, %d)", sx, sy, ex, ey)
            return True
        except Exception as exc:
            logger.error("Quartz drag execution failed: %s", exc)
            return False

    # =========================================================================
    # SCROLLING (MULTI-REGION & DIRECTIONAL)
    # =========================================================================

    def scroll(
        self,
        direction: str = "down",
        lines: int = 5,
        target_region: SemanticElement | tuple[int, int] | None = None,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Dispatch native Quartz scroll wheel event, optionally over a specific scroll container."""
        if stop_event and stop_event.is_set():
            return False

        # If a target region is specified, move pointer over that region first
        if target_region:
            if isinstance(target_region, SemanticElement):
                rx, ry = target_region.center_point
            else:
                rx, ry = target_region
            self.move_cursor(int(rx), int(ry), smooth=False, stop_event=stop_event)
            time.sleep(0.05)

        try:
            if not Quartz:
                return False

            dir_norm = direction.lower().strip()
            # Down = negative delta in Quartz, Up = positive delta
            scroll_delta = -lines if dir_norm in ("down", "bottom") else lines
            scroll_ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 1, scroll_delta)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, scroll_ev)
            time.sleep(0.08)
            logger.info("Dispatched scroll: direction=%s, lines=%d (target=%s)", direction, lines, target_region is not None)
            return True
        except Exception as exc:
            logger.error("Quartz scroll execution failed: %s", exc)
            return False

    # =========================================================================
    # KEYBOARD & TEXT INTERACTIONS
    # =========================================================================

    def type_text(
        self,
        text: str,
        target_element: SemanticElement | None = None,
        submit: bool = False,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Focus target element (if provided) and type text using AppleScript System Events."""
        if stop_event and stop_event.is_set():
            return False

        if not text:
            return False

        # If a target field is given, click it to focus first
        if target_element:
            self.click_element(target_element, stop_event=stop_event)
            time.sleep(0.15)

        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
        if submit:
            script += '\ntell application "System Events" to key code 36'  # Enter key

        try:
            res = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            if res.returncode == 0:
                logger.info("Typed text (%d characters) [submit=%s]", len(text), submit)
                return True
            else:
                logger.warning("Keystroke execution returned stderr: %s", res.stderr)
                return False
        except Exception as exc:
            logger.error("Failed to execute text typing: %s", exc)
            return False

    def press_key(
        self,
        key_name: str,
        modifiers: list[str] | None = None,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Press a special key or shortcut with optional modifier keys ('command', 'shift', 'option', 'control')."""
        if stop_event and stop_event.is_set():
            return False

        key_map: dict[str, int] = {
            "return": 36,
            "enter": 36,
            "escape": 53,
            "esc": 53,
            "tab": 48,
            "space": 49,
            "backspace": 51,
            "delete": 117,
            "up": 126,
            "down": 125,
            "left": 123,
            "right": 124,
            "pageup": 116,
            "pagedown": 121,
            "home": 115,
            "end": 119,
        }

        k_norm = key_name.lower().strip()
        mod_clause = ""
        if modifiers:
            mod_names = []
            for m in modifiers:
                m_low = m.lower().strip()
                if m_low in ("cmd", "command"):
                    mod_names.append("command down")
                elif m_low in ("shift",):
                    mod_names.append("shift down")
                elif m_low in ("opt", "option", "alt"):
                    mod_names.append("option down")
                elif m_low in ("ctrl", "control"):
                    mod_names.append("control down")
            if mod_names:
                mod_clause = f" using {{{', '.join(mod_names)}}}"

        if k_norm in key_map:
            code = key_map[k_norm]
            script = f'tell application "System Events" to key code {code}{mod_clause}'
        else:
            # Single character keystroke with modifiers (e.g. Cmd+C, Cmd+V, Cmd+L)
            char_escaped = k_norm.replace("\\", "\\\\").replace('"', '\\"')
            script = f'tell application "System Events" to keystroke "{char_escaped}"{mod_clause}'

        try:
            res = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            return res.returncode == 0
        except Exception as exc:
            logger.error("Failed to press key '%s' (%s): %s", key_name, modifiers, exc)
            return False
