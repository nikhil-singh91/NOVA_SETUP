"""Comprehensive Natural Language Variation Test Suite for NOVA V3.5."""

import pytest
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent


@pytest.fixture
def intent_engine():
    return NaturalLanguageIntentEngine()


class TestNaturalLanguageVariations:
    """Test direct, wake-word prefixed, conversational, and alternative phrasing across all major domains."""

    # 1. APPLICATION CONTROL
    @pytest.mark.parametrize(
        "phrase",
        [
            "Open VS Code",
            "Launch VS Code",
            "Start VS Code",
            "NOVA, open VS Code",
            "Hey NOVA, launch VS Code",
            "Can you please open VS Code?",
            "Could you launch VS Code for me?",
            "I want you to open VS Code",
            "Please start VS Code",
        ],
    )
    def test_app_launch_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.LAUNCH_APP
        assert action.parameters.get("app_name") == "Visual Studio Code"

    # 2. FILESYSTEM ACTIONS
    @pytest.mark.parametrize(
        "phrase",
        [
            "Create a folder called DSA on Desktop",
            "Make a folder called DSA on Desktop",
            "NOVA, create a folder called DSA on Desktop",
            "Can you please create a folder called DSA on Desktop?",
            "I want you to create a folder called DSA on Desktop",
            "Please make a folder called DSA on Desktop",
        ],
    )
    def test_create_folder_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.CREATE_DESKTOP_FOLDER
        assert action.parameters.get("folder_name") == "DSA"

    # 3. BROWSER NAVIGATION & IN-SITE SEARCH
    @pytest.mark.parametrize(
        "phrase",
        [
            "Go to AKTU website",
            "Open AKTU website",
            "Navigate to AKTU website",
            "NOVA, go to AKTU website",
            "Can you open AKTU website?",
            "Please take me to AKTU website",
        ],
    )
    def test_open_website_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.OPEN_WEBSITE
        assert "aktu" in action.parameters.get("entity", "").lower()

    @pytest.mark.parametrize(
        "phrase",
        [
            "In Flipkart search mobile phones",
            "NOVA, in Flipkart search mobile phones",
            "Can you in Flipkart search mobile phones?",
            "Search mobile phones in Flipkart",
        ],
    )
    def test_in_site_search_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.SEARCH_WEBSITE
        assert action.parameters.get("site").lower() == "flipkart"
        assert action.parameters.get("query").lower() == "mobile phones"

    # 4. MEDIA & MUSIC PLAYBACK
    @pytest.mark.parametrize(
        "phrase",
        [
            "Play Kesariya",
            "Play the song Kesariya",
            "NOVA, play Kesariya",
            "Hey NOVA, can you play Kesariya?",
            "I want to listen to Kesariya",
            "Please play Kesariya on YouTube",
        ],
    )
    def test_media_playback_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent in (CanonicalIntent.PLAY_MEDIA, CanonicalIntent.PLAY_SPECIFIC_SONG)
        assert "kesariya" in action.parameters.get("query", "").lower()

    # 5. CAMERA ACTIONS
    @pytest.mark.parametrize(
        "phrase",
        [
            "Open camera",
            "Launch camera",
            "Open Photo Booth",
            "NOVA, open camera",
            "Can you please launch the camera?",
        ],
    )
    def test_open_camera_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.OPEN_CAMERA

    @pytest.mark.parametrize(
        "phrase",
        [
            "Take a photo",
            "Take a picture",
            "Take my picture",
            "Click a photo",
            "Capture a photo",
            "NOVA, take a picture",
            "Can you take a picture?",
        ],
    )
    def test_take_photo_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.TAKE_PHOTO

    # 6. CLIPBOARD ACTIONS
    @pytest.mark.parametrize(
        "phrase",
        [
            "What is in my clipboard?",
            "What's in my clipboard?",
            "Show my clipboard",
            "What did I copy?",
            "NOVA, what is in my clipboard?",
        ],
    )
    def test_get_clipboard_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.GET_CLIPBOARD

    @pytest.mark.parametrize(
        "phrase",
        [
            "Clear my clipboard",
            "Empty the clipboard",
            "Clear clipboard",
            "NOVA, clear my clipboard",
        ],
    )
    def test_clear_clipboard_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.CLEAR_CLIPBOARD

    # 7. WI-FI & BLUETOOTH
    @pytest.mark.parametrize(
        "phrase",
        [
            "Turn on Wi-Fi",
            "Enable Wi-Fi",
            "Turn off Wi-Fi",
            "Disable Wi-Fi",
            "Is Wi-Fi on?",
        ],
    )
    def test_wifi_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.CONTROL_WIFI

    @pytest.mark.parametrize(
        "phrase",
        [
            "Turn on Bluetooth",
            "Enable Bluetooth",
            "Turn off Bluetooth",
            "Disable Bluetooth",
            "Is Bluetooth on?",
        ],
    )
    def test_bluetooth_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.CONTROL_BLUETOOTH

    # 8. TASK CONTROL & CANCELLATION
    @pytest.mark.parametrize(
        "phrase",
        [
            "Stop",
            "Cancel",
            "Never mind",
            "Abort",
            "Stop doing that",
            "Don't continue",
            "NOVA, stop",
            "रहने दो",
            "रुको",
        ],
    )
    def test_cancel_variations(self, intent_engine, phrase):
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.CANCEL_ACTION
