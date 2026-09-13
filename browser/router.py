"""Action routing and skill dispatching for NOVA Browser Actions V1, V2, and V2.1."""

from __future__ import annotations

import time

from core.logger import get_logger
from core.registry import registry

from browser.context import BrowserContextManager
from browser.engine import BaseBrowserEngine, log_browser_diagnostics
from browser.models import ActionType, BrowserActionPlan, BrowserResult, PageContent
from browser.sessions import BrowserSessionManager
from browser.sites import (
    AmazonSkill,
    BaseSiteSkill,
    GenericSiteSkill,
    GitHubSkill,
    GoogleSkill,
    YouTubeSkill,
)

logger = get_logger(__name__)


class BrowserActionRouter:
    """Routes structured BrowserActionPlan objects to appropriate site skills or navigation handlers."""

    def __init__(
        self,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
        context_mgr: BrowserContextManager | None = None,
    ) -> None:
        self.engine = engine
        self.sessions = sessions
        self.context_mgr = context_mgr or BrowserContextManager()
        self._skills: list[BaseSiteSkill] = [
            YouTubeSkill(),
            GitHubSkill(),
            AmazonSkill(),
            GoogleSkill(),
            GenericSiteSkill(),
        ]

    def register_skill(self, skill: BaseSiteSkill, priority: int = 0) -> None:
        """Register a new site skill at the given priority."""
        self._skills.insert(priority, skill)
        logger.info("Registered browser skill '%s' (priority=%d).", skill.name, priority)

    def route(self, plan: BrowserActionPlan) -> BrowserResult:
        """Find the capable site skill or internal handler and execute the action plan."""
        logger.info("Routing browser plan: action=%s, platform=%s", plan.action_type.value, plan.platform.value)

        # 1. Tab Switching Actions ("Next tab", "Previous tab", "Switch to tab 2", "Switch to YouTube")
        if plan.action_type == ActionType.SWITCH_TAB:
            return self._handle_tab_switching(plan)

        # 1B. Open Dedicated New Tab or Search in Current Tab
        if plan.action_type in (ActionType.OPEN_NEW_TAB, ActionType.SEARCH_CURRENT_TAB):
            generic_skill = next((s for s in self._skills if isinstance(s, GenericSiteSkill)), None)
            if generic_skill:
                return generic_skill.execute(plan, self.engine, self.sessions)

        # 2. Scrolling Actions ("Scroll down", "Scroll up", "Scroll to top", "Scroll to bottom")
        if plan.action_type == ActionType.SCROLL_PAGE:
            return self._handle_scrolling(plan)

        # 3. History Navigation ("Go back", "Go forward")
        if plan.action_type == ActionType.NAVIGATE_BACK:
            success = self.engine.navigate_back()
            msg = "Navigated back." if success else "Could not go back."
            return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

        if plan.action_type == ActionType.NAVIGATE_FORWARD:
            success = self.engine.navigate_forward()
            msg = "Navigated forward." if success else "Could not go forward."
            return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

        # 4. Close Research Tabs
        if plan.action_type == ActionType.CLOSE_RESEARCH_TABS:
            closed = self.sessions.close_research_tabs()
            self.context_mgr.clear_research_tabs()
            msg = f"Closed {closed} research tabs." if closed > 0 else "No active research tabs to close."
            return BrowserResult(success=True, action_type=plan.action_type, message=msg, spoken_response=msg)

        # 5. Ordinal Search Result Resolution ("Open the second one")
        if plan.action_type == ActionType.OPEN_RESULT and plan.target_index is not None:
            item = self.context_mgr.get_result_by_index(plan.target_index)
            if item and item.url:
                success = self.engine.open_url(item.url)
                spoken = f"Opening result #{plan.target_index}: {item.title}."
                log_browser_diagnostics("OPEN_ORDINAL_RESULT", "SUCCESS" if success else "FAILED", url=item.url, title=item.title)
                return BrowserResult(
                    success=success,
                    action_type=plan.action_type,
                    message=spoken,
                    spoken_response=spoken,
                    url=item.url,
                )

        # 6. Webpage Understanding (Read / Summarize / Explain Page)
        if plan.action_type in (ActionType.READ_PAGE, ActionType.SUMMARIZE_PAGE, ActionType.EXPLAIN_PAGE):
            # Synchronize real active tab
            state = self.engine.refresh_browser_state()
            page_url = state.get("url", "")
            if "github.com" in page_url:
                github_skill = next((s for s in self._skills if isinstance(s, GitHubSkill)), None)
                if github_skill:
                    return github_skill.execute(plan, self.engine, self.sessions)

            return self._handle_page_understanding(plan)

        # 7. Dispatch to Specialized Site Skills
        for skill in self._skills:
            if skill.can_handle(plan):
                logger.debug("Dispatching plan to skill: %s", skill.name)
                try:
                    return skill.execute(plan, self.engine, self.sessions)
                except Exception as exc:
                    logger.error("Error in skill '%s': %s", skill.name, exc, exc_info=True)
                    return BrowserResult(
                        success=False,
                        action_type=plan.action_type,
                        message=f"Browser action failed: {exc}",
                        spoken_response="Sorry Boss, something went wrong while automating the browser.",
                        error=str(exc),
                    )

        logger.warning("No capable skill found for action: %s", plan.action_type.value)
        return BrowserResult(
            success=False,
            action_type=plan.action_type,
            message="No supported browser skill available for this action.",
            spoken_response="I don't know how to perform that browser action yet.",
            error="Unsupported browser action",
        )

    def _handle_tab_switching(self, plan: BrowserActionPlan) -> BrowserResult:
        """Execute real browser tab switching."""
        q = (plan.query or "").strip().lower()

        if q == "next":
            success, new_idx, new_title = self.engine.next_tab()
            title_text = f" ('{new_title[:40]}')" if new_title else ""
            msg = f"Switched to next tab #{new_idx}{title_text}."
            return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

        if q == "previous":
            success, new_idx, new_title = self.engine.previous_tab()
            title_text = f" ('{new_title[:40]}')" if new_title else ""
            msg = f"Switched to previous tab #{new_idx}{title_text}."
            return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

        if q == "index" and plan.target_index:
            success = self.engine.set_active_tab_index(plan.target_index)
            time.sleep(0.2)
            state = self.engine.refresh_browser_state()
            title_text = f" ('{state.get('title', '')[:40]}')" if state.get('title') else ""
            msg = f"Switched to tab #{plan.target_index}{title_text}." if success else f"Could not switch to tab #{plan.target_index}."
            return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

        # Keyword tab search (e.g. "YouTube", "Google", "ChatGPT")
        if q:
            success, new_idx, new_title = self.engine.switch_to_tab_by_title_or_url(q)
            if success:
                msg = f"Switched to tab #{new_idx} ({new_title[:40]})."
                return BrowserResult(success=True, action_type=plan.action_type, message=msg, spoken_response=msg)
            else:
                msg = f"No open tab found matching '{plan.query}'."
                return BrowserResult(success=False, action_type=plan.action_type, message=msg, spoken_response=msg, error="Tab not found")

        return BrowserResult(success=False, action_type=plan.action_type, message="Unknown tab switch request.", spoken_response="I couldn't switch tabs.")

    def _handle_scrolling(self, plan: BrowserActionPlan) -> BrowserResult:
        """Execute real browser page scrolling."""
        q = (plan.query or "").strip().lower()

        if q == "top":
            success = self.engine.scroll_to_top()
            msg = "Scrolled to top of the page."
            return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

        if q == "bottom":
            success = self.engine.scroll_to_bottom()
            msg = "Scrolled to bottom of the page."
            return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

        if q == "up":
            success = self.engine.scroll_page(direction="up")
            msg = "Scrolled page up."
            return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

        # Default: scroll down
        success = self.engine.scroll_page(direction="down")
        msg = "Scrolled page down."
        return BrowserResult(success=success, action_type=plan.action_type, message=msg, spoken_response=msg)

    def _handle_page_understanding(self, plan: BrowserActionPlan) -> BrowserResult:
        """Extract content from the real active tab and provide direct reading or AI summary."""
        page: PageContent = self.engine.extract_page_content()
        self.context_mgr.set_active_page(page)

        if page.is_empty:
            return BrowserResult(
                success=False,
                action_type=plan.action_type,
                message="The current webpage did not contain readable body text.",
                spoken_response="I couldn't extract readable text from this page.",
                url=page.url,
            )

        # Direct reading request ("What is written on this page?", "Read this page")
        if plan.action_type == ActionType.READ_PAGE:
            text_snippet = page.text[:1200].strip()
            spoken = f"On '{page.title}', it says: {text_snippet[:250]}..."
            log_browser_diagnostics("READ_PAGE", "SUCCESS", url=page.url, title=page.title, extra=f"Length: {len(page.text)} chars")
            return BrowserResult(
                success=True,
                action_type=plan.action_type,
                message=f"Page Title: {page.title}\nURL: {page.url}\n\nContent:\n{page.text}",
                spoken_response=spoken,
                url=page.url,
                page_content=page,
            )

        # Explanation / Summarization request ("What is this page about?", "Summarize this page")
        if registry.exists("provider_manager"):
            try:
                provider_mgr = registry.get("provider_manager")
                prompt = (
                    f"You are NOVA, an intelligent AI assistant. The user wants you to summarize the currently open webpage.\n\n"
                    f"Webpage Title: {page.title}\nURL: {page.url}\n\n"
                    f"Page Content:\n{page.text[:4000]}\n\n"
                    "Provide a clear, 2-3 paragraph summary answering what this page is about and highlighting its key points."
                )
                res = provider_mgr.generate(prompt)
                if res and res.text:
                    ai_summary = res.text.strip()
                    spoken = f"This page is about '{page.title}'. {ai_summary[:250]}."
                    log_browser_diagnostics("SUMMARIZE_PAGE_AI", "SUCCESS", url=page.url, title=page.title)
                    return BrowserResult(
                        success=True,
                        action_type=plan.action_type,
                        message=ai_summary,
                        spoken_response=spoken,
                        url=page.url,
                        page_content=page,
                    )
            except Exception as exc:
                logger.debug("Provider summary error: %s", exc)

        # Fallback local explanation
        first_part = page.text[:350].replace("\n", " ").strip()
        spoken = f"This page is titled '{page.title}'. {first_part}..."
        log_browser_diagnostics("SUMMARIZE_PAGE_LOCAL", "SUCCESS", url=page.url, title=page.title)
        return BrowserResult(
            success=True,
            action_type=plan.action_type,
            message=f"Title: {page.title}\n\n{page.text[:1000]}...",
            spoken_response=spoken,
            url=page.url,
            page_content=page,
        )
