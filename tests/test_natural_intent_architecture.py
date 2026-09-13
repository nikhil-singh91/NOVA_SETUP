"""Test suite for Natural Language Intent Understanding Architecture.

Verifies that conversational noise, wake words, filler words, polite prefixes,
and phrasing differences map to canonical intents with clean parameters,
without breaking meaningful entity tokens.
"""

from __future__ import annotations

import pytest
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent


@pytest.fixture
def intent_engine() -> NaturalLanguageIntentEngine:
    return NaturalLanguageIntentEngine()


# =============================================================================
# PAIR 1: SCREEN RECORDING
# =============================================================================
@pytest.mark.parametrize(
    "phrase",
    [
        "start screenrecording",
        "start screen recording",
        "Now start screen recording",
        "NOVA start screen recording",
        "Please start recording my screen",
        "Begin recording my screen",
        "I want to record my screen",
        "record my screen",
        "record the screen",
        "start recording the screen",
    ],
)
def test_screen_recording_start_variations(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.START_SCREEN_RECORDING


@pytest.mark.parametrize(
    "phrase",
    [
        "stop recording",
        "stop screen recording",
        "stop screenrecording",
        "Now stop the screen recording",
        "NOVA stop recording",
        "Stop recording my screen",
        "end screen recording",
        "finish recording my screen",
    ],
)
def test_screen_recording_stop_variations(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.STOP_SCREEN_RECORDING


# =============================================================================
# PAIR 2: BROWSER SEARCH
# =============================================================================
@pytest.mark.parametrize(
    "phrase",
    [
        "Search for most important books",
        "Now search for most important books",
        "NOVA search for most important books",
        "Browse the internet and search for most important books",
        "Search the web for most important books",
        "Look up most important books online",
        "Can you search for most important books?",
        "Please search for most important books",
    ],
)
def test_browser_search_variations(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.SEARCH_WEB
    assert action.parameters.get("query") == "most important books"


# =============================================================================
# PAIR 3: APPLICATION CLOSE & LAUNCH
# =============================================================================
@pytest.mark.parametrize(
    "phrase",
    [
        "Close Sublime Text",
        "Close Sublime Text app",
        "NOVA, close Sublime Text",
        "Now close Sublime Text",
        "Please close Sublime Text",
        "Can you close Sublime Text for me?",
        "Quit Sublime Text",
        "Exit Sublime Text",
    ],
)
def test_app_close_variations(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.CLOSE_APP
    assert action.parameters.get("app_name") == "Sublime Text"


@pytest.mark.parametrize(
    "phrase",
    [
        "Open VS Code",
        "NOVA, open VS Code",
        "Please launch VS Code",
        "Start VS Code",
        "Can you open VS Code for me?",
    ],
)
def test_app_launch_variations(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.LAUNCH_APP
    assert action.parameters.get("app_name") == "Visual Studio Code"


# =============================================================================
# PAIR 4: SCREENSHOT
# =============================================================================
@pytest.mark.parametrize(
    "phrase",
    [
        "take screenshot",
        "Take a screenshot",
        "Now take a screenshot",
        "NOVA, take a screenshot",
        "Can you capture my screen?",
        "Please capture the screen",
        "Now, can you please capture my screen?",
        "capture my screen",
        "screenshot this",
    ],
)
def test_screenshot_variations(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.SCREEN_CAPTURE


# =============================================================================
# PAIR 5: FILES & FOLDERS
# =============================================================================
@pytest.mark.parametrize(
    "phrase",
    [
        "Open my DSA folder",
        "NOVA, open my DSA folder",
        "Can you find my DSA folder?",
        "NOVA, can you please open my DSA folder for me?",
    ],
)
def test_folder_open_variations(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent in (CanonicalIntent.OPEN_FOLDER, CanonicalIntent.FIND_ITEM)
    target = action.parameters.get("target_name") or action.parameters.get("query")
    assert target.lower() == "dsa"


# =============================================================================
# ENTITY PROTECTION
# =============================================================================
def test_protect_entity_in_search_query(intent_engine: NaturalLanguageIntentEngine) -> None:
    action = intent_engine.parse("Search for Now You See Me", allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.SEARCH_WEB
    assert "now you see me" in action.parameters.get("query", "").lower()


def test_protect_trailing_noun_in_folder_name(intent_engine: NaturalLanguageIntentEngine) -> None:
    action = intent_engine.parse("Create a folder named Please", allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.CREATE_DESKTOP_FOLDER
    assert action.parameters.get("folder_name") == "Please"


def test_tab_actions_with_conversational_prefixes(intent_engine: NaturalLanguageIntentEngine) -> None:
    act1 = intent_engine.parse("NOVA, open another tab", allow_ai_fallback=False)
    assert act1.intent == CanonicalIntent.OPEN_NEW_TAB

    act2 = intent_engine.parse("Please switch to the previous tab", allow_ai_fallback=False)
    assert act2.intent == CanonicalIntent.PREVIOUS_TAB

    act3 = intent_engine.parse("Go back to the last tab", allow_ai_fallback=False)
    assert act3.intent == CanonicalIntent.PREVIOUS_TAB
