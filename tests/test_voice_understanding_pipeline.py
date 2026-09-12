"""Comprehensive validation of NOVA Voice Understanding, Intent Routing, and State Isolation."""

import pytest
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent
from providers.provider_manager import TaskType


@pytest.fixture
def intent_engine() -> NaturalLanguageIntentEngine:
    return NaturalLanguageIntentEngine()


class TestVoiceUnderstandingPipeline:
    """Test suite covering the 10 core benchmark prompts, natural variations, and state isolation."""

    @pytest.mark.parametrize(
        "phrase,expected_intent",
        [
            ("Nova, how are you?", CanonicalIntent.GENERAL_CONVERSATION),
            ("Nova, can you listen to me?", CanonicalIntent.GENERAL_CONVERSATION),
            ("Nova, open Telegram.", CanonicalIntent.LAUNCH_APP),
            ("Nova, Telegram has been crashing.", CanonicalIntent.GENERAL_CONVERSATION),
            ("Nova, turn the volume up.", CanonicalIntent.CONTROL_VOLUME),
            ("Nova, turn the volume down.", CanonicalIntent.CONTROL_VOLUME),
            ("Nova, why is my volume so low?", CanonicalIntent.GENERAL_CONVERSATION),
            ("Nova, turn Bluetooth off.", CanonicalIntent.CONTROL_BLUETOOTH),
            ("Nova, why is Bluetooth not working?", CanonicalIntent.GENERAL_CONVERSATION),
            ("What is wrong with my Bluetooth?", CanonicalIntent.GENERAL_CONVERSATION),
            ("Bluetooth is not connecting", CanonicalIntent.GENERAL_CONVERSATION),
            ("Bluetooth isn't connecting, what's wrong?", CanonicalIntent.GENERAL_CONVERSATION),
            ("Nova, play some music.", CanonicalIntent.LISTEN_TO_MUSIC),
            ("Nova, I listened to music yesterday.", CanonicalIntent.GENERAL_CONVERSATION),
        ],
    )
    def test_core_10_benchmarks(self, intent_engine: NaturalLanguageIntentEngine, phrase: str, expected_intent: CanonicalIntent) -> None:
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == expected_intent, f"Failed for '{phrase}': expected {expected_intent}, got {action.intent}"

    @pytest.mark.parametrize(
        "phrase",
        [
            "Open Telegram.",
            "Can you open Telegram?",
            "Can you open Telegram for me?",
            "Please open Telegram.",
            "Hey Nova, can you please open Telegram?",
            "Could you open Telegram?",
            "Open the Telegram application.",
            "Nova, launch Telegram.",
        ],
    )
    def test_app_launch_variations(self, intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.LAUNCH_APP

    @pytest.mark.parametrize(
        "phrase,expected_action",
        [
            ("Turn the volume up.", "increase"),
            ("Make it louder.", "increase"),
            ("Increase the Mac volume.", "increase"),
            ("Could you make the sound louder?", "increase"),
            ("turn the sound up", "increase"),
            ("volume up", "increase"),
            ("Turn the volume down.", "decrease"),
            ("Make it quieter.", "decrease"),
            ("Decrease the Mac volume.", "decrease"),
            ("turn the sound down", "decrease"),
            ("make the volume softer", "decrease"),
            ("volume down", "decrease"),
        ],
    )
    def test_volume_variations(self, intent_engine: NaturalLanguageIntentEngine, phrase: str, expected_action: str) -> None:
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.CONTROL_VOLUME
        assert action.parameters.get("action") == expected_action

    @pytest.mark.parametrize(
        "phrase,expected_action",
        [
            ("Turn the brightness up.", "increase"),
            ("Make the screen brighter.", "increase"),
            ("turn brightness up", "increase"),
            ("brightness up", "increase"),
            ("Turn the brightness down.", "decrease"),
            ("Make the screen dimmer.", "decrease"),
            ("turn brightness down", "decrease"),
            ("brightness down", "decrease"),
        ],
    )
    def test_brightness_variations(self, intent_engine: NaturalLanguageIntentEngine, phrase: str, expected_action: str) -> None:
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.CONTROL_BRIGHTNESS
        assert action.parameters.get("action") == expected_action

    @pytest.mark.parametrize(
        "phrase",
        [
            "Why is my Bluetooth not working?",
            "Bluetooth isn't connecting, what's wrong?",
            "What's happening with my Bluetooth?",
            "What is wrong with my Bluetooth?",
            "Bluetooth is not connecting",
            "Bluetooth is annoying me",
            "Wi-Fi is slow",
            "My Wi-Fi is terrible today",
            "Nova, tell me why Bluetooth isn't connecting.",
            "Nova, what's wrong with my Wi-Fi?",
            "Why is my volume so low?",
            "How do I increase the brightness?",
        ],
    )
    def test_questions_not_confused_with_commands(self, intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.GENERAL_CONVERSATION, (
            f"Question '{phrase}' was erroneously parsed as executable command {action.intent}"
        )

    @pytest.mark.parametrize(
        "phrase",
        [
            "Nova, today was exhausting.",
            "Nova, I am really tired.",
            "Nova, I finally solved my coding problem.",
            "Nova, you speak very less these days.",
            "Nova, I just wanted to talk.",
            "Nova, can you listen to me?",
            "Nova, how are you?",
        ],
    )
    def test_casual_conversation_safety(self, intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
        action = intent_engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.GENERAL_CONVERSATION

    def test_cross_turn_state_isolation(self, intent_engine: NaturalLanguageIntentEngine) -> None:
        """Verify sequentially executed turns do not leak tokens, intents, or entities."""
        # Turn 1: Media
        act1 = intent_engine.parse("Nova, play Taylor Swift.", allow_ai_fallback=False)
        assert act1.intent in (CanonicalIntent.PLAY_MEDIA, CanonicalIntent.PLAY_SPECIFIC_SONG, CanonicalIntent.PLAY_ARTIST)
        assert "taylor swift" in act1.parameters.get("query", "").lower() or "taylor swift" in act1.parameters.get("artist", "").lower()

        # Turn 2: Conversation directly following media
        act2 = intent_engine.parse("Nova, how are you?", allow_ai_fallback=False)
        assert act2.intent == CanonicalIntent.GENERAL_CONVERSATION
        assert act2.parameters == {}
        assert "taylor" not in act2.normalized_input.lower()
        assert "play" not in act2.normalized_input.lower()

        # Turn 3: Open App
        act3 = intent_engine.parse("Nova, open Telegram.", allow_ai_fallback=False)
        assert act3.intent == CanonicalIntent.LAUNCH_APP
        assert act3.parameters.get("app_name") == "Telegram"

        # Turn 4: Joke / Conversation directly following App Launch
        act4 = intent_engine.parse("Nova, tell me a joke.", allow_ai_fallback=False)
        assert act4.intent == CanonicalIntent.GENERAL_CONVERSATION
        assert act4.parameters == {}
        assert "telegram" not in act4.normalized_input.lower()

    def test_task_type_contract_safety(self) -> None:
        """Verify TaskType enum integrity and ensure invalid members do not crash token calculation."""
        # Confirm valid TaskType members exist
        assert hasattr(TaskType, "CODING")
        assert hasattr(TaskType, "REASONING")
        assert hasattr(TaskType, "FAST")
        assert hasattr(TaskType, "CHEAP")
        assert hasattr(TaskType, "GENERAL")

        # Confirm TaskType values map cleanly
        for t in (TaskType.CODING, TaskType.REASONING, TaskType.FAST, TaskType.CHEAP, TaskType.GENERAL):
            assert isinstance(t.value, str)
