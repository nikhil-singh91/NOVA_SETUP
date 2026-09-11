"""Comprehensive regression test suite for NOVA command routing, normalization, and hardware control."""

import pytest
from unittest.mock import MagicMock, patch
from intent.engine import NaturalLanguageIntentEngine
from intent.normalizer import TextNormalizer
from intent.models import CanonicalIntent, StructuredAction
from desktop.apps import AppLauncher


@pytest.fixture
def engine():
    return NaturalLanguageIntentEngine()


class TestNormalizationAndWakeWords:
    """Test text normalizer strips wake words and filler prefixes while preserving core intent."""

    @pytest.mark.parametrize(
        "raw_text, expected_cleaned",
        [
            ("nova increase brightness", "increase brightness"),
            ("now increase brightness", "increase brightness"),
            ("boss increase the brightness", "increase the brightness"),
            ("boss, increase brightness", "increase brightness"),
            ("can you increase my screen brightness", "increase my screen brightness"),
            ("can you please make my screen brighter", "make my screen brighter"),
            ("nova open telegram", "open telegram"),
            ("now open telegram", "open telegram"),
            ("boss open telegram app", "open telegram app"),
            ("please open telegram app", "open telegram app"),
            ("hey nova, open telegram", "open telegram"),
            ("suno nova, increase brightness", "increase brightness"),
            ("can you please open telegram app for me", "open telegram app"),
        ],
    )
    def test_normalizer_cleans_conversational_wrappers(self, raw_text, expected_cleaned):
        norm = TextNormalizer.normalize(raw_text)
        assert norm.cleaned_lower == expected_cleaned.lower()


class TestBrightnessIntentClassification:
    """Test all brightness natural language variations and percentage parsing."""

    @pytest.mark.parametrize(
        "query, expected_action, expected_value",
        [
            ("increase brightness", "increase", None),
            ("increase the brightness", "increase", None),
            ("increase brightness of my Mac", "increase", None),
            ("make the screen brighter", "increase", None),
            ("make screen brighter", "increase", None),
            ("make my screen brighter", "increase", None),
            ("brightness up", "increase", None),
            ("turn up brightness", "increase", None),
            ("now increase brightness", "increase", None),
            ("nova increase brightness", "increase", None),
            ("nova, increase the brightness", "increase", None),
            ("boss increase the brightness", "increase", None),
            ("can you increase my screen brightness", "increase", None),
            ("please make my screen brighter", "increase", None),
            ("decrease brightness", "decrease", None),
            ("decrease the brightness", "decrease", None),
            ("lower screen brightness", "decrease", None),
            ("make screen darker", "decrease", None),
            ("make screen dimmer", "decrease", None),
            ("dim screen", "decrease", None),
            ("brightness down", "decrease", None),
            ("set brightness to 80%", "set", 80),
            ("set brightness to 50%", "set", 50),
            ("set brightness to 100%", "set", 100),
            ("increase brightness to 80%", "set", 80),
            ("decrease brightness to 30%", "set", 30),
            ("set my brightness to 50 percent", "set", 50),
            ("Brightness 100%", "set", 100),
            ("Make brightness 70%", "set", 70),
            ("Increase the brightness to 80 percent", "set", 80),
            ("Set my Mac brightness to 80", "set", 80),
            ("Make it 80 percent brighter", "set", 80),
            ("what is the brightness", "get", None),
            ("check brightness", "get", None),
        ],
    )
    def test_brightness_commands_matched(self, engine, query, expected_action, expected_value):
        res: StructuredAction = engine.parse(query, allow_ai_fallback=False)
        assert res.intent == CanonicalIntent.CONTROL_BRIGHTNESS, f"Failed for '{query}', got {res.intent}"
        assert res.parameters.get("action") == expected_action
        if expected_value is not None:
            assert res.parameters.get("value") == expected_value


class TestVolumeIntentClassification:
    """Test all volume natural language variations and percentage parsing."""

    @pytest.mark.parametrize(
        "query, expected_action, expected_value",
        [
            ("increase volume", "increase", None),
            ("now increase volume", "increase", None),
            ("make it louder", "increase", None),
            ("volume up", "increase", None),
            ("turn up volume", "increase", None),
            ("decrease volume", "decrease", None),
            ("volume down", "decrease", None),
            ("make it quieter", "decrease", None),
            ("lower volume", "decrease", None),
            ("set volume to 70%", "set", 70),
            ("increase volume to 80%", "set", 80),
            ("decrease volume to 30%", "set", 30),
            ("increase volume to 70 percent", "set", 70),
            ("Make volume 80", "set", 80),
            ("Set my Mac volume to 80", "set", 80),
            ("volume 100%", "set", 100),
            ("mute", "mute", None),
            ("mute volume", "mute", None),
            ("unmute", "unmute", None),
            ("unmute volume", "unmute", None),
            ("what is the volume", "get", None),
            ("check volume", "get", None),
        ],
    )
    def test_volume_commands_matched(self, engine, query, expected_action, expected_value):
        res: StructuredAction = engine.parse(query, allow_ai_fallback=False)
        assert res.intent == CanonicalIntent.CONTROL_VOLUME, f"Failed for '{query}', got {res.intent}"
        assert res.parameters.get("action") == expected_action
        if expected_value is not None:
            assert res.parameters.get("value") == expected_value


class TestAppLaunchingAndClosing:
    """Test Telegram, Sublime Text and other desktop app commands."""

    @pytest.mark.parametrize(
        "query, expected_intent, expected_app",
        [
            ("open telegram", CanonicalIntent.LAUNCH_APP, "Telegram"),
            ("open telegram app", CanonicalIntent.LAUNCH_APP, "Telegram"),
            ("now open telegram", CanonicalIntent.LAUNCH_APP, "Telegram"),
            ("nova open telegram", CanonicalIntent.LAUNCH_APP, "Telegram"),
            ("nova, open telegram app", CanonicalIntent.LAUNCH_APP, "Telegram"),
            ("launch telegram", CanonicalIntent.LAUNCH_APP, "Telegram"),
            ("start telegram", CanonicalIntent.LAUNCH_APP, "Telegram"),
            ("Please open Telegram app", CanonicalIntent.LAUNCH_APP, "Telegram"),
            ("open sublime text", CanonicalIntent.LAUNCH_APP, "Sublime Text"),
            ("close sublime text", CanonicalIntent.CLOSE_APP, "Sublime Text"),
            ("open vs code", CanonicalIntent.LAUNCH_APP, "Visual Studio Code"),
            ("quit vs code", CanonicalIntent.CLOSE_APP, "Visual Studio Code"),
        ],
    )
    def test_app_commands_matched(self, engine, query, expected_intent, expected_app):
        res: StructuredAction = engine.parse(query, allow_ai_fallback=False)
        assert res.intent == expected_intent, f"Failed for '{query}', got {res.intent}"
        assert res.parameters.get("app_name") == expected_app


class TestDesktopAndSystemFeatures:
    """Test screenshot, screen recording, scrolling, notepad writing, and hardware checks."""

    @pytest.mark.parametrize(
        "query, expected_intent",
        [
            ("capture screenshot", CanonicalIntent.SCREEN_CAPTURE),
            ("take a screenshot", CanonicalIntent.SCREEN_CAPTURE),
            ("start screen recording", CanonicalIntent.START_SCREEN_RECORDING),
            ("stop screen recording", CanonicalIntent.STOP_SCREEN_RECORDING),
            ("scroll down", CanonicalIntent.SCROLL_DOWN),
            ("scroll up", CanonicalIntent.SCROLL_UP),
            ("scroll to bottom", CanonicalIntent.SCROLL_TO_BOTTOM),
            ("write bubble sort code in notepad", CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT),
            ('write "what is love" in notepad', CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT),
            ("check bluetooth", CanonicalIntent.CONTROL_BLUETOOTH),
            ("check wifi", CanonicalIntent.CONTROL_WIFI),
            ("search for important books", CanonicalIntent.SEARCH_WEB),
            ("browse the internet and search for important books", CanonicalIntent.SEARCH_WEB),
        ],
    )
    def test_system_and_desktop_commands_matched(self, engine, query, expected_intent):
        res: StructuredAction = engine.parse(query, allow_ai_fallback=False)
        assert res.intent == expected_intent, f"Failed for '{query}', got {res.intent}"


class TestConversationalQueriesPreserved:
    """Test that pure questions and conversational queries are NOT misclassified as actions."""

    @pytest.mark.parametrize(
        "query",
        [
            ("what is love?"),
            ("how do I write bubble sort?"),
            ("what is the weather?"),
            ("tell me a joke"),
            ("who was Albert Einstein?"),
        ],
    )
    def test_conversational_queries_preserved(self, engine, query):
        res: StructuredAction = engine.parse(query, allow_ai_fallback=False)
        assert res.intent == CanonicalIntent.GENERAL_CONVERSATION, f"Misclassified '{query}' as {res.intent}"
