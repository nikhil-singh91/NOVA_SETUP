"""Global Natural Language Normalization and Robust Intent Matching Test Suite.

Verifies system-wide resilience against conversational prefixes ('Now, ', 'Okay NOVA, '),
articles ('the', 'a', 'an'), filler words, commas, punctuation, and multi-action commands.
"""

from __future__ import annotations

import pytest
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent
from intent.normalizer import TextNormalizer


@pytest.fixture
def engine() -> NaturalLanguageIntentEngine:
    return NaturalLanguageIntentEngine()


# =============================================================================
# 1. SCREENSHOT INTENT VARIATIONS
# =============================================================================
@pytest.mark.parametrize(
    "phrase",
    [
        "Capture screenshot",
        "Capture the screenshot",
        "Take a screenshot",
        "NOVA please take the screenshot",
        "Now, capture a screenshot",
        "Now... capture screenshot!",
        "Can you please capture the screenshot for me",
        "Okay NOVA, capture the screenshot please",
        "Take the screenshot",
        "Save the screen",
        "Snap the screenshot",
    ],
)
def test_screenshot_global_variations(engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.SCREEN_CAPTURE, f"Failed for '{phrase}': got {action.intent}"


# =============================================================================
# 2. MULTI-ACTION WEBSITE + SEARCH VARIATIONS
# =============================================================================
@pytest.mark.parametrize(
    "phrase,expected_site,expected_query",
    [
        ("Go to Flipkart website and search for mobile phones", "flipkart", "mobile phones"),
        ("Now, go to Flipkart website and search for mobile phones", "flipkart", "mobile phones"),
        ("NOVA please go to Flipkart and search for mobile phones", "flipkart", "mobile phones"),
        ("Can you open Flipkart and search for mobile phones?", "flipkart", "mobile phones"),
        ("Now open Google and search DSA roadmap", "google", "dsa roadmap"),
        ("Please open Amazon and search for headphones", "amazon", "headphones"),
        ("Okay NOVA, go to YouTube and play Kesariya", "youtube", "kesariya"),
    ],
)
def test_multi_action_search_and_media(
    engine: NaturalLanguageIntentEngine, phrase: str, expected_site: str, expected_query: str
) -> None:
    action = engine.parse(phrase, allow_ai_fallback=False)
    if expected_site == "youtube" and "play" in phrase.lower():
        assert action.intent in (CanonicalIntent.PLAY_MEDIA, CanonicalIntent.PLAY_SPECIFIC_SONG)
        assert action.parameters.get("query", "").lower() == expected_query.lower()
    else:
        assert action.intent == CanonicalIntent.SEARCH_WEBSITE
        assert action.parameters.get("site", "").lower() == expected_site.lower()
        assert action.parameters.get("query", "").lower() == expected_query.lower()


# =============================================================================
# 3. APP LAUNCHING VARIATIONS
# =============================================================================
@pytest.mark.parametrize(
    "phrase,expected_app",
    [
        ("Open Telegram app", "Telegram"),
        ("Now open Telegram app", "Telegram"),
        ("NOVA please open the Telegram application", "Telegram"),
        ("Can you launch Telegram for me?", "Telegram"),
        ("Now open the VS Code app", "Visual Studio Code"),
        ("Please launch Spotify for me", "Spotify"),
    ],
)
def test_app_launch_global_variations(
    engine: NaturalLanguageIntentEngine, phrase: str, expected_app: str
) -> None:
    action = engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.LAUNCH_APP
    assert action.parameters.get("app_name") == expected_app


# =============================================================================
# 4. SCREEN RECORDING VARIATIONS
# =============================================================================
@pytest.mark.parametrize(
    "phrase,expected_intent",
    [
        ("Start screen recording", CanonicalIntent.START_SCREEN_RECORDING),
        ("Start the screen recording", CanonicalIntent.START_SCREEN_RECORDING),
        ("Now start recording my screen", CanonicalIntent.START_SCREEN_RECORDING),
        ("NOVA, please begin the screen recording", CanonicalIntent.START_SCREEN_RECORDING),
        ("Stop screen recording", CanonicalIntent.STOP_SCREEN_RECORDING),
        ("Stop the screen recording", CanonicalIntent.STOP_SCREEN_RECORDING),
        ("Now, stop recording the screen", CanonicalIntent.STOP_SCREEN_RECORDING),
        ("NOVA please end the screen recording", CanonicalIntent.STOP_SCREEN_RECORDING),
    ],
)
def test_screen_recording_global_variations(
    engine: NaturalLanguageIntentEngine, phrase: str, expected_intent: CanonicalIntent
) -> None:
    action = engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == expected_intent


# =============================================================================
# 5. BROWSER TAB, SCROLLING, AND NAVIGATION VARIATIONS
# =============================================================================
@pytest.mark.parametrize(
    "phrase,expected_intent",
    [
        ("Next tab", CanonicalIntent.NEXT_TAB),
        ("NOVA go to the next tab", CanonicalIntent.NEXT_TAB),
        ("Please switch to the next tab", CanonicalIntent.NEXT_TAB),
        ("Now move to the next tab", CanonicalIntent.NEXT_TAB),
        ("Switch to the previous tab", CanonicalIntent.PREVIOUS_TAB),
        ("Now go back to the last tab", CanonicalIntent.PREVIOUS_TAB),
        ("Close the tab", CanonicalIntent.CLOSE_CURRENT_TAB),
        ("Now close the current tab", CanonicalIntent.CLOSE_CURRENT_TAB),
        ("Open a new tab", CanonicalIntent.OPEN_NEW_TAB),
        ("Now open the new tab", CanonicalIntent.OPEN_NEW_TAB),
        ("Scroll down", CanonicalIntent.SCROLL_DOWN),
        ("Now scroll the page down", CanonicalIntent.SCROLL_DOWN),
        ("Scroll the page up", CanonicalIntent.SCROLL_UP),
    ],
)
def test_browser_action_global_variations(
    engine: NaturalLanguageIntentEngine, phrase: str, expected_intent: CanonicalIntent
) -> None:
    action = engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == expected_intent


# =============================================================================
# 6. FILE AND FOLDER OPERATIONS WITH SEMANTIC PRESERVATION
# =============================================================================
@pytest.mark.parametrize(
    "phrase,expected_folder",
    [
        ("Create a folder called DSA", "DSA"),
        ("Now create a folder called DSA on Desktop", "DSA"),
        ("Make a folder named Test on Desktop", "Test"),
        ("Open the DSA folder", "DSA"),
    ],
)
def test_folder_operations_semantic_preservation(
    engine: NaturalLanguageIntentEngine, phrase: str, expected_folder: str
) -> None:
    action = engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent in (CanonicalIntent.CREATE_DESKTOP_FOLDER, CanonicalIntent.OPEN_FOLDER)
    folder_param = action.parameters.get("folder_name") or action.parameters.get("target_name")
    assert folder_param.lower() == expected_folder.lower()
