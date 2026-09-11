"""Unit and integration tests for ComputerAgent orchestration."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.computer_agent import ComputerAgent
from core.visual.models import (
    ScreenAnalysis,
    ScreenSnapshot,
    UIElement,
    UIElementType,
    VisualActionType,
    VisualConfidence,
)
from core.visual.observer import ScreenObserver


def test_computer_agent_execute_goal(tmp_path: Path) -> None:
    """Test full execute_visual_goal pipeline."""
    obs = ScreenObserver(snapshot_dir=tmp_path)
    snap = ScreenSnapshot(
        snapshot_id="snap_test",
        active_application="Google Chrome",
        active_window="Shopping",
    )
    b_search = UIElement.create(UIElementType.BUTTON, "Search", 100, 100, 80, 30)
    analysis = ScreenAnalysis(snapshot=snap, ui_elements=[b_search], buttons=[b_search])

    agent = ComputerAgent(observer=obs)

    with patch.object(obs, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=analysis):
            with patch.object(agent.interaction_mgr, "click_element", return_value=True):
                with patch("core.visual.verifier.VisualVerifier.verify_action_effect", return_value=(True, "Verified change")):
                    res = agent.execute_visual_goal("Click search")
                    assert res.success is True
                    assert res.verified is True
                    assert res.target_element == b_search


def test_computer_agent_close_popup(tmp_path: Path) -> None:
    """Test close popup automation."""
    obs = ScreenObserver(snapshot_dir=tmp_path)
    snap = ScreenSnapshot(snapshot_id="snap_popup", active_application="Safari")
    close_btn = UIElement.create(UIElementType.BUTTON, "Dismiss", 300, 300, 60, 30)
    analysis = ScreenAnalysis(snapshot=snap, ui_elements=[close_btn], buttons=[close_btn])

    agent = ComputerAgent(observer=obs)

    with patch.object(obs, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=analysis):
            with patch.object(agent.interaction_mgr, "click_element", return_value=True):
                res = agent.close_popup()
                assert res.success is True
                assert "Dismiss" in res.spoken_response or "popup" in res.spoken_response.lower()


def test_computer_agent_scroll_until_visible(tmp_path: Path) -> None:
    """Test scroll_until_visible bounded loop."""
    obs = ScreenObserver(snapshot_dir=tmp_path)
    snap = ScreenSnapshot(snapshot_id="snap_scroll", active_application="Chrome")

    # Step 1: Target not visible
    analysis1 = ScreenAnalysis(snapshot=snap, visible_text=["Intro", "Products"])
    # Step 2: Target visible
    contact_elem = UIElement.create(UIElementType.LINK, "Contact Us", 100, 500, 100, 30)
    analysis2 = ScreenAnalysis(snapshot=snap, ui_elements=[contact_elem], visible_text=["Intro", "Products", "Contact Us"])

    agent = ComputerAgent(observer=obs)

    with patch.object(obs, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", side_effect=[analysis1, analysis2]):
            with patch.object(agent.interaction_mgr, "scroll", return_value=True):
                res = agent.scroll_until_visible("Contact Us", max_scrolls=3)
                assert res.success is True
                assert "Contact Us" in res.spoken_response


def test_computer_agent_cancellation(tmp_path: Path) -> None:
    """Test agent cancellation during multi-step execution."""
    obs = ScreenObserver(snapshot_dir=tmp_path)
    snap = ScreenSnapshot(snapshot_id="snap_cancel", active_application="Chrome")
    analysis = ScreenAnalysis(snapshot=snap, visible_text=["Intro"])

    agent = ComputerAgent(observer=obs)
    agent.stop_active_task()

    with patch.object(obs, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=analysis):
            res = agent.scroll_until_visible("Pricing", max_scrolls=5)
            assert res.success is False
            assert "cancelled" in res.message.lower() or "stopped" in res.spoken_response.lower()
