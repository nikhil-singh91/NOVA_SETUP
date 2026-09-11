"""Unit and integration tests for volume/brightness parameters, Wi-Fi/Bluetooth state, scrolling, and writing flows."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from intent.matcher import LinguisticIntentMatcher
from intent.models import CanonicalIntent
from mac_control.models import MacCommand, CommandCategory, ExecutionStatus
from mac_control.actions.volume import get_volume_level, set_volume_level, execute_volume_command
from mac_control.actions.brightness import get_brightness_level, set_brightness_level, execute_brightness_command
from mac_control.actions.wifi import get_wifi_status, get_current_ssid, get_wifi_info, execute_wifi_command
from mac_control.actions.bluetooth import get_bluetooth_status, set_bluetooth_power, execute_bluetooth_command
from desktop.editor import DocumentEditor
from desktop.parser import DesktopIntentParser
from desktop.models import DesktopActionType


class TestParameterControlAndWriting(unittest.TestCase):
    def setUp(self):
        self.matcher = LinguisticIntentMatcher()

    # ==========================================
    # 1. VOLUME INTENT & PARAMETER TESTS
    # ==========================================
    def test_volume_intent_patterns(self):
        # Set / Absolute
        res = self.matcher.match("set volume to 70%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "set")
        self.assertEqual(res.parameters["value"], 70)

        res = self.matcher.match("increase volume to 100%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "set")
        self.assertEqual(res.parameters["value"], 100)

        res = self.matcher.match("increase 70% volume")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "set")
        self.assertEqual(res.parameters["value"], 70)

        res = self.matcher.match("70% volume")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "set")
        self.assertEqual(res.parameters["value"], 70)

        res = self.matcher.match("decrease volume to 30%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "set")
        self.assertEqual(res.parameters["value"], 30)

        # Relative By
        res = self.matcher.match("increase volume by 20%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "increase")
        self.assertEqual(res.parameters["step"], 20)
        self.assertTrue(res.parameters.get("is_relative"))

        res = self.matcher.match("decrease volume by 10%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "decrease")
        self.assertEqual(res.parameters["step"], 10)
        self.assertTrue(res.parameters.get("is_relative"))

        # Mute / Unmute
        res = self.matcher.match("mute volume")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "mute")

        res = self.matcher.match("unmute volume")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_VOLUME)
        self.assertEqual(res.parameters["action"], "unmute")

    # ==========================================
    # 2. BRIGHTNESS INTENT & PARAMETER TESTS
    # ==========================================
    def test_brightness_intent_patterns(self):
        res = self.matcher.match("set brightness to 70%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_BRIGHTNESS)
        self.assertEqual(res.parameters["action"], "set")
        self.assertEqual(res.parameters["value"], 70)

        res = self.matcher.match("increase brightness to 100%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_BRIGHTNESS)
        self.assertEqual(res.parameters["action"], "set")
        self.assertEqual(res.parameters["value"], 100)

        res = self.matcher.match("increase brightness by 10%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_BRIGHTNESS)
        self.assertEqual(res.parameters["action"], "increase")
        self.assertEqual(res.parameters["step"], 10)

        res = self.matcher.match("decrease brightness by 10%")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.CONTROL_BRIGHTNESS)
        self.assertEqual(res.parameters["action"], "decrease")
        self.assertEqual(res.parameters["step"], 10)

    # ==========================================
    # 3. VOLUME & BRIGHTNESS EXECUTION LOGIC
    # ==========================================
    @patch("mac_control.actions.volume.get_volume_level", return_value=50)
    @patch("mac_control.actions.volume.set_volume_level", side_effect=lambda v: v)
    def test_volume_execution(self, mock_set, mock_get):
        # Absolute set
        cmd = MacCommand(category=CommandCategory.VOLUME, action="set", args={"value": 70})
        res = execute_volume_command(cmd)
        self.assertEqual(res.status, ExecutionStatus.SUCCESS)
        self.assertIn("70%", res.message)

        # Relative increase
        cmd = MacCommand(category=CommandCategory.VOLUME, action="increase", args={"step": 20})
        res = execute_volume_command(cmd)
        self.assertEqual(res.status, ExecutionStatus.SUCCESS)

    @patch("mac_control.actions.brightness.get_brightness_level", return_value=80)
    @patch("mac_control.actions.brightness.set_brightness_level", side_effect=lambda v: v)
    def test_brightness_execution(self, mock_set, mock_get):
        with patch("mac_control.actions.brightness._has_display_services", False):
            cmd = MacCommand(category=CommandCategory.BRIGHTNESS, action="set", args={"value": 80})
            res = execute_brightness_command(cmd)
            self.assertEqual(res.status, ExecutionStatus.SUCCESS)
            self.assertIn("80%", res.message)

    # ==========================================
    # 4. WI-FI CONTROL & STATUS TESTS
    # ==========================================
    def test_wifi_intent_patterns(self):
        for phrase in [
            "check wifi", "check my wifi", "is wifi on", "is my wifi on",
            "what wifi am i connected to", "which wifi am i connected to",
            "tell me my wifi", "wifi status", "what network am i connected to"
        ]:
            res = self.matcher.match(phrase)
            self.assertIsNotNone(res, f"Failed to match: {phrase}")
            self.assertEqual(res.intent, CanonicalIntent.CONTROL_WIFI)
            self.assertIn(res.parameters["action"], ("status", "ssid"))

        res_on = self.matcher.match("turn wifi on")
        self.assertEqual(res_on.parameters["action"], "on")

        res_off = self.matcher.match("turn wifi off")
        self.assertEqual(res_off.parameters["action"], "off")

    @patch("mac_control.actions.wifi.get_wifi_info", return_value={"power": "ON", "connected": True, "ssid": "Home-5G", "interface": "en0"})
    def test_wifi_status_execution(self, mock_info):
        cmd = MacCommand(category=CommandCategory.NETWORK, action="status")
        res = execute_wifi_command(cmd)
        self.assertEqual(res.status, ExecutionStatus.SUCCESS)
        self.assertIn("Home-5G", res.message)

    # ==========================================
    # 5. BLUETOOTH CONTROL & STATUS TESTS
    # ==========================================
    def test_bluetooth_intent_patterns(self):
        for phrase in [
            "check bluetooth", "check my bluetooth", "is bluetooth on",
            "is my bluetooth on or off", "bluetooth status", "tell me bluetooth status"
        ]:
            res = self.matcher.match(phrase)
            self.assertIsNotNone(res, f"Failed to match: {phrase}")
            self.assertEqual(res.intent, CanonicalIntent.CONTROL_BLUETOOTH)
            self.assertEqual(res.parameters["action"], "status")

        res_on = self.matcher.match("turn bluetooth on")
        self.assertEqual(res_on.parameters["action"], "on")

        res_off = self.matcher.match("turn bluetooth off")
        self.assertEqual(res_off.parameters["action"], "off")

    @patch("mac_control.actions.bluetooth.get_bluetooth_status", return_value=True)
    def test_bluetooth_status_execution(self, mock_status):
        cmd = MacCommand(category=CommandCategory.NETWORK, action="status")
        res = execute_bluetooth_command(cmd)
        self.assertEqual(res.status, ExecutionStatus.SUCCESS)
        self.assertIn("on", res.message.lower())

    # ==========================================
    # 6. SCROLLING TESTS (TOP, BOTTOM, UP, DOWN)
    # ==========================================
    def test_scrolling_patterns(self):
        bottom_phrases = [
            "scroll to bottom", "scroll to the bottom", "go to bottom",
            "go to the bottom", "scroll all the way down", "take me to the bottom"
        ]
        for p in bottom_phrases:
            res = self.matcher.match(p)
            self.assertIsNotNone(res, f"Failed for {p}")
            self.assertEqual(res.intent, CanonicalIntent.SCROLL_TO_BOTTOM)

        top_phrases = [
            "scroll to top", "scroll to the top", "go to top",
            "go to the top", "scroll all the way up", "take me to the top"
        ]
        for p in top_phrases:
            res = self.matcher.match(p)
            self.assertIsNotNone(res, f"Failed for {p}")
            self.assertEqual(res.intent, CanonicalIntent.SCROLL_TO_TOP)

        self.assertEqual(self.matcher.match("scroll down").intent, CanonicalIntent.SCROLL_DOWN)
        self.assertEqual(self.matcher.match("scroll up").intent, CanonicalIntent.SCROLL_UP)

    # ==========================================
    # 7. DOCUMENT & CODE WRITING TESTS (NEVER LOGGER)
    # ==========================================
    def test_writing_intent_patterns(self):
        # Code generation
        res = self.matcher.match("write a bubble sort code")
        self.assertIsNotNone(res)
        self.assertEqual(res.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)
        self.assertEqual(res.parameters["destination"], "Notepad/TextEdit")

        res_cpp = self.matcher.match("write bubble sort code in C++")
        self.assertIsNotNone(res_cpp)
        self.assertEqual(res_cpp.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)
        self.assertEqual(res_cpp.parameters["filename"], "bubble_sort.cpp")

        # Literal / plain text
        res_love = self.matcher.match("write what is love")
        self.assertIsNotNone(res_love)
        self.assertEqual(res_love.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)

        res_open_write = self.matcher.match("open notepad and write hello")
        self.assertIsNotNone(res_open_write)
        self.assertEqual(res_open_write.intent, CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT)

        # Informational explanation should NOT match writing document
        res_how = self.matcher.match("how to write a bubble sort code")
        self.assertIsNone(res_how)

    @patch("desktop.apps.AppLauncher.launch", return_value=(True, "", "Opened"))
    def test_document_editor_generation_and_execution(self, mock_launch):
        # Verify plain text generation
        text_res = DocumentEditor.generate_document_text("what is love")
        self.assertEqual(text_res, "what is love")

        # Verify C++ bubble sort generation
        cpp_code = DocumentEditor.generate_document_text("bubble sort in C++")
        self.assertIn("bubbleSort", cpp_code)
        self.assertIn("#include <iostream>", cpp_code)

        # Verify Python bubble sort generation
        py_code = DocumentEditor.generate_document_text("bubble sort in python")
        self.assertIn("def bubble_sort", py_code)

        # Verify document writing execution creates file and opens in editor
        doc_res = DocumentEditor.write_and_open_document("bubble sort code in C++", filename="bubble_sort.cpp", open_in_editor=False)
        self.assertTrue(doc_res.success)
        self.assertTrue(Path(doc_res.target_path).exists())
        self.assertIn("bubble sort", doc_res.spoken_response.lower())


if __name__ == "__main__":
    unittest.main()
