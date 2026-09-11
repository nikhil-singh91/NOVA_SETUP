"""Unit tests for Visual Interaction models and schemas."""

from __future__ import annotations

import time
from pathlib import Path
from core.visual.models import (
    ScreenAnalysis,
    ScreenSnapshot,
    UIElement,
    UIElementType,
    VisualConfidence,
)


def test_ui_element_creation() -> None:
    """Test UIElement creation and center point calculation."""
    elem = UIElement.create(
        element_type=UIElementType.BUTTON,
        label="Search",
        x=100,
        y=200,
        w=80,
        h=40,
        confidence=0.95,
    )
    assert elem.type == UIElementType.BUTTON
    assert elem.label == "Search"
    assert elem.bounding_box == (100, 200, 80, 40)
    assert elem.center_point == (140, 220)
    assert elem.confidence == 0.95


def test_screen_snapshot_freshness(tmp_path: Path) -> None:
    """Test ScreenSnapshot freshness validation."""
    snap = ScreenSnapshot(
        snapshot_id="snap_123",
        image_path=tmp_path / "test.png",
        active_application="Google Chrome",
        active_window="Flipkart",
        screen_hash="abc123hash",
    )
    assert snap.is_fresh(max_age_seconds=2.0) is True
    assert snap.age_seconds >= 0.0


def test_screen_analysis_find_elements() -> None:
    """Test element filtering and search in ScreenAnalysis."""
    snap = ScreenSnapshot(snapshot_id="snap_456")
    b1 = UIElement.create(UIElementType.BUTTON, "Login", 10, 10, 50, 30)
    b2 = UIElement.create(UIElementType.BUTTON, "Sign Up", 70, 10, 60, 30)
    tf1 = UIElement.create(UIElementType.INPUT, "Search Box", 10, 50, 200, 30)

    analysis = ScreenAnalysis(
        snapshot=snap,
        ui_elements=[b1, b2, tf1],
        buttons=[b1, b2],
        inputs=[tf1],
        visible_text=["Welcome", "Login", "Sign Up"],
    )

    found_login = analysis.find_elements_by_label("login")
    assert len(found_login) == 1
    assert found_login[0] == b1

    found_inputs = analysis.find_elements_by_label("search", element_type=UIElementType.INPUT)
    assert len(found_inputs) == 1
    assert found_inputs[0] == tf1
