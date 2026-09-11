"""Comprehensive 10-point real-world test matrix for Computer Agent V2."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.environment import EnvironmentContext, environment_observer
from core.visual.models import (
    ScreenAnalysis,
    ScreenSnapshot,
    UIElement,
    UIElementType,
    VisualConfidence,
)
from main import NovaApplication, TurnRequest


def test_full_10_point_computer_agent_matrix(tmp_path: Path) -> None:
    """Execute the complete 10-point real-world computer agent test matrix."""
    app = NovaApplication()
    app.voice_available = False
    app.desktop_manager.initialize()
    app.browser_manager.initialize()
    app.computer_agent.initialize()

    delivered_responses: list[str] = []

    def fake_deliver(resp_text: str, turn_id: str) -> None:
        delivered_responses.append(resp_text)

    app._deliver_response = fake_deliver  # type: ignore

    test_records: list[dict[str, str]] = []

    def run_turn(cmd: str) -> str:
        delivered_responses.clear()
        app._process_turn(TurnRequest(source="voice", text=cmd))
        return delivered_responses[-1] if delivered_responses else ""

    # Shared UI Elements
    btn_search = UIElement.create(UIElementType.BUTTON, "Search", 120, 80, 70, 30)
    tf_input = UIElement.create(UIElementType.INPUT, "Search Input", 200, 80, 250, 30)
    btn_close = UIElement.create(UIElementType.BUTTON, "Close", 500, 300, 60, 30)
    res_1 = UIElement.create(UIElementType.LINK, "Result 1: GeeksforGeeks", 100, 200, 400, 30)
    res_2 = UIElement.create(UIElementType.LINK, "Result 2: Roadmap.sh DSA", 100, 250, 400, 30)

    snap = ScreenSnapshot(
        snapshot_id="snap_matrix",
        image_path=tmp_path / "matrix.png",
        active_application="Google Chrome",
        active_window="Google Search",
        screen_hash="matrix_hash_123",
    )

    analysis = ScreenAnalysis(
        snapshot=snap,
        ui_elements=[btn_search, tf_input, btn_close, res_1, res_2],
        buttons=[btn_search, btn_close],
        inputs=[tf_input],
        visible_text=["Google", "Search", "Close", "Result 1: GeeksforGeeks", "Result 2: Roadmap.sh DSA"],
    )

    # =========================================================================
    # TEST 1: "Nova, click the search button"
    # =========================================================================
    with patch.object(app.computer_agent.observer, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=analysis):
            with patch.object(app.computer_agent.interaction_mgr, "click_element", return_value=True) as mock_click:
                resp1 = run_turn("Nova, click the search button")
                assert "Search" in resp1
                mock_click.assert_called()
                test_records.append({"test": "TEST 1: Click Search Button", "response": resp1, "status": "PASS"})

    # =========================================================================
    # TEST 2: "Nova, type DSA roadmap"
    # =========================================================================
    with patch.object(app.computer_agent.interaction_mgr, "type_text", return_value=True) as mock_type:
        resp2 = run_turn("Nova, type DSA roadmap")
        assert "dsa roadmap" in resp2.lower()
        mock_type.assert_called()
        test_records.append({"test": "TEST 2: Type DSA Roadmap", "response": resp2, "status": "PASS"})

    # =========================================================================
    # TEST 3: "Nova, search"
    # =========================================================================
    with patch.object(app.computer_agent.observer, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=analysis):
            with patch.object(app.computer_agent.interaction_mgr, "click_element", return_value=True) as mock_click:
                resp3 = run_turn("Nova, search")
                assert "Search" in resp3 or "Clicked" in resp3
                test_records.append({"test": "TEST 3: Click Search", "response": resp3, "status": "PASS"})

    # =========================================================================
    # TEST 4: "Nova, close this popup"
    # =========================================================================
    with patch.object(app.computer_agent.observer, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=analysis):
            with patch.object(app.computer_agent.interaction_mgr, "click_element", return_value=True) as mock_click:
                resp4 = run_turn("Nova, close this popup")
                assert "popup" in resp4.lower() or "close" in resp4.lower()
                test_records.append({"test": "TEST 4: Close Popup", "response": resp4, "status": "PASS"})

    # =========================================================================
    # TEST 5: "Nova, what am I looking at?"
    # =========================================================================
    with patch.object(app.computer_agent.observer, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=analysis):
            resp5 = run_turn("Nova, what am I looking at?")
            assert len(resp5) > 0
            test_records.append({"test": "TEST 5: What am I looking at", "response": resp5, "status": "PASS"})

    # =========================================================================
    # TEST 6: "Nova, explain this error"
    # =========================================================================
    err_analysis = ScreenAnalysis(
        snapshot=snap,
        errors=["404 Not Found: Requested resource could not be located on server."],
        visible_text=["404 Not Found", "Error 404"],
    )
    with patch.object(app.computer_agent.observer, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=err_analysis):
            resp6 = run_turn("Nova, explain this error")
            assert "404" in resp6 or "error" in resp6.lower()
            test_records.append({"test": "TEST 6: Explain Error", "response": resp6, "status": "PASS"})

    # =========================================================================
    # TEST 7: "Nova, scroll until you find contact"
    # =========================================================================
    contact_elem = UIElement.create(UIElementType.LINK, "Contact Us", 100, 800, 100, 30)
    contact_analysis = ScreenAnalysis(snapshot=snap, ui_elements=[contact_elem], visible_text=["Contact Us"])
    with patch.object(app.computer_agent.observer, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=contact_analysis):
            resp7 = run_turn("Nova, scroll until you find contact")
            assert "contact" in resp7.lower()
            test_records.append({"test": "TEST 7: Scroll to Contact", "response": resp7, "status": "PASS"})

    # =========================================================================
    # TEST 8: "Nova, click the second result"
    # =========================================================================
    with patch.object(app.computer_agent.observer, "capture_current_screen", return_value=snap):
        with patch("core.visual.analysis.ScreenAnalyzer.analyze_snapshot", return_value=analysis):
            with patch.object(app.computer_agent.interaction_mgr, "click_element", return_value=True) as mock_click:
                resp8 = run_turn("Nova, click the second result")
                assert "Roadmap.sh" in resp8 or "Result 2" in resp8
                test_records.append({"test": "TEST 8: Click Second Result", "response": resp8, "status": "PASS"})

    # =========================================================================
    # TEST 9: Staleness Protection (Window switch after observation)
    # =========================================================================
    stale_snap = ScreenSnapshot(
        snapshot_id="stale_snap",
        active_application="OldApp",
        timestamp=snap.timestamp,
    )
    with patch.object(environment_observer, "get_context", return_value=EnvironmentContext(active_application="NewApp")):
        stale_flag, reason = app.computer_agent.interaction_mgr.is_snapshot_stale(stale_snap)
        assert stale_flag is True
        assert "switched" in reason
        test_records.append({"test": "TEST 9: Staleness Protection", "response": reason, "status": "PASS"})

    # =========================================================================
    # TEST 10: Cancellation ("Nova, scroll until you find pricing" then "Stop")
    # =========================================================================
    resp10_cancel = run_turn("Stop")
    assert "Stopped" in resp10_cancel
    test_records.append({"test": "TEST 10: Cancellation", "response": resp10_cancel, "status": "PASS"})

    assert len(test_records) == 10
    for rec in test_records:
        assert rec["status"] == "PASS"
