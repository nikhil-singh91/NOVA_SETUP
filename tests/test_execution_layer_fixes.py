"""Integration tests verifying the execution layer fixes for MacCommand and TaskContext.

Covers all 19 mandatory test commands:
1. increase volume
2. decrease volume
3. set volume to 70%
4. increase volume to 80%
5. increase brightness
6. decrease brightness
7. set brightness to 80%
8. increase brightness to 70%
9. open Telegram
10. open Telegram app
11. Nova open Telegram
12. Now open Telegram
13. open YouTube app
14. open VS Code
15. close Telegram
16. capture screenshot
17. start screen recording
18. scroll down
19. scroll to bottom
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from core.task_agent.models import TaskContext
from intent.models import CanonicalIntent
from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand
from main import NovaApplication, TurnRequest
from ui.health_checker import DashboardStatsManager


@pytest.fixture
def app():
    app_instance = NovaApplication()
    app_instance._delivered = []
    app_instance._deliver_response = lambda text, tid: app_instance._delivered.append(text)
    return app_instance


class TestConstructorInterfaces:
    """Test MacCommand, ExecutionResult, and TaskContext signatures."""

    def test_mac_command_raw_input_and_raw_text(self):
        cmd1 = MacCommand(category=CommandCategory.VOLUME, action="increase", raw_input="inc")
        assert cmd1.raw_input == "inc"
        assert cmd1.raw_text == "inc"

        cmd2 = MacCommand(category=CommandCategory.VOLUME, action="increase", raw_text="inc text")
        assert cmd2.raw_input == "inc text"
        assert cmd2.raw_text == "inc text"

    def test_execution_result_with_error(self):
        res = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="Test failed",
            command_name="Cmd",
            category=CommandCategory.VOLUME,
            error="Details error"
        )
        assert res.error == "Details error"

    def test_task_context_register_application(self):
        ctx = TaskContext(task_id="t1")
        ctx.register_application("Telegram")
        assert "Telegram" in ctx.opened_apps
        assert ctx.last_opened_target == "Telegram"
        assert ctx.variables["last_app"] == "Telegram"


class TestMandatoryCommandExecution:
    """Test the complete execution pipeline for all 19 mandatory commands."""

    @pytest.mark.parametrize(
        "query, expected_intent, expected_act, val_check",
        [
            ("increase volume", CanonicalIntent.CONTROL_VOLUME, "increase", None),
            ("decrease volume", CanonicalIntent.CONTROL_VOLUME, "decrease", None),
            ("set volume to 70%", CanonicalIntent.CONTROL_VOLUME, "set", 70),
            ("increase volume to 80%", CanonicalIntent.CONTROL_VOLUME, "set", 80),
            ("decrease volume to 30%", CanonicalIntent.CONTROL_VOLUME, "set", 30),
        ],
    )
    def test_volume_execution_pipeline(self, app, query, expected_intent, expected_act, val_check):
        with patch("mac_control.actions.volume._get_current_volume", return_value=50), \
             patch("mac_control.actions.volume.set_volume_level", side_effect=lambda v: v):
            app._process_turn(TurnRequest(source="voice", text=query))

        inter = DashboardStatsManager._current_interaction
        assert inter is not None
        assert inter.status == "COMPLETED"
        assert inter.result_success is True
        assert len(app._delivered) > 0
        delivered = app._delivered[-1]
        assert "Done Boss" in delivered
        if val_check is not None:
            assert f"{val_check}%" in delivered

    @pytest.mark.parametrize(
        "query, expected_intent, expected_act, val_check",
        [
            ("increase brightness", CanonicalIntent.CONTROL_BRIGHTNESS, "increase", None),
            ("decrease brightness", CanonicalIntent.CONTROL_BRIGHTNESS, "decrease", None),
            ("set brightness to 80%", CanonicalIntent.CONTROL_BRIGHTNESS, "set", 80),
            ("increase brightness to 70%", CanonicalIntent.CONTROL_BRIGHTNESS, "set", 70),
            ("Make my screen brightness 70%", CanonicalIntent.CONTROL_BRIGHTNESS, "set", 70),
        ],
    )
    def test_brightness_execution_pipeline(self, app, query, expected_intent, expected_act, val_check):
        mock_res = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Brightness set to {val_check}%" if val_check else "Brightness increased",
            command_name="Brightness Control",
            category=CommandCategory.BRIGHTNESS
        )
        with patch("mac_control.actions.brightness.execute_brightness_command", return_value=mock_res):
            app._process_turn(TurnRequest(source="voice", text=query))

        inter = DashboardStatsManager._current_interaction
        assert inter is not None
        assert inter.status == "COMPLETED"
        assert inter.result_success is True
        assert len(app._delivered) > 0
        delivered = app._delivered[-1]
        assert "Done Boss" in delivered

    @pytest.mark.parametrize(
        "query, expected_app",
        [
            ("open Telegram", "Telegram"),
            ("open Telegram app", "Telegram"),
            ("Nova open Telegram", "Telegram"),
            ("Now open Telegram", "Telegram"),
            ("open YouTube app", "YouTube"),
            ("open VS Code", "Visual Studio Code"),
        ],
    )
    def test_app_launch_pipeline(self, app, query, expected_app):
        with patch("desktop.apps.AppLauncher.launch", return_value=(True, f"{expected_app} launched successfully.", f"{expected_app} is open, Boss.")):
            app._process_turn(TurnRequest(source="voice", text=query))

        inter = DashboardStatsManager._current_interaction
        assert inter is not None
        assert inter.status == "COMPLETED"
        assert inter.result_success is True
        assert f"{expected_app} launched successfully." in inter.result_message
        assert expected_app in app.active_task_context.opened_apps
        assert app._delivered[-1] == f"{expected_app} is open, Boss."

    def test_close_telegram(self, app):
        with patch("desktop.apps.AppLauncher.close", return_value=(True, "Telegram closed successfully.", "Telegram is closed, Boss.")):
            app._process_turn(TurnRequest(source="voice", text="close Telegram"))

        inter = DashboardStatsManager._current_interaction
        assert inter is not None
        assert inter.status == "COMPLETED"
        assert inter.result_success is True
        assert app._delivered[-1] == "Telegram is closed, Boss."

    def test_capture_screenshot(self, app):
        mock_shot = MagicMock(success=True, saved_path="/Users/test/Desktop/screenshot.png")
        with patch("core.screenshot.screenshot_service.capture_full_screen", return_value=mock_shot):
            app._process_turn(TurnRequest(source="voice", text="capture screenshot"))

        inter = DashboardStatsManager._current_interaction
        assert inter is not None
        assert inter.status == "COMPLETED"
        assert inter.result_success is True
        assert "Screenshot captured successfully" in app._delivered[-1]

    def test_start_screen_recording(self, app):
        mock_rec = MagicMock(success=True, spoken_response="Screen recording started, Boss.")
        with patch.object(app.screen_recording_manager, "start_recording", return_value=mock_rec):
            app._process_turn(TurnRequest(source="voice", text="start screen recording"))

        inter = DashboardStatsManager._current_interaction
        assert inter is not None
        assert inter.result_success is True
        assert app._delivered[-1] == "Screen recording started, Boss."

    def test_scroll_down(self, app):
        with patch("browser.engine.MacOSNativeBrowserEngine.scroll_page") as mock_scroll:
            app._process_turn(TurnRequest(source="voice", text="scroll down"))
            mock_scroll.assert_called_once()

        inter = DashboardStatsManager._current_interaction
        assert inter is not None
        assert "Scrolled" in app._delivered[-1]

    def test_scroll_to_bottom(self, app):
        with patch("browser.engine.MacOSNativeBrowserEngine.scroll_to_bottom") as mock_scroll:
            app._process_turn(TurnRequest(source="voice", text="scroll to bottom"))
            mock_scroll.assert_called_once()

        inter = DashboardStatsManager._current_interaction
        assert inter is not None
        assert "Scrolled" in app._delivered[-1]
