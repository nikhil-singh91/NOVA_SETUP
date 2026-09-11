"""Real-world Voice V2 & Environment Awareness 15-Point Test Matrix."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from core.environment import EnvironmentContext, environment_observer
from main import NovaApplication, TurnRequest


def test_full_15_point_voice_environment_matrix(tmp_path: Path) -> None:
    """Execute the full 15-point real-world command matrix through NovaApplication turn pipeline."""
    app = NovaApplication()
    # Mock voice speaker and network side effects for deterministic evaluation
    app.voice_available = False
    app.desktop_manager.initialize()
    app.browser_manager.initialize()

    delivered_responses: list[str] = []

    def fake_deliver(resp_text: str, turn_id: str) -> None:
        delivered_responses.append(resp_text)

    app._deliver_response = fake_deliver  # type: ignore

    # Test Results Matrix Log
    matrix_results: list[dict[str, str]] = []

    # Helper function to run a turn and record results
    def run_matrix_turn(cmd: str, mock_context: EnvironmentContext | None = None) -> str:
        delivered_responses.clear()
        if mock_context:
            with patch.object(environment_observer, "refresh", return_value=mock_context):
                with patch.object(environment_observer, "get_context", return_value=mock_context):
                    app._process_turn(TurnRequest(source="voice", text=cmd))
        else:
            app._process_turn(TurnRequest(source="voice", text=cmd))
        return delivered_responses[-1] if delivered_responses else ""

    # =========================================================================
    # 1. "Nova go to AKTU website"
    # =========================================================================
    with patch("browser.engine.MacOSNativeBrowserEngine.open_url", return_value=True) as mock_open:
        resp = run_matrix_turn("Nova go to AKTU website")
        assert "aktu" in resp.lower() or "opening" in resp.lower()
        mock_open.assert_called()
        matrix_results.append({"cmd": "Nova go to AKTU website", "result": resp, "status": "PASS"})

    # =========================================================================
    # 2. "Nova open Flipkart"
    # =========================================================================
    with patch("browser.engine.MacOSNativeBrowserEngine.open_url", return_value=True) as mock_open:
        resp = run_matrix_turn("Nova open Flipkart")
        assert "flipkart" in resp.lower()
        mock_open.assert_called()
        matrix_results.append({"cmd": "Nova open Flipkart", "result": resp, "status": "PASS"})

    # =========================================================================
    # 3. "Nova search mobile phones in Flipkart"
    # =========================================================================
    with patch("browser.engine.MacOSNativeBrowserEngine.open_url", return_value=True) as mock_open:
        resp = run_matrix_turn("Nova search mobile phones in Flipkart")
        assert "flipkart" in resp.lower() and "mobile phones" in resp.lower()
        mock_open.assert_called()
        matrix_results.append({"cmd": "Nova search mobile phones in Flipkart", "result": resp, "status": "PASS"})

    # =========================================================================
    # 4. "Nova create a folder called Test on Desktop"
    # =========================================================================
    desktop_mock_root = tmp_path / "MockDesktop"
    desktop_mock_root.mkdir()
    with patch("pathlib.Path.home", return_value=tmp_path):
        resp = run_matrix_turn("Nova create a folder called Test on Desktop")
        assert "Created folder Test on your Desktop" in resp or "Test" in resp
        matrix_results.append({"cmd": "Nova create a folder called Test on Desktop", "result": resp, "status": "PASS"})

    # =========================================================================
    # 5. "Nova open DSA folder"
    # =========================================================================
    dsa_dir = tmp_path / "DSA"
    dsa_dir.mkdir()
    with patch("desktop.files.FileSystemManager.find_folders_by_name", return_value=[dsa_dir]):
        with patch("subprocess.run"):
            resp = run_matrix_turn("Nova open DSA folder")
            assert "Opened DSA folder in Finder" in resp
            matrix_results.append({"cmd": "Nova open DSA folder", "result": resp, "status": "PASS"})

    # =========================================================================
    # 6. "Nova create main.cpp inside the DSA folder"
    # =========================================================================
    with patch("desktop.files.FileSystemManager.find_folders_by_name", return_value=[dsa_dir]):
        resp = run_matrix_turn("Nova create main.cpp inside the DSA folder")
        assert "main.cpp" in resp and "DSA" in resp
        assert (dsa_dir / "main.cpp").exists()
        matrix_results.append({"cmd": "Nova create main.cpp inside the DSA folder", "result": resp, "status": "PASS"})

    # =========================================================================
    # 7. "Nova write an application for college leave"
    # =========================================================================
    with patch("desktop.apps.AppLauncher.launch", return_value=(True, "Opened", "Opened")):
        resp = run_matrix_turn("Nova write an application for college leave")
        assert "leave" in resp.lower() and "TextEdit" in resp
        matrix_results.append({"cmd": "Nova write an application for college leave", "result": resp, "status": "PASS"})

    # =========================================================================
    # 8. "Nova open Notepad and write a leave application"
    # =========================================================================
    with patch("desktop.apps.AppLauncher.launch", return_value=(True, "Opened", "Opened")):
        resp = run_matrix_turn("Nova open Notepad and write a leave application")
        assert "leave" in resp.lower() and "TextEdit" in resp
        matrix_results.append({"cmd": "Nova open Notepad and write a leave application", "result": resp, "status": "PASS"})

    # =========================================================================
    # 9. "Nova, I want to go to the market at 8 PM"
    # =========================================================================
    resp = run_matrix_turn("Nova, I want to go to the market at 8 PM")
    assert "8 PM" in resp
    matrix_results.append({"cmd": "Nova, I want to go to the market at 8 PM", "result": resp, "status": "PASS"})

    # =========================================================================
    # 10. "Nova play Shorts"
    # =========================================================================
    with patch("browser.engine.MacOSNativeBrowserEngine.open_url", return_value=True) as mock_open:
        resp = run_matrix_turn("Nova play Shorts")
        assert "shorts" in resp.lower()
        mock_open.assert_called()
        matrix_results.append({"cmd": "Nova play Shorts", "result": resp, "status": "PASS"})

    # =========================================================================
    # 11. "Nova open YouTube Shorts"
    # =========================================================================
    with patch("browser.engine.MacOSNativeBrowserEngine.open_url", return_value=True) as mock_open:
        resp = run_matrix_turn("Nova open YouTube Shorts")
        assert "shorts" in resp.lower()
        mock_open.assert_called()
        matrix_results.append({"cmd": "Nova open YouTube Shorts", "result": resp, "status": "PASS"})

    # =========================================================================
    # 12 & 14. "Nova record screen" & "Nova stop screen recording"
    # =========================================================================
    mock_proc = MagicMock()
    mock_proc.pid = 9999
    mock_proc.poll.return_value = None

    def fake_wait(timeout=None):
        if app.screen_recording_manager._active_file:
            app.screen_recording_manager._active_file.write_bytes(b"\x00\x00\x00\x1cftypqt  " + b"\x00" * 2048)
        return 0

    mock_proc.wait.side_effect = fake_wait

    with patch("subprocess.Popen", return_value=mock_proc):
        with patch("os.killpg"):
            with patch("os.getpgid", return_value=9999):
                # 12. Start Recording
                resp_rec = run_matrix_turn("Nova record screen")
                assert "Screen recording started" in resp_rec
                matrix_results.append({"cmd": "Nova record screen", "result": resp_rec, "status": "PASS"})

                # 13. Wait
                time.sleep(0.05)

                # 14. Stop Recording
                resp_stop = run_matrix_turn("Nova stop screen recording")
                assert "saved successfully" in resp_stop or "saved to" in resp_stop
                matrix_results.append({"cmd": "Nova stop screen recording", "result": resp_stop, "status": "PASS"})

    # =========================================================================
    # 15. Context Resolution Tests ("this", "that", "it", "here")
    # =========================================================================
    # 15A: "Search iPhone here" on active Flipkart tab
    browser_ctx = EnvironmentContext(
        active_application="Google Chrome",
        current_url="https://www.flipkart.com",
        current_domain="flipkart.com",
        current_page_title="Flipkart",
    )
    with patch("browser.engine.MacOSNativeBrowserEngine.open_url", return_value=True) as mock_open:
        resp_here = run_matrix_turn("Search iPhone here", mock_context=browser_ctx)
        assert "flipkart" in resp_here.lower() and "iphone" in resp_here.lower()
        mock_open.assert_called()
        matrix_results.append({"cmd": "Search iPhone here", "result": resp_here, "status": "PASS"})

    # 15B: "Delete this" on active selected file
    active_pdf = tmp_path / "homework.pdf"
    active_pdf.write_text("test")
    finder_ctx = EnvironmentContext(
        active_application="Finder",
        selected_file_or_folder=active_pdf,
        selected_files=[active_pdf],
        current_folder=tmp_path,
    )
    resp_del = run_matrix_turn("Delete this", mock_context=finder_ctx)
    assert "homework.pdf" in resp_del
    matrix_results.append({"cmd": "Delete this", "result": resp_del, "status": "PASS"})

    # 15C: "What am I looking at?" on active web page
    resp_look = run_matrix_turn("What am I looking at?", mock_context=browser_ctx)
    assert "Flipkart" in resp_look or "webpage" in resp_look
    matrix_results.append({"cmd": "What am I looking at?", "result": resp_look, "status": "PASS"})

    assert len(matrix_results) >= 15
    for r in matrix_results:
        assert r["status"] == "PASS"
