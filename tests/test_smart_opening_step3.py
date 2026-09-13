"""Step 3 Verification Test Suite: Smart Opening, Browser, and Application Resolution.

Tests the complete intent parsing, entity extraction, app vs website disambiguation,
conversational wrapper stripping, and execution routing across all 12+ user test commands.
"""

from __future__ import annotations

import pytest
from browser.sites.generic import TRUSTED_SITES, GenericSiteSkill
from desktop.apps import AppLauncher
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent


@pytest.fixture
def intent_engine() -> NaturalLanguageIntentEngine:
    return NaturalLanguageIntentEngine()


@pytest.fixture
def site_skill() -> GenericSiteSkill:
    return GenericSiteSkill()


# ==============================================================================
# 1. 12 SPECIFIC REQUIRED COMMAND INTENT & ENTITY EXTRACTION TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "phrase,expected_intent,expected_target,is_app",
    [
        # 1. NOVA open YouTube
        ("NOVA open YouTube", CanonicalIntent.OPEN_WEBSITE, "youtube", False),
        # 2. Can you take me to YouTube?
        ("Can you take me to YouTube?", CanonicalIntent.OPEN_WEBSITE, "youtube", False),
        # 3. Please open YouTube for me
        ("Please open YouTube for me", CanonicalIntent.OPEN_WEBSITE, "youtube", False),
        # 4. Open YouTube app
        ("Open YouTube app", CanonicalIntent.LAUNCH_APP, "YouTube", True),
        # 5. Open Telegram app
        ("Open Telegram app", CanonicalIntent.LAUNCH_APP, "Telegram", True),
        # 6. Launch Telegram
        ("Launch Telegram", CanonicalIntent.LAUNCH_APP, "Telegram", True),
        # 7. Open VS Code
        ("Open VS Code", CanonicalIntent.LAUNCH_APP, "Visual Studio Code", True),
        # 8. Can you launch Visual Studio Code?
        ("Can you launch Visual Studio Code?", CanonicalIntent.LAUNCH_APP, "Visual Studio Code", True),
        # 9. Go to GitHub
        ("Go to GitHub", CanonicalIntent.OPEN_WEBSITE, "github", False),
        # 10. Take me to the AKTU website
        ("Take me to the AKTU website", CanonicalIntent.OPEN_WEBSITE, "aktu", False),
        # 11. Open Mirai School of Technology website
        ("Open Mirai School of Technology website", CanonicalIntent.OPEN_WEBSITE, "mirai school of technology", False),
        # 12. Conversational filler variations
        ("NOVA can you please open YouTube for me?", CanonicalIntent.OPEN_WEBSITE, "youtube", False),
        ("Can you take me to the AKTU website please?", CanonicalIntent.OPEN_WEBSITE, "aktu", False),
        ("NOVA please open Telegram app for me", CanonicalIntent.LAUNCH_APP, "Telegram", True),
        ("I want to visit YouTube", CanonicalIntent.OPEN_WEBSITE, "youtube", False),
        ("Go on YouTube", CanonicalIntent.OPEN_WEBSITE, "youtube", False),
        ("Open the YouTube website", CanonicalIntent.OPEN_WEBSITE, "youtube", False),
        ("Go to the Flipkart website", CanonicalIntent.OPEN_WEBSITE, "flipkart", False),
        ("Open Chrome", CanonicalIntent.LAUNCH_APP, "Google Chrome", True),
    ],
)
def test_smart_opening_natural_language_matrix(
    intent_engine: NaturalLanguageIntentEngine,
    phrase: str,
    expected_intent: CanonicalIntent,
    expected_target: str,
    is_app: bool,
) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == expected_intent, f"Failed intent for: {phrase} (got {action.intent.value}, expected {expected_intent.value})"

    if is_app:
        app_name = action.parameters.get("app_name")
        assert app_name == expected_target, f"Failed app_name for: {phrase} (got {app_name}, expected {expected_target})"
    else:
        entity = action.parameters.get("entity", "").lower()
        assert expected_target in entity, f"Failed entity for: {phrase} (got {entity}, expected {expected_target})"


# ==============================================================================
# 2. CONVERSATIONAL FILLER STRIPPING & ENTITY PURITY TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "phrase,expected_clean_entity",
    [
        ("NOVA can you please open YouTube for me?", "youtube"),
        ("Please open YouTube for me", "youtube"),
        ("Can you take me to the AKTU website please?", "aktu"),
        ("Take me to the official website of AKTU", "aktu"),
        ("Go to Flipkart website please", "flipkart"),
        ("Show me the official website for OpenAI", "openai"),
        ("Open Mirai School of Technology website for me", "mirai school of technology"),
    ],
)
def test_conversational_filler_removal(
    intent_engine: NaturalLanguageIntentEngine,
    phrase: str,
    expected_clean_entity: str,
) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.OPEN_WEBSITE
    extracted = action.parameters.get("entity", "").lower().strip()
    assert extracted == expected_clean_entity, f"Entity polluted: got '{extracted}', expected '{expected_clean_entity}'"


# ==============================================================================
# 3. WEBSITE DISCOVERY & TRUSTED SITE REGISTRY TESTS
# ==============================================================================

def test_trusted_sites_registry_coverage(site_skill: GenericSiteSkill) -> None:
    assert "youtube" in TRUSTED_SITES
    assert "google" in TRUSTED_SITES
    assert "flipkart" in TRUSTED_SITES
    assert "amazon" in TRUSTED_SITES
    assert "aktu" in TRUSTED_SITES
    assert "github" in TRUSTED_SITES
    assert "leetcode" in TRUSTED_SITES
    assert "chatgpt" in TRUSTED_SITES
    assert "gmail" in TRUSTED_SITES
    assert "notion" in TRUSTED_SITES


def test_discover_official_website(site_skill: GenericSiteSkill) -> None:
    # 1. Known trusted sites
    assert site_skill.discover_official_website("youtube") == "https://www.youtube.com"
    assert site_skill.discover_official_website("aktu") == "https://aktu.ac.in"
    assert site_skill.discover_official_website("AKTU website") == "https://aktu.ac.in"
    assert site_skill.discover_official_website("Flipkart") == "https://www.flipkart.com"
    assert site_skill.discover_official_website("GitHub") == "https://github.com"

    # 2. Direct domains
    assert site_skill.discover_official_website("aktu.ac.in") == "https://aktu.ac.in"
    assert site_skill.discover_official_website("https://example.com") == "https://example.com"


# ==============================================================================
# 4. APPLICATION RESOLVER & ALIAS DISAMBIGUATION TESTS
# ==============================================================================

def test_app_launcher_aliases() -> None:
    assert AppLauncher.resolve_app_name("vs code") == "Visual Studio Code"
    assert AppLauncher.resolve_app_name("vscode") == "Visual Studio Code"
    assert AppLauncher.resolve_app_name("code editor") == "Visual Studio Code"
    assert AppLauncher.resolve_app_name("chrome") == "Google Chrome"
    assert AppLauncher.resolve_app_name("telegram") == "Telegram"
    assert AppLauncher.resolve_app_name("telegram app") == "Telegram"
    assert AppLauncher.resolve_app_name("whatsapp app") == "WhatsApp"
    assert AppLauncher.resolve_app_name("cursor") == "Cursor"
    assert AppLauncher.resolve_app_name("terminal") == "Terminal"
    assert AppLauncher.resolve_app_name("safari") == "Safari"
