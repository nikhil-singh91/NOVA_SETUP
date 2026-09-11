"""Comprehensive test suite for NOVA Eyes + Computer Interaction System.

Tests in-memory display capture, native Accessibility extraction, Apple Vision OCR,
Retina coordinate mapping, target resolution, pointer/keyboard interaction,
post-action verification, and ComputerAgent orchestration.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.computer_agent import ComputerAgent
from core.eyes import (
    AccessibilityInspector,
    ActionType,
    ConfidenceLevel,
    DisplayMetrics,
    EyesInteractionManager,
    EyesStateVerifier,
    EyesTargetResolver,
    MemoryFrame,
    NovaEyesManager,
    ScreenCapturer,
    ScreenState,
    SemanticElement,
    UIElementType,
    VerificationOutcome,
    VisionOCR,
    nova_eyes,
)


# =============================================================================
# 1. DISPLAY METRICS & RETINA COORDINATES
# =============================================================================

def test_display_metrics_query() -> None:
    """Verify primary display metrics query returns valid geometry and Retina scale."""
    metrics = DisplayMetrics.get_primary_metrics()
    assert metrics.logical_width > 0
    assert metrics.logical_height > 0
    assert metrics.pixel_width > 0
    assert metrics.pixel_height > 0
    assert metrics.scale_factor >= 1.0
    assert metrics.is_main is True


def test_interaction_coordinate_validation() -> None:
    """Verify that interaction coordinates are strictly clamped to display bounds."""
    metrics = DisplayMetrics(
        display_id=1,
        logical_x=0.0,
        logical_y=0.0,
        logical_width=1440.0,
        logical_height=900.0,
        pixel_width=2880,
        pixel_height=1800,
        scale_factor=2.0,
        is_main=True,
    )
    interaction = EyesInteractionManager(metrics=metrics)

    # Valid coordinates
    valid, x, y = interaction.validate_coordinates(500, 400)
    assert valid is True
    assert (x, y) == (500, 400)

    # Negative coordinates
    valid_neg, x_neg, y_neg = interaction.validate_coordinates(-50, -100)
    assert valid_neg is False
    assert (x_neg, y_neg) == (0, 0)

    # Out of bounds coordinates
    valid_oob, x_oob, y_oob = interaction.validate_coordinates(2000, 1500)
    assert valid_oob is False
    assert x_oob == 1439
    assert y_oob == 899


# =============================================================================
# 2. IN-MEMORY CAPTURE & ZERO DISK WRITES
# =============================================================================

def test_in_memory_capture_zero_disk_writes(tmp_path: Path) -> None:
    """Verify ScreenCapturer captures directly into RAM CGImage without writing files."""
    capturer = ScreenCapturer()
    metrics = DisplayMetrics.get_primary_metrics()

    # Capture frame
    frame = capturer.capture_frame(metrics)
    assert frame is not None
    assert frame.cg_image is not None
    assert frame.metrics == metrics
    assert len(frame.visual_hash) > 0
    assert frame.is_fresh(max_age_seconds=5.0) is True

    # Confirm no files were generated in tmp_path or default screenshot dir
    nova_snapshots = Path.home() / ".nova" / "snapshots"
    if nova_snapshots.exists():
        new_files = [f for f in nova_snapshots.glob("*.png") if f.stat().st_mtime > time.time() - 2.0]
        assert len(new_files) == 0, "No disk screenshots should be persisted by NOVA Eyes!"


# =============================================================================
# 3. SEMANTIC ELEMENT & ACCESSIBILITY INSPECTOR
# =============================================================================

def test_semantic_element_creation() -> None:
    """Verify SemanticElement properties, center point calculation, and bounding box."""
    elem = SemanticElement.create(
        element_id="elem_btn_1",
        element_type=UIElementType.BUTTON,
        label="Download Report",
        x=100.0,
        y=200.0,
        width=150.0,
        height=40.0,
        role="AXButton",
        value="",
    )
    assert elem.label == "Download Report"
    assert elem.element_type == UIElementType.BUTTON
    assert elem.bounds == (100.0, 200.0, 150.0, 40.0)
    assert elem.center_point == (175, 220)
    assert elem.is_clickable is True
    assert elem.is_input is False


def test_accessibility_inspector_live() -> None:
    """Verify AccessibilityInspector queries frontmost window elements safely."""
    inspector = AccessibilityInspector()
    app_name, win_title, elements = inspector.inspect_frontmost_window(max_depth=3, max_elements=50)

    # Should safely return app name string (even if empty in headless CI)
    assert isinstance(app_name, str)
    assert isinstance(win_title, str)
    assert isinstance(elements, list)
    for elem in elements:
        assert isinstance(elem, SemanticElement)
        assert elem.bounds[2] > 0
        assert elem.bounds[3] > 0


# =============================================================================
# 4. APPLE VISION NEURAL OCR & COORDINATE MAPPING
# =============================================================================

def test_vision_ocr_live() -> None:
    """Verify Apple Vision OCR runs on in-memory frame and returns positioned elements."""
    capturer = ScreenCapturer()
    ocr = VisionOCR(accurate=False)
    frame = capturer.capture_frame()
    assert frame is not None

    ocr_elements = ocr.recognize_text(frame)
    assert isinstance(ocr_elements, list)
    if ocr_elements:
        first = ocr_elements[0]
        assert isinstance(first, SemanticElement)
        assert len(first.label) > 0
        assert first.source == "vision_ocr"
        # Verify coordinates lie inside display boundaries
        assert 0 <= first.x <= frame.metrics.logical_width
        assert 0 <= first.y <= frame.metrics.logical_height


# =============================================================================
# 5. SCREEN STATE WORLD MODEL & FUSION
# =============================================================================

def test_screen_state_fusion_and_deduplication() -> None:
    """Verify ScreenState fuses Accessibility and OCR elements without near-duplicates."""
    metrics = DisplayMetrics.get_primary_metrics()

    ax_elem = SemanticElement.create(
        element_id="ax_1",
        element_type=UIElementType.BUTTON,
        label="Submit Order",
        x=200.0,
        y=300.0,
        width=100.0,
        height=30.0,
        role="AXButton",
    )
    # OCR element at virtually same center (250, 315)
    ocr_duplicate = SemanticElement.create(
        element_id="ocr_1",
        element_type=UIElementType.TEXT,
        label="Submit Order",
        x=202.0,
        y=301.0,
        width=98.0,
        height=28.0,
        role="OCRText",
        source="vision_ocr",
    )
    # OCR element at different location
    ocr_unique = SemanticElement.create(
        element_id="ocr_2",
        element_type=UIElementType.TEXT,
        label="Total: $49.99",
        x=500.0,
        y=600.0,
        width=120.0,
        height=25.0,
        role="OCRText",
        source="vision_ocr",
    )

    state = ScreenState.build_from_sources(
        timestamp=datetime.now(timezone.utc),
        active_app="ShoppingApp",
        active_win="Checkout",
        metrics=metrics,
        visual_hash="hash123",
        ax_elements=[ax_elem],
        ocr_elements=[ocr_duplicate, ocr_unique],
    )

    # Duplicate should be suppressed
    assert len(state.elements) == 2
    assert state.buttons == [ax_elem]
    assert "Total: $49.99" in state.visible_texts
    assert "Submit Order" in state.visible_texts


def test_screen_state_change_detection() -> None:
    """Verify ScreenState detects meaningful visual or window transitions."""
    metrics = DisplayMetrics.get_primary_metrics()
    now = datetime.now(timezone.utc)

    state_a = ScreenState(
        timestamp=now,
        active_application="Terminal",
        active_window="bash",
        metrics=metrics,
        visual_hash="hash_a",
    )
    state_same = ScreenState(
        timestamp=now,
        active_application="Terminal",
        active_window="bash",
        metrics=metrics,
        visual_hash="hash_a",
    )
    state_diff_win = ScreenState(
        timestamp=now,
        active_application="Terminal",
        active_window="zsh",
        metrics=metrics,
        visual_hash="hash_a",
    )
    state_diff_hash = ScreenState(
        timestamp=now,
        active_application="Terminal",
        active_window="bash",
        metrics=metrics,
        visual_hash="hash_b",
    )

    assert state_a.has_changed_from(None) is True
    assert state_a.has_changed_from(state_same) is False
    assert state_diff_win.has_changed_from(state_a) is True
    assert state_diff_hash.has_changed_from(state_a) is True


# =============================================================================
# 6. DYNAMIC TARGET RESOLVER (NO HARDCODED COORDINATES)
# =============================================================================

def test_target_resolver_synonyms_and_scoring() -> None:
    """Verify resolver maps synonyms (e.g. search -> query field, sign in -> login button)."""
    metrics = DisplayMetrics.get_primary_metrics()

    btn_login = SemanticElement.create(
        element_id="b1",
        element_type=UIElementType.BUTTON,
        label="Sign In to Account",
        x=800.0,
        y=50.0,
        width=120.0,
        height=35.0,
        role="AXButton",
    )
    input_search = SemanticElement.create(
        element_id="i1",
        element_type=UIElementType.INPUT,
        label="Search products and brands",
        x=200.0,
        y=50.0,
        width=400.0,
        height=35.0,
        role="AXTextField",
        is_input=True,
    )
    state = ScreenState(
        timestamp=datetime.now(timezone.utc),
        active_application="Browser",
        active_window="Store",
        metrics=metrics,
        visual_hash="hash_x",
        elements=[btn_login, input_search],
        buttons=[btn_login],
        inputs=[input_search],
    )

    # Test synonym 'login' resolving to 'Sign In'
    elem_login, conf_login, score_login = EyesTargetResolver.resolve("login button", state)
    assert elem_login == btn_login
    assert conf_login in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    # Test synonym 'find' resolving to search field
    elem_search, conf_search, score_search = EyesTargetResolver.resolve("search box", state)
    assert elem_search == input_search
    assert conf_search in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)


def test_target_resolver_ordinals() -> None:
    """Verify ordinal resolution ('click the second button', '3rd link')."""
    metrics = DisplayMetrics.get_primary_metrics()

    b1 = SemanticElement.create(UIElementType.BUTTON, "Result 1", 100.0, 100.0, 100.0, 30.0, element_id="1")
    b2 = SemanticElement.create(UIElementType.BUTTON, "Result 2", 100.0, 150.0, 100.0, 30.0, element_id="2")
    b3 = SemanticElement.create(UIElementType.BUTTON, "Result 3", 100.0, 200.0, 100.0, 30.0, element_id="3")

    state = ScreenState(
        timestamp=datetime.now(timezone.utc),
        active_application="App",
        active_window="List",
        metrics=metrics,
        visual_hash="hash_ord",
        elements=[b1, b2, b3],
        buttons=[b1, b2, b3],
    )

    elem, conf, score = EyesTargetResolver.resolve("click the second result", state)
    assert elem == b2
    assert conf == ConfidenceLevel.HIGH


# =============================================================================
# 7. STATE VERIFIER (NEVER FAKE SUCCESS)
# =============================================================================

def test_verifier_never_fakes_success() -> None:
    """Verify that verifier rejects unchanged state when action produced no observable effect."""
    metrics = DisplayMetrics.get_primary_metrics()
    now = datetime.now(timezone.utc)

    btn = SemanticElement.create(UIElementType.BUTTON, "Apply Filter", 100.0, 100.0, 80.0, 30.0, element_id="b_apply")

    state_before = ScreenState(
        timestamp=now,
        active_application="Spreadsheet",
        active_window="Data",
        metrics=metrics,
        visual_hash="identical_hash",
        elements=[btn],
    )
    state_after_identical = ScreenState(
        timestamp=now,
        active_application="Spreadsheet",
        active_window="Data",
        metrics=metrics,
        visual_hash="identical_hash",
        elements=[btn],
    )

    # Identical state must NOT report verified success
    outcome = EyesStateVerifier.verify(ActionType.CLICK, state_before, state_after_identical, btn)
    assert outcome.verified is False
    assert outcome.should_retry is True
    assert "did not produce an observable change" in outcome.summary


def test_verifier_detects_genuine_change() -> None:
    """Verify that verifier confirms success when visual hash or window title updates."""
    metrics = DisplayMetrics.get_primary_metrics()
    now = datetime.now(timezone.utc)

    btn = SemanticElement.create(UIElementType.BUTTON, "Save As", 100.0, 100.0, 80.0, 30.0, element_id="b_save")

    state_before = ScreenState(
        timestamp=now,
        active_application="TextEdit",
        active_window="Untitled.txt",
        metrics=metrics,
        visual_hash="hash_before",
        elements=[btn],
    )
    state_after_dialog = ScreenState(
        timestamp=now,
        active_application="TextEdit",
        active_window="Save File Dialog",
        metrics=metrics,
        visual_hash="hash_after_dialog",
        elements=[btn],
    )

    outcome = EyesStateVerifier.verify(ActionType.CLICK, state_before, state_after_dialog, btn)
    assert outcome.verified is True
    assert "Window title updated" in outcome.summary or "screen state changed" in outcome.summary


def test_verifier_typing_confirmation() -> None:
    """Verify typing verifier confirms text inside focused field or visible OCR."""
    metrics = DisplayMetrics.get_primary_metrics()
    now = datetime.now(timezone.utc)

    field = SemanticElement.create(
        UIElementType.INPUT,
        "Search Box",
        200.0,
        100.0,
        300.0,
        35.0,
        element_id="f1",
        value="Python asyncio",
        is_focused=True,
    )
    state_before = ScreenState(
        timestamp=now,
        active_application="Browser",
        active_window="Google",
        metrics=metrics,
        visual_hash="h1",
    )
    state_after = ScreenState(
        timestamp=now,
        active_application="Browser",
        active_window="Google",
        metrics=metrics,
        visual_hash="h2",
        elements=[field],
        focused_element=field,
        visible_texts=["Python asyncio", "Google Search"],
    )

    outcome = EyesStateVerifier.verify(ActionType.TYPE_TEXT, state_before, state_after, field, action_payload="Python asyncio")
    assert outcome.verified is True
    assert "confirmed in focused field" in outcome.summary


# =============================================================================
# 8. NOVA EYES MANAGER LIFECYCLE & ACTIVE OBSERVATION
# =============================================================================

def test_nova_eyes_manager_lifecycle() -> None:
    """Verify NovaEyesManager starts, pauses, resumes, and stops safely and idempotently."""
    manager = NovaEyesManager()

    # Start
    assert manager.start() is True
    assert manager.start() is True  # Idempotent
    assert manager.is_running is True

    # Status check
    status = manager.get_status()
    assert status["status"] == "ACTIVE"
    assert status["disk_storage"] == "OFF (0 bytes persisted)"
    assert status["recording"] == "OFF"
    assert status["cloud_streaming"] == "OFF"

    # Pause & Resume
    manager.pause()
    assert manager.is_running is False
    manager.resume()
    assert manager.is_running is True

    # Observe now on demand
    state = manager.observe_now(force_ocr=False)
    assert isinstance(state, ScreenState)
    assert state.metrics.logical_width > 0

    # Stop
    assert manager.stop() is True
    assert manager.stop() is True  # Idempotent
    assert manager.is_running is False


# =============================================================================
# 9. COMPUTER AGENT INTEGRATION (SEE -> ACT -> VERIFY)
# =============================================================================

def test_computer_agent_execute_goal_with_eyes() -> None:
    """Verify ComputerAgent orchestrates observe -> target resolve -> click -> verify pipeline."""
    metrics = DisplayMetrics.get_primary_metrics()
    now = datetime.now(timezone.utc)

    btn = SemanticElement.create(
        UIElementType.BUTTON,
        "Checkout Now",
        400.0,
        500.0,
        150.0,
        40.0,
        element_id="btn_chk",
    )

    state_before = ScreenState(
        timestamp=now,
        active_application="Safari",
        active_window="Cart",
        metrics=metrics,
        visual_hash="hash_cart",
        elements=[btn],
        buttons=[btn],
    )
    state_after = ScreenState(
        timestamp=now,
        active_application="Safari",
        active_window="Payment Gateway",
        metrics=metrics,
        visual_hash="hash_payment",
    )

    agent = ComputerAgent()

    with patch.object(agent.eyes, "observe_now", side_effect=[state_before, state_after]):
        with patch.object(agent.eyes.interaction, "click_element", return_value=True) as mock_click:
            res = agent.execute_visual_goal("Click checkout")
            assert res.success is True
            assert res.verified is True
            assert mock_click.called
            assert "Checkout Now" in res.spoken_response


def test_computer_agent_low_confidence_asks_clarification() -> None:
    """Verify ComputerAgent asks clarification instead of clicking blindly when confidence is low."""
    metrics = DisplayMetrics.get_primary_metrics()
    now = datetime.now(timezone.utc)

    state = ScreenState(
        timestamp=now,
        active_application="Desktop",
        active_window="Desktop",
        metrics=metrics,
        visual_hash="hash_empty",
        elements=[],
    )

    agent = ComputerAgent()
    with patch.object(agent.eyes, "observe_now", return_value=state):
        res = agent.execute_visual_goal("click nonexistent blue diamond widget")
        assert res.success is False
        assert "clarify" in res.spoken_response.lower()
