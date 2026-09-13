"""Tests for NOVA's Contextual Follow-Up Architecture.

Validates:
1. RecentInteractionContext retention, freshness, and boundedness.
2. ContextualReferenceResolver natural reference extraction and resolution.
3. Screen state reality overriding stale memory.
4. Intent classification using (transcript + context + screen_state).
5. Target / Action / Payload separation on search commands.
6. Browser engine & GenericSiteSkill handling of open_new_tab and search_current_tab.
7. Capability registry reflection.
8. Natural friendly response orchestration.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from browser.models import ActionType, BrowserActionPlan, BrowserResult
from browser.sites.generic import GenericSiteSkill
from core.context import (
    ContextualReferenceResolver,
    RecentInteractionContext,
)
from core.task_agent.registry import capability_registry
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent, StructuredAction
from personality.response_orchestrator import ResponseOrchestrator


class TestRecentInteractionContext:
    def test_context_boundedness_and_recency(self):
        ctx = RecentInteractionContext(max_turns=3)
        for i in range(5):
            ctx.add_turn(
                user_input=f"Turn {i}",
                intent="test_intent",
                action="test_action",
                action_result="success",
                success=True,
            )
        assert len(ctx.turns) == 3
        assert ctx.turns[-1].user_input == "Turn 4"
        assert ctx.turns[0].user_input == "Turn 2"

    def test_browser_state_recording(self):
        ctx = RecentInteractionContext()
        ctx.update_browser_state(
            browser_name="Google Chrome",
            tab_id=2,
            window_id=1,
            url="chrome://newtab/",
            title="New Tab",
            is_new_tab=True,
        )
        assert ctx.active_browser == "Google Chrome"
        assert ctx.active_tab_id == 2
        assert ctx.last_opened_url == "chrome://newtab/"
        assert ctx.is_current_tab_new is True

    def test_reference_resolution_tab(self):
        ctx = RecentInteractionContext()
        ctx.update_browser_state(
            browser_name="Google Chrome",
            tab_id=3,
            url="chrome://newtab/",
            title="New Tab",
            is_new_tab=True,
        )
        resolver = ContextualReferenceResolver(ctx)

        # Test natural follow-up phrases
        for phrase in ("this new tab", "in this tab", "that tab", "current tab", "the one I just opened"):
            resolved = resolver.resolve(phrase)
            assert resolved is not None, f"Failed to resolve: {phrase}"
            assert resolved.entity_type == "tab"
            assert resolved.app_name == "Google Chrome"
            assert resolved.confidence >= 0.85

    def test_screen_state_overrides_stale_memory(self):
        ctx = RecentInteractionContext()
        # Stale memory thinks Tab 1 (Google) is open
        ctx.update_browser_state(
            browser_name="Google Chrome",
            tab_id=1,
            url="https://google.com",
            title="Google",
        )
        resolver = ContextualReferenceResolver(ctx)

        # But ScreenState / Eyes observes that Safari is frontmost with YouTube
        mock_screen_state = MagicMock()
        mock_screen_state.active_application = "Safari"
        mock_screen_state.active_app = "Safari"
        mock_screen_state.active_window = "YouTube - Watch"
        mock_screen_state.active_window_title = "YouTube - Watch"

        resolved = resolver.resolve("this app", screen_state=mock_screen_state)
        assert resolved is not None
        assert resolved.app_name == "Safari"

        resolved_tab = resolver.resolve("this tab", screen_state=mock_screen_state)
        assert resolved_tab is not None
        assert resolved_tab.app_name == "Safari"
        assert "YouTube" in (resolved_tab.title or "")


class TestContextualIntentClassification:
    def setup_method(self):
        self.engine = NaturalLanguageIntentEngine()
        self.context = RecentInteractionContext()

    def test_turn1_open_chrome_new_tab(self):
        action = self.engine.parse("Nova, open a Chrome new tab")
        assert action.intent == CanonicalIntent.OPEN_NEW_TAB
        assert action.parameters.get("browser", "").lower() == "chrome"

    def test_turn1_open_new_tab_in_chrome(self):
        action = self.engine.parse("open a new tab in Chrome")
        assert action.intent == CanonicalIntent.OPEN_NEW_TAB
        assert action.parameters.get("browser", "").lower() == "chrome"

    def test_turn2_in_this_new_tab_search(self):
        # Setup context after turn 1
        self.context.add_turn(
            user_input="open a Chrome new tab",
            intent="open_new_tab",
            action="open_new_tab",
            action_result="opened new tab",
            success=True,
            target_app="Google Chrome",
            target_browser="Google Chrome",
            current_url="chrome://newtab/",
            current_title="New Tab",
        )
        self.context.update_browser_state(
            browser_name="Google Chrome",
            url="chrome://newtab/",
            title="New Tab",
            is_new_tab=True,
        )

        action = self.engine.parse(
            "In this new tab, search for mobile phones",
            context=self.context,
        )
        assert action.intent == CanonicalIntent.SEARCH_CURRENT_TAB
        assert action.parameters.get("query") == "mobile phones"
        assert action.parameters.get("target") == "current_tab"
        assert action.parameters.get("reference") == "this_tab"

    def test_contextual_chained_actions(self):
        # 1. Search for laptops in active tab
        action1 = self.engine.parse("In this tab search for laptops", context=self.context)
        assert action1.intent == CanonicalIntent.SEARCH_CURRENT_TAB
        assert action1.parameters.get("query") == "laptops"

        # 2. Follow-up "now search for headphones"
        self.context.add_turn(
            user_input="In this tab search for laptops",
            intent="search_current_tab",
            action="search_current_tab",
            action_result="searched laptops",
            success=True,
            target_app="Google Chrome",
            last_search_query="laptops",
        )
        action2 = self.engine.parse("now search for headphones", context=self.context)
        assert action2.intent == CanonicalIntent.SEARCH_CURRENT_TAB
        assert action2.parameters.get("query") == "headphones"

        # 3. "Scroll down"
        action3 = self.engine.parse("Scroll down", context=self.context)
        assert action3.intent == CanonicalIntent.SCROLL_DOWN

        # 4. "Click the second result"
        action4 = self.engine.parse("Click the second result", context=self.context)
        assert action4.intent == CanonicalIntent.CLICK_UI_ELEMENT

        # 5. "Go back"
        action5 = self.engine.parse("Go back", context=self.context)
        assert action5.intent == CanonicalIntent.GO_BACK

    def test_statement_is_not_falsely_converted_to_search(self):
        # A purely conversational observation must not be treated as a command
        action = self.engine.parse("I just opened a new tab", context=self.context)
        assert action.intent != CanonicalIntent.SEARCH_CURRENT_TAB


class TestGenericBrowserExecution:
    def test_generic_skill_open_new_tab(self):
        skill = GenericSiteSkill()
        plan = BrowserActionPlan(
            platform="generic",
            action_type=ActionType.OPEN_NEW_TAB,
            metadata={"browser": "Chrome"},
        )
        mock_engine = MagicMock()
        mock_engine._app_name = "Google Chrome"
        mock_sessions = MagicMock()
        mock_engine.open_new_tab.return_value = (True, 1, "New Tab", "chrome://newtab/")
        res = skill.execute(plan, engine=mock_engine, sessions=mock_sessions)
        assert res.success is True
        assert "Opened a new tab" in res.message or "Opened new tab" in res.message
        assert res.metadata.get("tab_index") == 1

    def test_generic_skill_search_current_tab(self):
        skill = GenericSiteSkill()
        plan = BrowserActionPlan(
            platform="generic",
            action_type=ActionType.SEARCH_CURRENT_TAB,
            query="macbook pro",
            metadata={"query": "macbook pro"},
        )
        mock_engine = MagicMock()
        mock_sessions = MagicMock()
        mock_engine.search_current_tab.return_value = (
            True,
            1,
            "macbook pro - Google Search",
            "https://www.google.com/search?q=macbook+pro",
        )
        res = skill.execute(plan, engine=mock_engine, sessions=mock_sessions)
        assert res.success is True
        assert "Searched for 'macbook pro'" in res.message
        assert "google.com" in (res.url or "")


class TestCapabilityRegistry:
    def test_browser_capabilities_present(self):
        assert capability_registry.has("browser.open_new_tab")
        assert capability_registry.has("browser.search_current_tab")
        assert capability_registry.has("browser.search_web")
        assert capability_registry.has("browser.search_site")


class TestFriendlyResponseOrchestrator:
    def test_search_current_tab_friendly_response(self):
        action = StructuredAction(
            intent=CanonicalIntent.SEARCH_CURRENT_TAB,
            confidence=0.95,
            parameters={"query": "smartphones", "target": "current_tab"},
        )
        res = BrowserResult(
            success=True,
            action_type=ActionType.SEARCH_CURRENT_TAB,
            message="Searched for 'smartphones'",
            metadata={"query": "smartphones"},
        )
        orch = ResponseOrchestrator.format_action_response(
            action, res, "in this tab search for smartphones"
        )
        assert orch.success is True
        assert "searched for smartphones in that tab" in orch.spoken_text.lower() or "tab mein search kar diya" in orch.spoken_text.lower()
        # Ensure it does NOT claim it cannot browse
        assert "cannot browse" not in orch.spoken_text.lower()
        assert "can't browse" not in orch.spoken_text.lower()


class TestManualInterventionAndStaleContext:
    def test_manual_tab_switch_prefers_active_observation(self):
        ctx = RecentInteractionContext()
        # NOVA opened Tab A
        ctx.update_browser_state(
            browser_name="Google Chrome",
            tab_id=1,
            url="chrome://newtab/",
            title="New Tab",
            is_new_tab=True,
        )
        resolver = ContextualReferenceResolver(ctx)

        # User manually switched to Tab B (observed by NOVA Eyes / OS Observer)
        mock_eyes = MagicMock()
        mock_eyes.active_application = "Google Chrome"
        mock_eyes.active_window = "Python Documentation - Tab 2"

        resolved = resolver.resolve("in this tab", screen_state=mock_eyes)
        assert resolved is not None
        assert resolved.entity_type == "tab"
        assert resolved.app_name == "Google Chrome"
        # The current reality must reflect Tab B
        assert resolved.title == "Python Documentation - Tab 2"

    def test_context_expiration(self):
        ctx = RecentInteractionContext()
        ctx.update_browser_state(
            browser_name="Google Chrome",
            tab_id=1,
            url="chrome://newtab/",
            title="New Tab",
        )
        # Force timestamp into the past
        ctx.last_update_time = ctx.last_update_time - 300
        assert ctx.is_fresh(max_age_seconds=180) is False


class TestFullEndToEndWorkflow:
    """Verifies the exact user issue flow:
    Turn 1: 'Nova, open a Chrome new tab'
    Turn 2: 'In this new tab, search for mobile phones'
    """

    def test_complete_chained_pipeline(self):
        engine = NaturalLanguageIntentEngine()
        context = RecentInteractionContext()

        # --- TURN 1: User says: "Nova, open a Chrome new tab" ---
        turn1_input = "Nova, open a Chrome new tab"
        action1 = engine.parse(turn1_input, context=context)
        assert action1.intent == CanonicalIntent.OPEN_NEW_TAB
        assert action1.parameters.get("browser", "").lower() == "chrome"

        from intent.router import structured_action_to_browser_plan
        plan1 = structured_action_to_browser_plan(action1)
        assert plan1 is not None
        assert plan1.action == ActionType.OPEN_NEW_TAB

        # Simulate execution of Turn 1
        turn1_url = "chrome://newtab/"
        turn1_tab_id = 2
        context.add_turn(
            user_input=turn1_input,
            intent=action1.intent.value,
            action=plan1.action.value,
            action_result="Opened a new tab in Google Chrome",
            success=True,
            target_app="Google Chrome",
            target_browser="Google Chrome",
            current_url=turn1_url,
            current_title="New Tab",
        )
        context.update_browser_state(
            browser_name="Google Chrome",
            tab_id=turn1_tab_id,
            url=turn1_url,
            title="New Tab",
            is_new_tab=True,
        )

        # --- TURN 2: User says: "In this new tab, search for mobile phones" ---
        turn2_input = "In this new tab, search for mobile phones"
        action2 = engine.parse(turn2_input, context=context)

        # 1. Intent must NOT be CanonicalIntent.GENERAL_CONVERSATION
        assert action2.intent == CanonicalIntent.SEARCH_CURRENT_TAB

        # 2. Entity separation: Reference, Action, Payload
        assert action2.parameters.get("query") == "mobile phones"
        assert action2.parameters.get("reference") == "this_tab"
        assert action2.parameters.get("target") == "current_tab"

        # 3. Reference resolution
        resolver = ContextualReferenceResolver(context)
        resolved = resolver.resolve(action2.parameters["reference"])
        assert resolved is not None
        assert resolved.entity_type == "tab"
        assert resolved.app_name == "Google Chrome"

        # 4. Plan routing
        plan2 = structured_action_to_browser_plan(action2)
        assert plan2 is not None
        assert plan2.action == ActionType.SEARCH_CURRENT_TAB
        assert plan2.query == "mobile phones"

        # 5. Friendly Response Orchestration (NOT "I can't browse the web...")
        mock_result = BrowserResult(
            success=True,
            action_type=ActionType.SEARCH_CURRENT_TAB,
            message="Searched for 'mobile phones' in active tab",
            metadata={"query": "mobile phones", "url": "https://www.google.com/search?q=mobile+phones"},
        )
        orch = ResponseOrchestrator.format_action_response(action2, mock_result, turn2_input)
        assert orch.success is True
        assert "mobile phones" in orch.spoken_text
        assert "searched for mobile phones in that tab" in orch.spoken_text.lower() or "tab mein" in orch.spoken_text.lower()
        assert "can't browse" not in orch.spoken_text.lower()
        assert "cannot browse" not in orch.spoken_text.lower()

