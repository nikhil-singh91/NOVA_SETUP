"""Comprehensive test suite for NOVA Browser Actions V2: Web Understanding & Multi-Step Planning."""

from __future__ import annotations

import json
import threading
import time
import pytest

from core.event_bus import EventBus, NovaEvent
from core.registry import registry
from browser.context import BrowserContextManager
from browser.engine import BaseBrowserEngine
from browser.extractor import PageContentExtractor
from browser.manager import BrowserManager
from browser.models import (
    ActionType,
    BrowserActionCancelled,
    BrowserActionPlan,
    BrowserContext,
    BrowserResult,
    BrowserTaskCancelled,
    BrowserTaskPlan,
    PageContent,
    Platform,
    SearchResultItem,
)
from browser.parser import BrowserIntentParser
from browser.planner import BrowserTaskPlanner
from browser.router import BrowserActionRouter
from browser.safety import BrowserSafetyPolicy
from browser.sessions import BrowserSessionManager
from browser.sites import AmazonSkill, GenericSiteSkill, GitHubSkill, GoogleSkill, YouTubeSkill


class MockBrowserEngineV2(BaseBrowserEngine):
    """Mock engine simulating DOM extraction, navigation, and multi-tab automation."""

    def __init__(self) -> None:
        self.opened_urls: list[str] = []
        self.closed_tabs_count = 0
        self.history_actions: list[str] = []
        self.scroll_actions: list[str] = []
        self.current_title = "Mock Page Title"
        self.current_url = "https://example.com/article"
        self._is_initialized = False

    @property
    def browser_name(self) -> str:
        return "MockBrowserV2"

    def initialize(self) -> None:
        self._is_initialized = True

    def open_url(self, url: str, new_tab: bool = False) -> bool:
        self.opened_urls.append(url)
        self.current_url = url
        return True

    def click(self, selector: str) -> bool:
        return True

    def type_text(self, selector: str, text: str) -> bool:
        return True

    def wait_for(self, selector: str, timeout_seconds: float = 5.0) -> bool:
        return True

    def execute_script(self, script: str):
        if "maxChars" in script and "headings" in script:
            return json.dumps({
                "url": self.current_url,
                "title": self.current_title,
                "text": "This is meaningful readable content extracted from the web article.",
                "headings": ["Introduction", "Architecture", "Conclusion"],
                "links": [{"title": "Official Doc", "url": "https://example.com/docs"}]
            })
        if "googleCards" in script or "limit" in script:
            return json.dumps([
                {"title": "Python FastAPI Guide", "url": "https://fastapi.tiangolo.com", "snippet": "FastAPI is modern web framework"},
                {"title": "Django Documentation", "url": "https://djangoproject.com", "snippet": "The web framework for perfectionists"},
                {"title": "Flask Web Development", "url": "https://flask.palletsprojects.com", "snippet": "A lightweight WSGI web framework"}
            ])
        if "repo-description" in script:
            return json.dumps({
                "description": "An open source agentic AI assistant framework.",
                "stars": "12.4k",
                "readme_snippet": "NOVA AI Assistant - Installation & Usage Guide."
            })
        if "data-component-type=\"s-search-result\"" in script:
            return json.dumps([
                {"title": "Sony WH-1000XM4 Headphones", "price": "₹19,990", "rating": "4.6 out of 5", "url": "https://amazon.in/dp/B0863TXGM3"},
                {"title": "Bose QuietComfort 45", "price": "₹21,990", "rating": "4.5 out of 5", "url": "https://amazon.in/dp/B098FKXT8L"}
            ])
        return "mock_ok"
    def extract_search_results(self, limit: int = 5) -> list[dict[str, str]]:
        return [
            {"title": "Python FastAPI Guide", "url": "https://fastapi.tiangolo.com", "snippet": "FastAPI is modern web framework"},
            {"title": "Django Documentation", "url": "https://djangoproject.com", "snippet": "The web framework for perfectionists"},
            {"title": "Flask Web Development", "url": "https://flask.palletsprojects.com", "snippet": "A lightweight WSGI web framework"}
        ][:limit]

    def extract_page_content(self) -> PageContent:
        return PageContent(
            url=self.current_url,
            title=self.current_title,
            text="This is meaningful readable content extracted from the web article.",
            headings=["Introduction", "Architecture", "Conclusion"],
            links=[{"title": "Official Doc", "url": "https://example.com/docs"}]
        )

    def get_page_info(self) -> dict[str, str]:
        return {"title": self.current_title, "url": self.current_url}

    def close_tab(self) -> bool:
        self.closed_tabs_count += 1
        return True

    def navigate_back(self) -> bool:
        self.history_actions.append("back")
        return True

    def navigate_forward(self) -> bool:
        self.history_actions.append("forward")
        return True

    def scroll_page(self, direction: str = "down", amount: int = 500) -> bool:
        self.scroll_actions.append(f"scroll_{direction}_{amount}")
        return True

    def refresh_browser_state(self) -> dict[str, Any]:
        return {"active_tab": 1, "total_tabs": 2, "title": self.current_title, "url": self.current_url}

    def get_active_tab_index(self) -> int:
        return 1

    def set_active_tab_index(self, index: int) -> bool:
        return True

    def get_tab_count(self) -> int:
        return 2

    def list_tabs(self) -> list[dict[str, Any]]:
        return [{"index": 1, "title": self.current_title, "url": self.current_url}]

    def next_tab(self) -> tuple[bool, int, str]:
        return True, 2, "Tab 2"

    def previous_tab(self) -> tuple[bool, int, str]:
        return True, 1, "Tab 1"

    def switch_to_tab_by_title_or_url(self, query: str) -> tuple[bool, int, str]:
        return True, 1, self.current_title

    def scroll_to_top(self) -> bool:
        self.scroll_actions.append("scroll_top")
        return True

    def scroll_to_bottom(self) -> bool:
        self.scroll_actions.append("scroll_bottom")
        return True

    def extract_page_content(self) -> PageContent:
        extractor = PageContentExtractor()
        return extractor.extract_page(self)

    def extract_search_results(self, limit: int = 5) -> list[dict[str, str]]:
        return [
            {"title": "Python FastAPI Guide", "url": "https://fastapi.tiangolo.com", "snippet": "FastAPI is modern web framework"},
            {"title": "Django Documentation", "url": "https://djangoproject.com", "snippet": "The web framework for perfectionists"},
            {"title": "Flask Web Development", "url": "https://flask.palletsprojects.com", "snippet": "A lightweight WSGI web framework"}
        ][:limit]

    def shutdown(self) -> None:
        self._is_initialized = False


# ==============================================================================
# TEST 1: Webpage Content Extraction & Sanitization
# ==============================================================================

def test_page_content_extraction() -> None:
    engine = MockBrowserEngineV2()
    extractor = PageContentExtractor(max_chars=500, max_links=5)
    page = extractor.extract_page(engine)

    assert isinstance(page, PageContent)
    assert not page.is_empty
    assert page.title == "Mock Page Title"
    assert "meaningful readable content" in page.text
    assert "Introduction" in page.headings
    assert len(page.links) == 1
    assert page.links[0]["url"] == "https://example.com/docs"


# ==============================================================================
# TEST 2: Multi-Step Browser Task Planning
# ==============================================================================

def test_browser_task_planning() -> None:
    planner = BrowserTaskPlanner(max_steps=6)

    # 1. Research plan
    plan_res = planner.generate_plan(
        goal="Research Python frameworks",
        action_type=ActionType.RESEARCH_TOPIC,
        query="Python backend frameworks",
    )
    assert isinstance(plan_res, BrowserTaskPlan)
    assert len(plan_res.steps) == 5
    assert plan_res.steps[0].action == "search_web"
    assert plan_res.steps[4].action == "synthesize_findings"
    assert plan_res.max_steps == 6

    # 2. Product comparison plan
    plan_comp = planner.generate_plan(
        goal="Compare laptops under 60000",
        action_type=ActionType.COMPARE_PRODUCTS,
        query="laptops under 60000",
    )
    assert len(plan_comp.steps) == 3
    assert plan_comp.steps[0].action == "open_marketplace"


# ==============================================================================
# TEST 3: Web Research Workflow Execution
# ==============================================================================

def test_web_research_workflow() -> None:
    engine = MockBrowserEngineV2()
    sessions = BrowserSessionManager(engine)
    context_mgr = BrowserContextManager()
    planner = BrowserTaskPlanner()
    stop_event = threading.Event()

    result = planner.execute_research(
        query="best Python backend frameworks",
        engine=engine,
        sessions=sessions,
        context_mgr=context_mgr,
        stop_event=stop_event,
    )

    assert result.success is True
    assert result.action_type == ActionType.RESEARCH_TOPIC
    assert len(engine.opened_urls) >= 2  # Search page + opened candidate pages
    assert "google.com/search" in engine.opened_urls[0]
    assert "researched 'best Python backend frameworks'" in result.spoken_response


# ==============================================================================
# TEST 4: Immediate Cancellation of Research Workflow
# ==============================================================================

def test_research_workflow_cancellation() -> None:
    engine = MockBrowserEngineV2()
    sessions = BrowserSessionManager(engine)
    context_mgr = BrowserContextManager()
    planner = BrowserTaskPlanner()
    stop_event = threading.Event()
    stop_event.set()  # Pre-trigger cancellation

    with pytest.raises((BrowserActionCancelled, BrowserTaskCancelled)):
        planner.execute_research(
            query="test topic",
            engine=engine,
            sessions=sessions,
            context_mgr=context_mgr,
            stop_event=stop_event,
        )


# ==============================================================================
# TEST 5: Tab Management V2 & Isolated Research Tab Closing
# ==============================================================================

def test_isolated_research_tab_closing() -> None:
    engine = MockBrowserEngineV2()
    sessions = BrowserSessionManager(engine)

    # Open 3 research tabs
    sessions.open_research_tab("https://example.com/tab1")
    sessions.open_research_tab("https://example.com/tab2")
    sessions.open_research_tab("https://example.com/tab3")

    assert len(sessions._research_tabs) == 3

    # Close only research tabs
    closed = sessions.close_research_tabs()
    assert closed == 3
    assert len(sessions._research_tabs) == 0
    assert engine.closed_tabs_count == 3


# ==============================================================================
# TEST 6: Browser Context & Ordinal Reference Resolution
# ==============================================================================

def test_browser_context_and_ordinal_resolution() -> None:
    context_mgr = BrowserContextManager()
    results = [
        {"title": "FastAPI Web Framework", "url": "https://fastapi.tiangolo.com", "snippet": "High performance"},
        {"title": "Django Official", "url": "https://djangoproject.com", "snippet": "Batteries included"},
    ]
    context_mgr.set_search_results("Python frameworks", results)

    # Lookup ordinal 2 ("the second one")
    item2 = context_mgr.get_result_by_index(2)
    assert item2 is not None
    assert item2.title == "Django Official"
    assert item2.url == "https://djangoproject.com"

    # Lookup ordinal 1 ("first result")
    item1 = context_mgr.get_result_by_index(1)
    assert item1 is not None
    assert item1.title == "FastAPI Web Framework"


# ==============================================================================
# TEST 7: Amazon & GitHub Skills Execution
# ==============================================================================

def test_amazon_and_github_skills() -> None:
    engine = MockBrowserEngineV2()
    sessions = BrowserSessionManager(engine)

    # 1. Amazon Product Search
    amz_skill = AmazonSkill()
    plan_amz = BrowserActionPlan(
        action_type=ActionType.SEARCH_SITE,
        platform=Platform.AMAZON,
        query="Sony headphones under 5000",
        metadata={"site_key": "amazon"},
    )
    res_amz = amz_skill.execute(plan_amz, engine, sessions)
    assert res_amz.success is True
    assert "Sony" in res_amz.spoken_response

    # 2. GitHub Repo Explanation
    gh_skill = GitHubSkill()
    plan_gh = BrowserActionPlan(
        action_type=ActionType.EXPLAIN_PAGE,
        platform=Platform.GITHUB,
        metadata={"site_key": "github"},
    )
    res_gh = gh_skill.execute(plan_gh, engine, sessions)
    assert res_gh.success is True
    assert "agentic AI assistant" in res_gh.spoken_response


# ==============================================================================
# TEST 8: V2 Intent Parser Capabilities
# ==============================================================================

def test_v2_intent_parsing() -> None:
    parser = BrowserIntentParser()

    # 1. Read & Summarize Page
    p1 = parser.parse("Read this page")
    assert p1 is not None
    assert p1.action_type == ActionType.READ_PAGE

    p2 = parser.parse("Summarize this article")
    assert p2 is not None
    assert p2.action_type == ActionType.SUMMARIZE_PAGE

    # 2. GitHub Repo Understanding
    p3 = parser.parse("What is this GitHub project?")
    assert p3 is not None
    assert p3.action_type == ActionType.EXPLAIN_PAGE
    assert p3.platform == Platform.GITHUB

    # 3. Deep Research
    p4 = parser.parse("Research the best Python backend frameworks")
    assert p4 is not None
    assert p4.action_type == ActionType.RESEARCH_TOPIC
    assert p4.query.lower() == "best python backend frameworks"

    # 4. Ordinal Selection
    p5 = parser.parse("Open the second one")
    assert p5 is not None
    assert p5.action_type == ActionType.OPEN_RESULT
    assert p5.target_index == 2

    # 5. Navigation
    p6 = parser.parse("Go back")
    assert p6 is not None
    assert p6.action_type == ActionType.NAVIGATE_BACK

    p7 = parser.parse("Close all research tabs")
    assert p7 is not None
    assert p7.action_type == ActionType.CLOSE_RESEARCH_TABS


# ==============================================================================
# TEST 9: Full V2 Manager Integration & EventBus Verification
# ==============================================================================

def test_v2_manager_full_integration() -> None:
    if registry.exists("event_bus"):
        bus = registry.get("event_bus")
    else:
        bus = EventBus()
        registry.register("event_bus", bus)

    events: list[str] = []

    def on_event(event_name: str, payload: dict) -> None:
        events.append(event_name)

    bus.subscribe(NovaEvent.BROWSER_TASK_STARTED, on_event)
    bus.subscribe(NovaEvent.BROWSER_TASK_COMPLETED, on_event)

    manager = BrowserManager()
    manager.engine = MockBrowserEngineV2()
    manager.sessions = BrowserSessionManager(manager.engine)
    manager.router = BrowserActionRouter(manager.engine, manager.sessions, manager.context_mgr)
    manager.initialize()

    # Execute "Research Python backend frameworks"
    res = manager.execute_command("Research the best Python backend frameworks")

    assert res is not None
    assert res.success is True
    assert NovaEvent.BROWSER_TASK_STARTED.value in events
    assert NovaEvent.BROWSER_TASK_COMPLETED.value in events

    manager.shutdown()
