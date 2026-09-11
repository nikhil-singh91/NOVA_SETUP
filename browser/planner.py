"""Multi-step action planner and web research coordinator for NOVA Browser Actions V2."""

from __future__ import annotations

import threading
import time
import urllib.parse
from typing import Any, Callable

from config.settings import settings
from core.event_bus import NovaEvent
from core.logger import get_logger
from core.registry import registry
from browser.context import BrowserContextManager
from browser.engine import BaseBrowserEngine
from browser.models import (
    ActionType,
    BrowserActionCancelled,
    BrowserResult,
    BrowserTaskPlan,
    PageContent,
    Platform,
    TaskStep,
)
from browser.sessions import BrowserSessionManager

logger = get_logger(__name__)


class BrowserTaskPlanner:
    """Creates structured multi-step browser execution plans and orchestrates web research."""

    def __init__(self, max_steps: int | None = None) -> None:
        self.max_steps = max_steps or settings.browser_max_task_steps or 6
        self.max_pages = settings.browser_max_research_pages or 3

    def generate_plan(
        self,
        goal: str,
        action_type: ActionType,
        platform: Platform = Platform.GENERIC,
        query: str = "",
    ) -> BrowserTaskPlan:
        """Create a bounded, step-by-step task plan for complex user requests."""
        steps: list[TaskStep] = []

        if action_type == ActionType.RESEARCH_TOPIC:
            steps = [
                TaskStep(1, "search_web", "google", {"query": query}),
                TaskStep(2, "extract_search_results", "search_page", {"limit": self.max_pages}),
                TaskStep(3, "open_candidate_pages", "research_tabs", {"max_pages": self.max_pages}),
                TaskStep(4, "extract_page_contents", "active_tabs", {}),
                TaskStep(5, "synthesize_findings", "ai_reasoning", {"query": query}),
            ]
        elif action_type == ActionType.COMPARE_PRODUCTS:
            steps = [
                TaskStep(1, "open_marketplace", "amazon", {"query": query}),
                TaskStep(2, "extract_product_listings", "catalog", {"limit": 2}),
                TaskStep(3, "compare_specifications", "ai_reasoning", {}),
            ]
        elif action_type in (ActionType.READ_PAGE, ActionType.SUMMARIZE_PAGE, ActionType.EXPLAIN_PAGE):
            steps = [
                TaskStep(1, "extract_active_page", "current_tab", {}),
                TaskStep(2, "summarize_content", "ai_reasoning", {"mode": action_type.value}),
            ]
        else:
            steps = [
                TaskStep(1, action_type.value, platform.value, {"query": query}),
            ]

        plan = BrowserTaskPlan(
            goal=goal,
            steps=steps[: self.max_steps],
            max_steps=self.max_steps,
        )
        logger.info("Generated BrowserTaskPlan (%s) with %d steps for goal: '%s'", plan.task_id, len(steps), goal)
        return plan

    def execute_research(
        self,
        query: str,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
        context_mgr: BrowserContextManager,
        stop_event: threading.Event,
    ) -> BrowserResult:
        """Execute a complete, bounded, and cancellable multi-step web research workflow."""
        logger.info("Starting web research for query: '%s'", query)
        self._publish_event(NovaEvent.BROWSER_TASK_STARTED, task="research", query=query)

        # Step 1: Open Google Search
        encoded = urllib.parse.quote_plus(query)
        search_url = f"https://www.google.com/search?q={encoded}"
        if not engine.open_url(search_url):
            return BrowserResult(
                success=False,
                action_type=ActionType.RESEARCH_TOPIC,
                message=f"Failed to launch search for '{query}'.",
                spoken_response="I couldn't perform the web search.",
                error="Search navigation failed",
            )

        if stop_event.is_set():
            raise BrowserActionCancelled("Research cancelled by user.")

        time.sleep(1.2)

        # Step 2: Extract top organic results
        results = engine.extract_search_results(limit=self.max_pages)
        context_mgr.set_search_results(query, results)

        if not results:
            # Fallback to general page text if organic search cards not found
            extracted = engine.extract_page_content()
            self._publish_event(
                NovaEvent.BROWSER_TASK_COMPLETED,
                query=query,
                sources_count=1,
            )
            return BrowserResult(
                success=True,
                action_type=ActionType.RESEARCH_TOPIC,
                message=f"Research results for '{query}'.",
                spoken_response=f"I found information about '{query}'.",
                url=search_url,
                page_content=extracted,
            )

        # Step 3: Open top candidate results and extract key contents
        gathered_pages: list[PageContent] = []
        for i, item in enumerate(results[: self.max_pages]):
            if stop_event.is_set():
                raise BrowserActionCancelled("Research cancelled during page extraction.")

            link_url = item.get("url")
            if not link_url:
                continue

            try:
                # Open in research tab
                sessions.open_research_tab(link_url)
                context_mgr.add_research_tab(link_url)
                time.sleep(1.5)

                page = engine.extract_page_content()
                if not page.is_empty:
                    gathered_pages.append(page)
                    context_mgr.set_active_page(page)

                self._publish_event(
                    NovaEvent.BROWSER_TASK_STEP_COMPLETED,
                    step=f"extracted_page_{i+1}",
                    url=link_url,
                )
            except Exception as exc:
                logger.debug("Error extracting page '%s': %s", link_url, exc)

        if stop_event.is_set():
            raise BrowserActionCancelled("Research cancelled before synthesis.")

        # Step 4: Synthesize gathered sources via AI Reasoning if available
        synthesis = self._synthesize_content(query, gathered_pages, results)

        self._publish_event(
            NovaEvent.BROWSER_TASK_COMPLETED,
            query=query,
            sources_count=len(gathered_pages),
        )

        return BrowserResult(
            success=True,
            action_type=ActionType.RESEARCH_TOPIC,
            message=synthesis["text"],
            spoken_response=synthesis["spoken"],
            url=search_url,
            metadata={"sources": results, "extracted_count": len(gathered_pages)},
        )

    def _synthesize_content(
        self,
        query: str,
        pages: list[PageContent],
        search_items: list[dict[str, str]],
    ) -> dict[str, str]:
        """Synthesize gathered page contents into a concise answer."""
        if not pages:
            # Fallback to search result snippets
            snippets = [f"• {item.get('title')}: {item.get('snippet')}" for item in search_items[:3]]
            text = f"Research summary for '{query}':\n" + "\n".join(snippets)
            spoken = f"I researched '{query}'. Here are the top findings from {len(search_items[:3])} sources."
            return {"text": text, "spoken": spoken}

        # Try using ProviderManager via registry if available
        if registry.exists("provider_manager"):
            try:
                provider_mgr = registry.get("provider_manager")
                content_snippets = []
                for p in pages:
                    content_snippets.append(f"Source: {p.title} ({p.url})\n{p.text[:1200]}")

                prompt = (
                    f"User asked for research on: '{query}'.\n"
                    f"Here is extracted content from {len(pages)} web sources:\n"
                    + "\n---\n".join(content_snippets)
                    + "\n\nProvide a concise 3-4 bullet point summary answering the user's research request. "
                    "Include key facts and cite the source domain."
                )

                response_obj = provider_mgr.generate(prompt)
                if response_obj and response_obj.text:
                    ai_text = response_obj.text.strip()
                    spoken = f"I finished researching '{query}'. Based on the top sources: {ai_text[:250]}."
                    return {"text": ai_text, "spoken": spoken}
            except Exception as exc:
                logger.debug("AI provider synthesis note: %s", exc)

        # Fallback local synthesis
        bullets = []
        for p in pages:
            summary = p.text[:300].replace("\n", " ").strip()
            bullets.append(f"• **{p.title}**: {summary}...")

        text = f"Research findings for '{query}':\n" + "\n".join(bullets)
        spoken = f"I researched '{query}' and reviewed {len(pages)} sources. Here are the main highlights."
        return {"text": text, "spoken": spoken}

    def _publish_event(self, event: NovaEvent, **payload: Any) -> None:
        """Helper to publish task lifecycle events on EventBus."""
        try:
            if registry.exists("event_bus"):
                bus = registry.get("event_bus")
                bus.publish(event, **payload)
        except Exception:
            pass
