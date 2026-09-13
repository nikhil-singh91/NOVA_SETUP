"""Integration tests for Anakin Live Web Intelligence within NOVA architecture."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.context import ContextualReferenceResolver, RecentInteractionContext
from core.task_agent.registry import CapabilityRegistry, capability_registry
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent
from services.anakin_service import AnakinSearchResult, WebSource, anakin_service


class TestAnakinNovaIntegration:
    """Integration verification across intent, capability registry, context, and browser."""

    def test_live_web_request_invokes_search_intent(self) -> None:
        """13. Live web request classifies to SEARCH_WEB."""
        engine = NaturalLanguageIntentEngine()
        queries = [
            "What's the latest news about NVIDIA?",
            "Find the current price of iPhone 17.",
            "What are the best laptops under ₹50,000?",
            "Search for the latest AI agent frameworks.",
            "Search the web for the latest AI news.",
            "Find current information about the Anakin Forge hackathon.",
        ]
        for q in queries:
            action = engine.parse(q)
            assert action.intent == CanonicalIntent.SEARCH_WEB, f"Failed on query: {q}"

    def test_deep_research_request_invokes_agentic_research_intent(self) -> None:
        """14. In-depth research or comparison request classifies to RESEARCH_TOPIC."""
        engine = NaturalLanguageIntentEngine()
        queries = [
            "Research the best laptops under ₹50,000 for an AI/ML student and compare them.",
            "Do a detailed comparison of the top AI coding agents in 2026.",
            "Research this topic using multiple reliable sources: agent architectures.",
            "Investigate this company and summarize what you find.",
        ]
        for q in queries:
            action = engine.parse(q)
            assert action.intent == CanonicalIntent.RESEARCH_TOPIC, f"Failed on query: {q}"

    def test_normal_question_does_not_invoke_anakin(self) -> None:
        """11. Normal math and conversational questions do NOT invoke Anakin search."""
        engine = NaturalLanguageIntentEngine()
        action = engine.parse("What's 2 + 2?")
        assert action.intent != CanonicalIntent.SEARCH_WEB
        assert action.intent != CanonicalIntent.RESEARCH_TOPIC
        assert action.intent == CanonicalIntent.GENERAL_CONVERSATION

    def test_mac_command_does_not_invoke_anakin(self) -> None:
        """12. Mac control commands do NOT invoke Anakin search."""
        engine = NaturalLanguageIntentEngine()
        vol_action = engine.parse("Increase the volume.")
        assert vol_action.intent == CanonicalIntent.CONTROL_VOLUME

        app_action = engine.parse("Open Telegram.")
        assert app_action.intent == CanonicalIntent.LAUNCH_APP

        wifi_action = engine.parse("Turn wifi off.")
        assert wifi_action.intent == CanonicalIntent.CONTROL_WIFI

    def test_capability_registry_reports_live_web_research(self) -> None:
        """10. Capability registry registers web.live_search and web.agentic_research."""
        assert capability_registry.has("web.live_search")
        assert capability_registry.has("web.agentic_research")

        health = capability_registry.get_health("live_web_research")
        assert "capability_id" in health
        assert health["capability_id"] == "live_web_research"
        assert health["required_dependency"] == "anakin-sdk"

    def test_results_enter_task_context_and_resolve_followups(self) -> None:
        """15, 16, 17. Results enter task context, source URLs preserved, and follow-ups resolve."""
        ctx = RecentInteractionContext()
        resolver = ContextualReferenceResolver(ctx)

        # Simulate web research completed
        sources = [
            {
                "index": 1,
                "title": "Redmi Note 13 Pro 5G",
                "url": "https://mi.com/in/redmi-note-13-pro",
                "snippet": "200MP camera, Snapdragon 7s Gen 2, priced under ₹20,000.",
            },
            {
                "index": 2,
                "title": "Realme Narzo 70 Pro",
                "url": "https://realme.com/in/narzo-70-pro",
                "snippet": "Sony IMX890 flagship OIS camera under ₹20k.",
            },
            {
                "index": 3,
                "title": "Moto G84 5G",
                "url": "https://motorola.in/smartphones-moto-g84-5g",
                "snippet": "120Hz pOLED display, 50MP OIS camera.",
            },
        ]
        ctx.record_web_research(
            query="best smartphones under ₹20,000",
            sources=sources,
            summary="Found top smartphones under ₹20,000 in India.",
            mode="search",
        )

        # 15. Verify research context is stored
        assert ctx.last_search_query == "best smartphones under ₹20,000"
        assert len(ctx.last_search_results) == 3

        # 16. Test follow-up resolution: "the first one" / "open the first phone"
        res_first = resolver.resolve("the first one")
        assert res_first.resolved
        assert res_first.target_type == "search_result"
        assert res_first.target_value["index"] == 1
        assert res_first.target_value["url"] == "https://mi.com/in/redmi-note-13-pro"
        assert res_first.target_value["title"] == "Redmi Note 13 Pro 5G"

        res_second = resolver.resolve("open the second result")
        assert res_second.resolved
        assert res_second.target_value["index"] == 2
        assert res_second.target_value["url"] == "https://realme.com/in/narzo-70-pro"

        res_third = resolver.resolve("the third phone")
        assert res_third.resolved
        assert res_third.target_value["index"] == 3
        assert res_third.target_value["url"] == "https://motorola.in/smartphones-moto-g84-5g"

    def test_browser_separation_from_research(self) -> None:
        """Browser actions and Anakin data intelligence remain distinct capabilities."""
        # web.live_search is in web_intelligence subsystem
        cap_web = capability_registry.get("web.live_search")
        assert cap_web is not None
        assert cap_web.subsystem == "web_intelligence"

        # browser.open_site is in browser subsystem
        cap_browser = capability_registry.get("browser.open_site")
        assert cap_browser is not None
        assert cap_browser.subsystem == "browser"
