"""Unit tests for UITargetResolver candidate ranking and confidence scoring."""

from __future__ import annotations

from core.visual.models import (
    ScreenAnalysis,
    ScreenSnapshot,
    UIElement,
    UIElementType,
    VisualConfidence,
)
from core.visual.resolver import UITargetResolver


def test_resolve_exact_button() -> None:
    """Test exact button resolution with high confidence."""
    snap = ScreenSnapshot(snapshot_id="snap_1")
    b1 = UIElement.create(UIElementType.BUTTON, "Search", 100, 100, 80, 30)
    b2 = UIElement.create(UIElementType.BUTTON, "Cancel", 200, 100, 80, 30)
    analysis = ScreenAnalysis(snapshot=snap, ui_elements=[b1, b2], buttons=[b1, b2])

    elem, conf, score = UITargetResolver.resolve_target("Click search", analysis)
    assert elem == b1
    assert conf == VisualConfidence.HIGH
    assert score >= 0.85


def test_resolve_ordinal_element() -> None:
    """Test ordinal selection: 'click the second result'."""
    snap = ScreenSnapshot(snapshot_id="snap_2")
    r1 = UIElement.create(UIElementType.LINK, "Apple iPhone 15", 50, 100, 300, 40)
    r2 = UIElement.create(UIElementType.LINK, "Apple iPhone 15 Pro", 50, 160, 300, 40)
    r3 = UIElement.create(UIElementType.LINK, "Apple iPhone 14", 50, 220, 300, 40)
    analysis = ScreenAnalysis(snapshot=snap, ui_elements=[r1, r2, r3])

    elem, conf, score = UITargetResolver.resolve_target("Click the second result", analysis)
    assert elem == r2


def test_resolve_popup_close_button() -> None:
    """Test popup close button resolution."""
    snap = ScreenSnapshot(snapshot_id="snap_3")
    sheet = UIElement.create(UIElementType.POPUP, "Cookie Consent", 200, 200, 400, 300)
    close_btn = UIElement.create(UIElementType.BUTTON, "Got It", 350, 450, 100, 35)
    analysis = ScreenAnalysis(
        snapshot=snap,
        ui_elements=[sheet, close_btn],
        dialogs=[sheet],
        buttons=[close_btn],
    )

    elem, conf, score = UITargetResolver.resolve_target("Close this popup", analysis)
    assert elem == close_btn
    assert conf == VisualConfidence.HIGH


def test_low_confidence_unmatched() -> None:
    """Test low confidence return when element is not present."""
    snap = ScreenSnapshot(snapshot_id="snap_4")
    b1 = UIElement.create(UIElementType.BUTTON, "Submit", 100, 100, 80, 30)
    analysis = ScreenAnalysis(snapshot=snap, ui_elements=[b1], buttons=[b1])

    elem, conf, score = UITargetResolver.resolve_target("Click the mysterious astronaut icon", analysis)
    assert conf == VisualConfidence.LOW
