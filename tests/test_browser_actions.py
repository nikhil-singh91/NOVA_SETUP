"""Comprehensive test suite for NOVA Browser Actions V1."""

from __future__ import annotations

import time
import pytest

from core.event_bus import EventBus, NovaEvent
from core.registry import registry
from browser.engine import BaseBrowserEngine
from browser.manager import BrowserManager
from browser.models import (
    ActionType,
    BrowserActionPlan,
    BrowserResult,
    Platform,
)
from browser.parser import BrowserIntentParser
from browser.router import BrowserActionRouter
from browser.safety import BrowserSafetyPolicy
from browser.sessions import BrowserSessionManager
from browser.sites import GenericSiteSkill, GoogleSkill, YouTubeSkill


class MockBrowserEngine(BaseBrowserEngine):
    """Mock engine simulating browser automation without launching real windows."""

    def __init__(self) -> None:
        self.opened_urls: list[str] = []
        self.clicked_selectors: list[str] = []
        self.typed_texts: list[tuple[str, str]] = []
        self.scripts_executed: list[str] = []
        self._is_initialized = False

    @property
    def browser_name(self) -> str:
        return "MockBrowser"

    def initialize(self) -> None:
        self._is_initialized = True

    def open_url(self, url: str, new_tab: bool = False) -> bool:
        self.opened_urls.append(url)
        return True

    def click(self, selector: str) -> bool:
        self.clicked_selectors.append(selector)
        return True

    def type_text(self, selector: str, text: str) -> bool:
        self.typed_texts.append((selector, text))
        return True

    def wait_for(self, selector: str, timeout_seconds: float = 5.0) -> bool:
        return True

    def execute_script(self, script: str):
        self.scripts_executed.append(script)
        if "firstVideo" in script or "titles" in script:
            return "Simulated Video Title"
        if "nextBtn" in script or "ArrowDown" in script:
            return "next_btn_clicked"
        return "mock_ok"

    def get_page_info(self) -> dict[str, str]:
        return {"title": "Mock Page", "url": self.opened_urls[-1] if self.opened_urls else ""}

    def close_tab(self) -> bool:
        return True

    def navigate_back(self) -> bool:
        return True

    def navigate_forward(self) -> bool:
        return True

    def scroll_page(self, direction: str = "down", amount: int = 500) -> bool:
        return True

    def refresh_browser_state(self) -> dict[str, Any]:
        return {"active_tab": 1, "total_tabs": 2, "title": "Mock Page", "url": self.opened_urls[-1] if self.opened_urls else "https://example.com"}

    def get_active_tab_index(self) -> int:
        return 1

    def set_active_tab_index(self, index: int) -> bool:
        return True

    def get_tab_count(self) -> int:
        return 2

    def list_tabs(self) -> list[dict[str, Any]]:
        return [{"index": 1, "title": "Mock Page", "url": "https://example.com"}]

    def next_tab(self) -> tuple[bool, int, str]:
        return True, 2, "Tab 2"

    def previous_tab(self) -> tuple[bool, int, str]:
        return True, 1, "Tab 1"

    def switch_to_tab_by_title_or_url(self, query: str) -> tuple[bool, int, str]:
        return True, 1, "Mock Page"

    def scroll_to_top(self) -> bool:
        return True

    def scroll_to_bottom(self) -> bool:
        return True

    def extract_page_content(self):
        from browser.models import PageContent
        return PageContent(url=self.current_url if hasattr(self, 'current_url') else "", title="Mock Title", text="Mock page text")

    def extract_search_results(self, limit: int = 5):
        return []

    def shutdown(self) -> None:
        self._is_initialized = False


# ==============================================================================
# TEST 1: Intent Parsing for Playback & YouTube Media
# ==============================================================================

def test_intent_parsing_youtube_media() -> None:
    parser = BrowserIntentParser()

    # 1. "Play song Mere Liye"
    plan1 = parser.parse("Play song Mere Liye")
    assert plan1 is not None
    assert plan1.action_type == ActionType.PLAY_MEDIA
    assert plan1.platform == Platform.YOUTUBE
    assert plan1.query == "mere liye"

    # 2. "Play Kesariya on YouTube"
    plan2 = parser.parse("Play Kesariya on YouTube")
    assert plan2 is not None
    assert plan2.action_type == ActionType.PLAY_MEDIA
    assert plan2.platform == Platform.YOUTUBE
    assert plan2.query == "kesariya"

    # 3. "I want to watch Motu Patlu"
    plan3 = parser.parse("I want to watch Motu Patlu")
    assert plan3 is not None
    assert plan3.action_type == ActionType.WATCH_VIDEO
    assert plan3.platform == Platform.YOUTUBE
    assert plan3.query == "motu patlu"

    # 4. Hindi/Hinglish "Kesariya gaana chalao"
    plan4 = parser.parse("Kesariya gaana chalao")
    assert plan4 is not None
    assert plan4.action_type == ActionType.PLAY_MEDIA
    assert plan4.platform == Platform.YOUTUBE
    assert plan4.query == "kesariya"


# ==============================================================================
# TEST 2: Intent Parsing for YouTube Shorts & Navigation
# ==============================================================================

def test_intent_parsing_youtube_shorts() -> None:
    parser = BrowserIntentParser()

    # 1. "Show me YouTube Shorts"
    plan1 = parser.parse("Show me YouTube Shorts")
    assert plan1 is not None
    assert plan1.action_type == ActionType.WATCH_SHORTS
    assert plan1.platform == Platform.YOUTUBE

    # 2. "Watch coding Shorts automatically"
    plan2 = parser.parse("Watch coding Shorts automatically")
    assert plan2 is not None
    assert plan2.action_type == ActionType.START_AUTO_SHORTS
    assert plan2.auto_navigation is True
    assert plan2.query == "coding"

    # 3. "Next Short"
    plan3 = parser.parse("Next Short")
    assert plan3 is not None
    assert plan3.action_type == ActionType.NEXT_ITEM

    # 4. "Stop scrolling"
    plan4 = parser.parse("Stop scrolling")
    assert plan4 is not None
    assert plan4.action_type == ActionType.STOP_AUTO_SHORTS


# ==============================================================================
# TEST 3: Intent Parsing for Web & Specific Site Search
# ==============================================================================

def test_intent_parsing_search() -> None:
    parser = BrowserIntentParser()

    # 1. "Search Google for what is artificial intelligence"
    plan1 = parser.parse("Search Google for what is artificial intelligence")
    assert plan1 is not None
    assert plan1.action_type == ActionType.SEARCH_WEB
    assert plan1.platform == Platform.GOOGLE
    assert plan1.query == "what is artificial intelligence"

    # 2. "Search Amazon for MacBook accessories"
    plan2 = parser.parse("Search Amazon for MacBook accessories")
    assert plan2 is not None
    assert plan2.action_type == ActionType.SEARCH_SITE
    assert plan2.platform == Platform.AMAZON
    assert plan2.query == "macbook accessories"

    # 3. "Search Wikipedia for Alan Turing"
    plan3 = parser.parse("Search Wikipedia for Alan Turing")
    assert plan3 is not None
    assert plan3.action_type == ActionType.SEARCH_SITE
    assert plan3.platform == Platform.WIKIPEDIA
    assert plan3.query == "alan turing"


# ==============================================================================
# TEST 4: Intent Parsing for Opening Trusted Sites
# ==============================================================================

def test_intent_parsing_open_sites() -> None:
    parser = BrowserIntentParser()

    # 1. "Open Instagram"
    plan1 = parser.parse("Open Instagram")
    assert plan1 is not None
    assert plan1.action_type == ActionType.OPEN_SITE
    assert plan1.platform == Platform.INSTAGRAM

    # 2. "Open WhatsApp Web"
    plan2 = parser.parse("Open WhatsApp Web")
    assert plan2 is not None
    assert plan2.action_type == ActionType.OPEN_SITE
    assert plan2.platform == Platform.WHATSAPP

    # 3. "Open YouTube"
    plan3 = parser.parse("Open YouTube")
    assert plan3 is not None
    assert plan3.action_type == ActionType.OPEN_SITE
    assert plan3.platform == Platform.YOUTUBE

    # Non-browser query
    plan_none = parser.parse("Write a python function to compute fibonacci")
    assert plan_none is None


# ==============================================================================
# TEST 5: Safety Policy Evaluation & Sensitivity
# ==============================================================================

def test_safety_policy_evaluation() -> None:
    # 1. Public safe search
    safe_plan = BrowserActionPlan(
        action_type=ActionType.SEARCH_WEB,
        query="python tutorials",
        raw_prompt="Search Google for python tutorials",
    )
    evaluated_safe = BrowserSafetyPolicy.evaluate(safe_plan)
    assert not evaluated_safe.is_sensitive
    assert not evaluated_safe.requires_confirmation

    # 2. Sensitive action
    sensitive_plan = BrowserActionPlan(
        action_type=ActionType.OPEN_SITE,
        query="checkout and pay",
        raw_prompt="Buy this MacBook right now and pay with card",
    )
    evaluated_sensitive = BrowserSafetyPolicy.evaluate(sensitive_plan)
    assert evaluated_sensitive.is_sensitive
    assert evaluated_sensitive.requires_confirmation
    assert "consequences" in evaluated_sensitive.confirmation_prompt


# ==============================================================================
# TEST 6: YouTube Skill Execution
# ==============================================================================

def test_youtube_skill_execution() -> None:
    engine = MockBrowserEngine()
    sessions = BrowserSessionManager(engine)
    skill = YouTubeSkill()

    # 1. Play Media
    plan = BrowserActionPlan(
        action_type=ActionType.PLAY_MEDIA,
        platform=Platform.YOUTUBE,
        query="Kesariya",
    )
    res = skill.execute(plan, engine, sessions)

    assert res.success is True
    assert ("Playing Kesariya on YouTube" in res.spoken_response) or ("Kesariya" in res.spoken_response)
    assert len(engine.opened_urls) == 1
    assert "youtube.com/watch" in engine.opened_urls[0] or "youtube.com/results" in engine.opened_urls[0]

    # 2. Shorts Auto Navigation
    plan_shorts = BrowserActionPlan(
        action_type=ActionType.START_AUTO_SHORTS,
        platform=Platform.YOUTUBE,
        auto_navigation=True,
    )
    res_shorts = skill.execute(plan_shorts, engine, sessions)

    assert res_shorts.success is True
    assert "auto-scrolling" in res_shorts.spoken_response
    assert sessions.is_task_running() is True

    # 3. Stop Auto Shorts
    plan_stop = BrowserActionPlan(
        action_type=ActionType.STOP_AUTO_SHORTS,
        platform=Platform.YOUTUBE,
    )
    res_stop = skill.execute(plan_stop, engine, sessions)
    assert res_stop.success is True
    assert sessions.is_task_running() is False


# ==============================================================================
# TEST 7: Google Skill Execution
# ==============================================================================

def test_google_skill_execution() -> None:
    engine = MockBrowserEngine()
    sessions = BrowserSessionManager(engine)
    skill = GoogleSkill()

    plan = BrowserActionPlan(
        action_type=ActionType.SEARCH_WEB,
        platform=Platform.GOOGLE,
        query="what is artificial intelligence",
    )
    res = skill.execute(plan, engine, sessions)

    assert res.success is True
    assert "Google search results for 'what is artificial intelligence'" in res.spoken_response
    assert len(engine.opened_urls) == 1
    assert "google.com/search?q=what+is+artificial+intelligence" in engine.opened_urls[0]


# ==============================================================================
# TEST 8: Generic Site Skill Execution
# ==============================================================================

def test_generic_site_skill_execution() -> None:
    engine = MockBrowserEngine()
    sessions = BrowserSessionManager(engine)
    skill = GenericSiteSkill()

    # 1. Open Instagram
    plan_ig = BrowserActionPlan(
        action_type=ActionType.OPEN_SITE,
        platform=Platform.INSTAGRAM,
        metadata={"site_key": "instagram"},
    )
    res_ig = skill.execute(plan_ig, engine, sessions)
    assert res_ig.success is True
    assert "Opening Instagram" in res_ig.spoken_response
    assert "https://www.instagram.com" in engine.opened_urls

    # 2. Search Amazon
    plan_amz = BrowserActionPlan(
        action_type=ActionType.SEARCH_SITE,
        platform=Platform.AMAZON,
        query="MacBook accessories",
        metadata={"site_key": "amazon"},
    )
    res_amz = skill.execute(plan_amz, engine, sessions)
    assert res_amz.success is True
    assert "Searching Amazon for 'MacBook accessories'" in res_amz.spoken_response
    assert "amazon.com/s?k=MacBook+accessories" in engine.opened_urls[-1]


# ==============================================================================
# TEST 9: BrowserManager Full Flow & EventBus Notifications
# ==============================================================================

def test_browser_manager_full_flow() -> None:
    bus = EventBus()
    registry.register("event_bus", bus)

    events: list[str] = []

    def on_event(event_name: str, payload: dict) -> None:
        events.append(event_name)

    bus.subscribe(NovaEvent.BROWSER_ACTION_STARTED, on_event)
    bus.subscribe(NovaEvent.BROWSER_ACTION_COMPLETED, on_event)

    manager = BrowserManager()
    manager.engine = MockBrowserEngine()
    manager.sessions = BrowserSessionManager(manager.engine)
    manager.router = BrowserActionRouter(manager.engine, manager.sessions)
    manager.initialize()

    # Execute "Play Kesariya"
    res = manager.execute_command("Play Kesariya on YouTube")

    assert res is not None
    assert res.success is True
    assert "playing kesariya on youtube" in res.spoken_response.lower()
    assert NovaEvent.BROWSER_ACTION_STARTED.value in events
    assert NovaEvent.BROWSER_ACTION_COMPLETED.value in events

    manager.shutdown()
