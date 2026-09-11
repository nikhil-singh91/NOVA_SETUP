"""Comprehensive regression test matrix for NOVA Natural Language Action Understanding."""

from __future__ import annotations

import pytest
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent, IntentConfidence
from intent.normalizer import TextNormalizer


@pytest.fixture
def intent_engine() -> NaturalLanguageIntentEngine:
    return NaturalLanguageIntentEngine()


# ==============================================================================
# TEST 1: Wake Word & Conversational Wrapper Normalization
# ==============================================================================

def test_normalization_and_wake_word_stripping() -> None:
    norm = TextNormalizer.normalize("Nova, can you please go to the next tab?")
    assert norm.has_wake_word is True
    assert norm.cleaned_lower == "go to the next tab"

    norm2 = TextNormalizer.normalize("Hey NOVA, play song Mere Liye")
    assert norm2.has_wake_word is True
    assert "mere liye" in norm2.cleaned_lower
    assert norm2.normalized == "play song Mere Liye"  # Preserved entity casing


# ==============================================================================
# TEST 2: NEXT_TAB Paraphrase Matrix (All 8 variations)
# ==============================================================================

@pytest.mark.parametrize(
    "phrase",
    [
        "Next tab",
        "Nova next tab",
        "Go to next tab",
        "Go to the next tab",
        "Switch to the next tab",
        "Can you show me the next tab",
        "Hey Nova please move to the next tab",
        "Nova, can you please go to the next tab?",
    ],
)
def test_next_tab_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.NEXT_TAB
    assert action.confidence >= 0.85


# ==============================================================================
# TEST 3: PREVIOUS_TAB Paraphrase Matrix (All 8 variations)
# ==============================================================================

@pytest.mark.parametrize(
    "phrase",
    [
        "Previous tab",
        "Go to previous tab",
        "Go to the previous tab",
        "Switch to previous tab",
        "Take me to the previous tab",
        "Go back to the last tab",
        "Switch back",
        "Nova, take me back to the previous tab",
    ],
)
def test_previous_tab_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.PREVIOUS_TAB
    assert action.confidence >= 0.85


# ==============================================================================
# TEST 4: OPEN_NEW_TAB Paraphrase Matrix (All 8 variations)
# ==============================================================================

@pytest.mark.parametrize(
    "phrase",
    [
        "Open new tab",
        "Open a new tab",
        "Create new tab",
        "Make a new tab",
        "Open another tab",
        "New tab please",
        "Can you open a new tab",
        "Hey Nova, open another tab",
    ],
)
def test_open_new_tab_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.OPEN_NEW_TAB
    assert action.confidence >= 0.85


# ==============================================================================
# TEST 5: READ_CURRENT_PAGE Paraphrase Matrix (All 9 variations)
# ==============================================================================

@pytest.mark.parametrize(
    "phrase",
    [
        "Read this page",
        "Read the current page",
        "What is written on this page",
        "What is written on my current page",
        "What does this page say",
        "Tell me what is on this page",
        "Can you read this website",
        "Nova, what is written on my current page?",
    ],
)
def test_read_current_page_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.READ_CURRENT_PAGE
    assert action.confidence >= 0.85


# ==============================================================================
# TEST 6: SCROLL_DOWN & SCROLL_UP Paraphrase Matrix
# ==============================================================================

@pytest.mark.parametrize(
    "phrase",
    [
        "Scroll down",
        "Scroll the page down",
        "Go down",
        "Move down",
        "Show more",
        "Take me lower",
        "Scroll a little down",
    ],
)
def test_scroll_down_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.SCROLL_DOWN
    assert action.confidence >= 0.85


@pytest.mark.parametrize(
    "phrase",
    [
        "Scroll up",
        "Go up",
        "Move up",
        "Show previous section",
        "Scroll a little up",
    ],
)
def test_scroll_up_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.SCROLL_UP
    assert action.confidence >= 0.85


# ==============================================================================
# TEST 7: OPEN_WEBSITE Entity Discovery Matrix
# ==============================================================================

@pytest.mark.parametrize(
    "phrase,expected_entity",
    [
        ("Open Mirai School of Technology website", "mirai school of technology"),
        ("Take me to Mirai School of Technology", "mirai school of technology"),
        ("Go to the AKTU website", "aktu"),
        ("Find the official OpenAI website", "openai"),
        ("Can you open the GitHub website?", "github"),
        ("Show me the website for Apple", "apple"),
    ],
)
def test_open_website_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str, expected_entity: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.OPEN_WEBSITE
    assert expected_entity in action.parameters.get("entity", "").lower()


# ==============================================================================
# TEST 8: PLAY_MEDIA & Query Preservation Matrix
# ==============================================================================

@pytest.mark.parametrize(
    "phrase,expected_query",
    [
        ("Play song Mere Liye", "mere liye"),
        ("Play Kesariya on YouTube", "kesariya"),
        ("Nova, play Believer", "believer"),
        ("I want to watch Motu Patlu", "motu patlu"),
        ("Play Kesariya", "kesariya"),
    ],
)
def test_play_media_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str, expected_query: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.PLAY_MEDIA
    assert action.parameters.get("platform") == "youtube"
    assert expected_query in action.parameters.get("query", "").lower()


# ==============================================================================
# TEST 9: Desktop Application Launching Matrix
# ==============================================================================

@pytest.mark.parametrize(
    "phrase,expected_app",
    [
        ("Open VS Code", "Visual Studio Code"),
        ("Launch Visual Studio Code", "Visual Studio Code"),
        ("Start code editor", "Visual Studio Code"),
        ("Nova, open Spotify", "Spotify"),
    ],
)
def test_app_launch_paraphrases(intent_engine: NaturalLanguageIntentEngine, phrase: str, expected_app: str) -> None:
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.LAUNCH_APP
    assert action.parameters.get("app_name") == expected_app


# ==============================================================================
# TEST 10: Environment Awareness & Computer Agent V1 Matrix
# ==============================================================================

def test_in_site_search_commands(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Test 'In Flipkart search mobile phones' and variants."""
    act1 = intent_engine.parse("In Flipkart search mobile phones")
    assert act1.intent == CanonicalIntent.SEARCH_WEBSITE
    assert act1.parameters.get("site") == "flipkart"
    assert "mobile phones" in act1.parameters.get("query", "")

    act2 = intent_engine.parse("Search mobile phones in Flipkart")
    assert act2.intent == CanonicalIntent.SEARCH_WEBSITE
    assert act2.parameters.get("site") == "flipkart"

    act3 = intent_engine.parse("Search iPhone here")
    assert act3.intent == CanonicalIntent.SEARCH_CURRENT_SITE
    assert "iphone" in act3.parameters.get("query", "").lower()


def test_youtube_shorts_commands(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Test 'Play Shorts' and 'Open YouTube Shorts' mapping to WATCH_SHORTS."""
    act1 = intent_engine.parse("Play Shorts")
    assert act1.intent == CanonicalIntent.WATCH_SHORTS

    act2 = intent_engine.parse("Open YouTube Shorts")
    assert act2.intent == CanonicalIntent.WATCH_SHORTS

    act3 = intent_engine.parse("Show me YouTube Shorts")
    assert act3.intent == CanonicalIntent.WATCH_SHORTS

    act4 = intent_engine.parse("Play funny shorts")
    assert act4.intent == CanonicalIntent.WATCH_SHORTS
    assert act4.parameters.get("query") == "funny"


def test_screen_recording_commands(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Test screen recording intent recognition."""
    act1 = intent_engine.parse("Record screen")
    assert act1.intent == CanonicalIntent.START_SCREEN_RECORDING

    act2 = intent_engine.parse("Start screen recording")
    assert act2.intent == CanonicalIntent.START_SCREEN_RECORDING

    act3 = intent_engine.parse("Stop screen recording")
    assert act3.intent == CanonicalIntent.STOP_SCREEN_RECORDING

    act4 = intent_engine.parse("Stop recording")
    assert act4.intent == CanonicalIntent.STOP_SCREEN_RECORDING


def test_desktop_folder_file_commands(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Test desktop folder creation, opening, and contextual file creation."""
    act1 = intent_engine.parse("Create a folder called Test on Desktop")
    assert act1.intent == CanonicalIntent.CREATE_DESKTOP_FOLDER
    assert act1.parameters.get("folder_name") == "Test"
    assert act1.parameters.get("on_desktop") is True

    act2 = intent_engine.parse("Open DSA folder")
    assert act2.intent == CanonicalIntent.OPEN_FOLDER
    assert act2.parameters.get("target_name") == "DSA"

    act3 = intent_engine.parse("Open the folder I just created")
    assert act3.intent == CanonicalIntent.OPEN_FOLDER
    assert act3.parameters.get("use_context") is True

    act4 = intent_engine.parse("Create main.cpp inside it")
    assert act4.intent == CanonicalIntent.CREATE_DESKTOP_FILE
    assert act4.parameters.get("filename") == "main.cpp"


def test_document_writing_commands(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Test document writing recognition."""
    act1 = intent_engine.parse("Write an application for college leave")
    assert act1.intent == CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT
    assert "college leave" in act1.parameters.get("topic", "").lower() or "leave" in act1.parameters.get("topic", "").lower()

    act2 = intent_engine.parse("Write a leave application")
    assert act2.intent == CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT

    act3 = intent_engine.parse("Open Notepad and write a leave application")
    assert act3.intent == CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT


def test_reminder_intent_disambiguation(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Test reminder disambiguation for 'I want to go to the market at 8 PM'."""
    act = intent_engine.parse("I want to go to the market at 8 PM")
    assert act.intent == CanonicalIntent.REMINDER_REQUEST
    assert act.parameters.get("time_str") == "8 PM"
    assert act.requires_clarification is True
    assert "8 PM" in (act.clarification_prompt or "")


def test_delete_safety_intent(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Test delete intent requires confirmation."""
    act = intent_engine.parse("Delete this")
    assert act.intent == CanonicalIntent.DELETE_ITEM
    assert act.parameters.get("requires_confirmation") is True


def test_screen_visual_awareness_intent(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Test screen awareness intent."""
    act1 = intent_engine.parse("What am I looking at?")
    assert act1.intent == CanonicalIntent.WHAT_AM_I_LOOKING_AT

    act2 = intent_engine.parse("What is on my screen?")
    assert act2.intent == CanonicalIntent.WHAT_AM_I_LOOKING_AT

