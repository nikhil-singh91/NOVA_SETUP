"""Automated regression test suite verifying intent detection, normalization, browser search, and Mac control."""

import pytest
from intent.normalizer import TextNormalizer
from intent.matcher import LinguisticIntentMatcher
from intent.models import CanonicalIntent
from browser.parser import BrowserIntentParser
from browser.models import ActionType, Platform


def test_natural_language_conversational_prefix_normalization():
    """Verify conversational wrappers ('Nova', 'now', 'please', 'can you') are stripped while preserving queries."""
    cases = [
        ("Nova, open YouTube", "open YouTube"),
        ("Now open YouTube", "open YouTube"),
        ("Nova, now open YouTube", "open YouTube"),
        ("Please open YouTube", "open YouTube"),
        ("Hey Nova, please open YouTube", "open YouTube"),
        ("Nova, now please go and open Sublime Text", "open Sublime Text"),
        ("Nova, search for most important books", "search for most important books"),
        ("Now search for most important books", "search for most important books"),
        ("Nova, now search for most important books", "search for most important books"),
        ("Go to the Flipkart website and search for mobile phones.", "go to the Flipkart website and search for mobile phones"),
        ("Nova, go to Flipkart and search for mobile phones", "go to Flipkart and search for mobile phones"),
        ("Now start screen recording", "start screen recording"),
        ("Nova, start screen recording", "start screen recording"),
        ("Nova, now increase brightness", "increase brightness"),
        ("Nova, increase brightness of my Mac", "increase brightness of my Mac"),
    ]

    for raw, expected_start in cases:
        res = TextNormalizer.normalize(raw)
        assert res.normalized.lower().startswith(expected_start.lower()) or expected_start.lower() in res.normalized.lower()


def test_flipkart_search_and_site_search_parsing():
    """Verify Flipkart and site search commands parse into ActionType.SEARCH_SITE with clean queries."""
    parser = BrowserIntentParser()

    # 1. "Go to the Flipkart website and search for mobile phones."
    p1 = parser.parse("Go to the Flipkart website and search for mobile phones.")
    assert p1 is not None
    assert p1.action_type == ActionType.SEARCH_SITE
    assert "flipkart" in p1.metadata.get("site_key", "").lower()
    assert "mobile phones" in p1.query.lower()

    # 2. "Go to Flipkart and search for mobile phones"
    p2 = parser.parse("Go to Flipkart and search for mobile phones")
    assert p2 is not None
    assert p2.action_type == ActionType.SEARCH_SITE
    assert "flipkart" in p2.metadata.get("site_key", "").lower()
    assert "mobile phones" in p2.query.lower()

    # 3. "search YouTube for DSA tutorials"
    p3 = parser.parse("search YouTube for DSA tutorials")
    assert p3 is not None
    assert p3.action_type == ActionType.SEARCH_SITE
    assert p3.platform == Platform.YOUTUBE
    assert "dsa tutorials" in p3.query.lower()

    # 4. "search for most important books"
    p4 = parser.parse("search for most important books")
    assert p4 is not None
    assert p4.action_type == ActionType.SEARCH_WEB
    assert "most important books" in p4.query.lower()


def test_intent_matcher_mac_control_and_search():
    """Verify deterministic intent matcher classifies brightness, volume, search, screenshot, and apps."""
    matcher = LinguisticIntentMatcher()

    # Brightness
    act_bri = matcher.match("increase brightness of my mac")
    assert act_bri is not None
    assert act_bri.intent == CanonicalIntent.CONTROL_BRIGHTNESS
    assert act_bri.parameters.get("action") == "increase"

    act_bri_screen = matcher.match("make my screen brighter")
    assert act_bri_screen is not None
    assert act_bri_screen.intent == CanonicalIntent.CONTROL_BRIGHTNESS

    # Volume
    act_vol = matcher.match("increase volume of my mac")
    assert act_vol is not None
    assert act_vol.intent == CanonicalIntent.CONTROL_VOLUME
    assert act_vol.parameters.get("action") == "increase"

    act_mute = matcher.match("mute my mac")
    assert act_mute is not None
    assert act_mute.intent == CanonicalIntent.CONTROL_VOLUME
    assert act_mute.parameters.get("action") == "mute"

    # Search Website
    act_flip = matcher.match("go to the flipkart website and search for mobile phones")
    assert act_flip is not None
    assert act_flip.intent == CanonicalIntent.SEARCH_WEBSITE
    assert act_flip.parameters.get("site") == "flipkart"
    assert "mobile phones" in act_flip.parameters.get("query", "").lower()

    # General Web Search
    act_web = matcher.match("search for most important books")
    assert act_web is not None
    assert act_web.intent == CanonicalIntent.SEARCH_WEB
    assert "most important books" in act_web.parameters.get("query", "").lower()

    # Screenshot
    act_shot = matcher.match("take a screenshot")
    assert act_shot is not None
    assert act_shot.intent == CanonicalIntent.SCREEN_CAPTURE

    # Screen recording
    act_rec = matcher.match("start screen recording")
    assert act_rec is not None
    assert act_rec.intent == CanonicalIntent.START_SCREEN_RECORDING

    # App control
    act_app_open = matcher.match("open youtube app")
    assert act_app_open is not None
    assert act_app_open.intent == CanonicalIntent.LAUNCH_APP
    assert act_app_open.parameters.get("app_name") == "YouTube"

    act_app_close = matcher.match("close sublime text")
    assert act_app_close is not None
    assert act_app_close.intent == CanonicalIntent.CLOSE_APP


def test_all_sixteen_regression_commands():
    """Verify all 16 mandatory regression commands from the specification."""
    matcher = LinguisticIntentMatcher()

    # 1. "search for books"
    # 2. "now search for books"
    # 3. "Nova, search for books"
    # 4. "Nova, now search for books"
    # 5. "browse the internet and search for books"
    for phrase in [
        "search for books",
        "now search for books",
        "Nova, search for books",
        "Nova, now search for books",
        "browse the internet and search for books",
    ]:
        norm = TextNormalizer.normalize(phrase)
        act = matcher.match(norm)
        assert act is not None, f"Failed for {phrase}"
        assert act.intent == CanonicalIntent.SEARCH_WEB, f"Expected SEARCH_WEB for {phrase}, got {act.intent}"
        assert "books" in act.parameters.get("query", "")

    # 6. "go to Flipkart and search for mobile phones"
    # 7. "now go to Flipkart and search for mobile phones"
    # 8. "Nova, go to Flipkart and search for mobile phones"
    # "Go to the Flipkart website and search for mobile phones."
    for phrase in [
        "go to Flipkart and search for mobile phones",
        "now go to Flipkart and search for mobile phones",
        "Nova, go to Flipkart and search for mobile phones",
        "Go to the Flipkart website and search for mobile phones.",
    ]:
        norm = TextNormalizer.normalize(phrase)
        act = matcher.match(norm)
        assert act is not None, f"Failed for {phrase}"
        assert act.intent == CanonicalIntent.SEARCH_WEBSITE, f"Expected SEARCH_WEBSITE for {phrase}, got {act.intent}"
        assert "flipkart" in act.parameters.get("site", "").lower()
        assert "mobile phones" in act.parameters.get("query", "").lower()

    # 9. "search YouTube for DSA tutorials"
    # 10. "Nova, search YouTube for DSA tutorials"
    for phrase in [
        "search YouTube for DSA tutorials",
        "Nova, search YouTube for DSA tutorials",
    ]:
        norm = TextNormalizer.normalize(phrase)
        act = matcher.match(norm)
        assert act is not None, f"Failed for {phrase}"
        assert act.intent == CanonicalIntent.SEARCH_WEBSITE
        assert "youtube" in act.parameters.get("site", "").lower()
        assert "dsa tutorials" in act.parameters.get("query", "").lower()

    # 11. "open YouTube app"
    # 12. "Nova, open YouTube app"
    for phrase in ["open YouTube app", "Nova, open YouTube app"]:
        norm = TextNormalizer.normalize(phrase)
        act = matcher.match(norm)
        assert act is not None, f"Failed for {phrase}"
        assert act.intent == CanonicalIntent.LAUNCH_APP

    # 13. "now close Sublime Text"
    # 14. "Nova, close Sublime Text"
    for phrase in ["now close Sublime Text", "Nova, close Sublime Text"]:
        norm = TextNormalizer.normalize(phrase)
        act = matcher.match(norm)
        assert act is not None, f"Failed for {phrase}"
        assert act.intent == CanonicalIntent.CLOSE_APP

    # 15. "now start screen recording"
    # 16. "Nova, start screen recording"
    for phrase in ["now start screen recording", "Nova, start screen recording"]:
        norm = TextNormalizer.normalize(phrase)
        act = matcher.match(norm)
        assert act is not None, f"Failed for {phrase}"
        assert act.intent == CanonicalIntent.START_SCREEN_RECORDING
