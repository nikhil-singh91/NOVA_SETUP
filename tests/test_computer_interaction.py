"""Unit tests for ComputerInteractionManager coordinates validation and staleness protection."""

from __future__ import annotations

import threading
import time

from core.visual.interaction import ComputerInteractionManager
from core.visual.models import ScreenSnapshot, UIElement, UIElementType


def test_coordinate_boundary_clamping() -> None:
    """Validate that out-of-bounds coordinates are clamped."""
    mgr = ComputerInteractionManager()
    valid, cx, cy = mgr.validate_coordinates(-50, 2000, screen_w=1470, screen_h=956)
    assert valid is False
    assert cx == 0
    assert cy == 955


def test_staleness_rejection() -> None:
    """Validate that stale snapshots reject pointer clicks."""
    mgr = ComputerInteractionManager()
    old_snap = ScreenSnapshot(
        snapshot_id="old_snap",
        active_application="Safari",
    )
    # Simulate aging
    time.sleep(0.05)
    stale, reason = mgr.is_snapshot_stale(old_snap, max_age_seconds=0.01)
    assert stale is True
    assert "stale" in reason.lower()


def test_click_cancellation() -> None:
    """Validate that an active stop event cancels pointer clicks."""
    mgr = ComputerInteractionManager()
    elem = UIElement.create(UIElementType.BUTTON, "Submit", 100, 100, 50, 30)
    stop_ev = threading.Event()
    stop_ev.set()

    success = mgr.click_element(elem, stop_event=stop_ev)
    assert success is False
