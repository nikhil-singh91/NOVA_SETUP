"""Safe pointer and keyboard interaction manager for NOVA Visual Agent."""

from __future__ import annotations

import subprocess
import threading
import time
from typing import Any

from core.environment import environment_observer
from core.logger import get_logger

try:
    import Quartz
    Quartz: Any = Quartz
except ImportError:
    Quartz = None
from core.visual.models import (
    ScreenSnapshot,
    UIElement,
)

logger = get_logger(__name__)


class ComputerInteractionManager:
    """Dispatches low-level mouse and keyboard events safely using macOS Quartz APIs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def validate_coordinates(self, x: int, y: int, screen_w: int = 1470, screen_h: int = 956) -> tuple[bool, int, int]:
        """Clamp coordinates and verify they lie strictly inside the active display boundaries."""
        try:
            if not Quartz:
                return True, x, y
            main_id = Quartz.CGMainDisplayID()
            w = int(Quartz.CGDisplayPixelsWide(main_id)) or screen_w
            h = int(Quartz.CGDisplayPixelsHigh(main_id)) or screen_h
        except Exception:
            w, h = screen_w, screen_h

        # Strict boundary check with margin
        if x < 0 or y < 0 or x > w or y > h:
            clamped_x = max(0, min(w - 1, x))
            clamped_y = max(0, min(h - 1, y))
            logger.warning("Coordinates (%d, %d) were out of bounds, clamped to (%d, %d)", x, y, clamped_x, clamped_y)
            return False, clamped_x, clamped_y

        return True, x, y

    def is_snapshot_stale(self, snapshot: ScreenSnapshot | None, max_age_seconds: float = 5.0) -> tuple[bool, str]:
        """Verify that the target snapshot is fresh and matches current frontmost application state."""
        if snapshot is None:
            return True, "No snapshot provided."

        if snapshot.age_seconds > max_age_seconds:
            return True, f"Snapshot is stale ({snapshot.age_seconds:.1f}s > {max_age_seconds}s limit)."

        # Check frontmost application continuity
        ctx = environment_observer.get_context()
        if snapshot.active_application and ctx.active_application:
            if snapshot.active_application.lower() != ctx.active_application.lower():
                return True, f"Active app switched from '{snapshot.active_application}' to '{ctx.active_application}'."

        return False, "Snapshot is fresh."

    def click_element(
        self,
        element: UIElement,
        snapshot: ScreenSnapshot | None = None,
        double_click: bool = False,
        right_click: bool = False,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Move pointer and click the center point of an identified UI element."""
        if stop_event and stop_event.is_set():
            logger.info("Click cancelled by stop event.")
            return False

        # Staleness protection
        stale, reason = self.is_snapshot_stale(snapshot)
        if stale:
            logger.warning("Aborting click due to staleness: %s", reason)
            return False

        cx, cy = element.center_point
        valid, x, y = self.validate_coordinates(cx, cy)
        if not valid:
            logger.warning("Element center coordinates (%d, %d) failed boundary validation", cx, cy)

        return self.click_point(x, y, double_click=double_click, right_click=right_click, stop_event=stop_event)

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

        try:
            if not Quartz:
                return False

            pt = (float(x), float(y))

            # 1. Mouse Move
            move_ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, 0)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, move_ev)
            time.sleep(0.04)

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
            time.sleep(0.03)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_ev)

            # Click 2 for double click
            if double_click:
                time.sleep(0.05)
                down_ev2 = Quartz.CGEventCreateMouseEvent(None, down_type, pt, btn)
                up_ev2 = Quartz.CGEventCreateMouseEvent(None, up_type, pt, btn)
                Quartz.CGEventSetIntegerValueField(down_ev2, Quartz.kCGMouseEventClickState, 2)
                Quartz.CGEventSetIntegerValueField(up_ev2, Quartz.kCGMouseEventClickState, 2)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_ev2)
                time.sleep(0.03)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, up_ev2)

            logger.info("Dispatched pointer click at (%d, %d) [double=%s, right=%s]", x, y, double_click, right_click)
            return True
        except Exception as exc:
            logger.error("Quartz click execution failed: %s", exc)
            return False

    def scroll(self, direction: str = "down", lines: int = 5, stop_event: threading.Event | None = None) -> bool:
        """Dispatch native Quartz scroll wheel event."""
        if stop_event and stop_event.is_set():
            return False

        try:
            if not Quartz:
                return False
            scroll_delta = -lines if direction.lower() == "down" else lines
            scroll_ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 1, scroll_delta)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, scroll_ev)
            time.sleep(0.1)
            logger.info("Dispatched scroll event: direction=%s, lines=%d", direction, lines)
            return True
        except Exception as exc:
            logger.error("Quartz scroll execution failed: %s", exc)
            return False

    def type_text(self, text: str, submit: bool = False, stop_event: threading.Event | None = None) -> bool:
        """Type text safely into active focused element via AppleScript or Quartz keystrokes."""
        if stop_event and stop_event.is_set():
            return False

        if not text:
            return False

        # Escape special characters for AppleScript keystroke
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
        if submit:
            script += '\ntell application "System Events" to key code 36'  # Enter key

        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0:
                logger.info("Typed text (%d characters) [submit=%s]", len(text), submit)
                return True
            else:
                logger.warning("Keystroke execution returned error: %s", res.stderr)
                return False
        except Exception as exc:
            logger.error("Failed to execute text input: %s", exc)
            return False

    def press_key(self, key_name: str, stop_event: threading.Event | None = None) -> bool:
        """Press a special key (e.g. 'return', 'escape', 'tab', 'space')."""
        if stop_event and stop_event.is_set():
            return False

        key_map = {
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
        }
        code = key_map.get(key_name.lower().strip())
        if code is None:
            return False

        script = f'tell application "System Events" to key code {code}'
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2.0)
            return res.returncode == 0
        except Exception as exc:
            logger.error("Failed to press key '%s': %s", key_name, exc)
            return False
