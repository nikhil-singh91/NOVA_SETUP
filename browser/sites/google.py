"""Google Search browser automation skill."""

from __future__ import annotations

import time
import urllib.parse

from core.logger import get_logger
from browser.engine import BaseBrowserEngine
from browser.models import ActionType, BrowserActionPlan, BrowserResult, Platform
from browser.sessions import BrowserSessionManager
from browser.sites.base import BaseSiteSkill

logger = get_logger(__name__)


class GoogleSkill(BaseSiteSkill):
    """Automates Google web searches and search result interaction."""

    @property
    def name(self) -> str:
        return "google_skill"

    def can_handle(self, plan: BrowserActionPlan) -> bool:
        if plan.platform == Platform.GOOGLE:
            return True
        if plan.action_type == ActionType.SEARCH_WEB:
            return True
        if plan.action_type == ActionType.OPEN_RESULT:
            return True
        return False

    def execute(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
    ) -> BrowserResult:
        """Execute Google search or result action."""
        if plan.action_type == ActionType.OPEN_RESULT:
            return self._handle_open_result(plan, engine)

        query = (plan.query or "").strip()
        if not query:
            url = "https://www.google.com"
            spoken = "Opening Google."
        else:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://www.google.com/search?q={encoded}"
            spoken = f"Here are the Google search results for '{query}'."

        success = engine.open_url(url)
        return BrowserResult(
            success=success,
            action_type=plan.action_type,
            message=spoken,
            spoken_response=spoken,
            url=url,
        )

    def _handle_open_result(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
    ) -> BrowserResult:
        """Click on the first organic search result."""
        click_js = """
        (function() {
            const candidates = Array.from(document.querySelectorAll('a:has(h3), #rso a, #search a, div.g a, a[jsname]'));
            for (let a of candidates) {
                const href = a.href || "";
                if (href.startsWith('http') && !href.includes('google.com') && !href.includes('googleadservices') && !href.includes('&ad=')) {
                    a.scrollIntoView({behavior: 'smooth', block: 'center'});
                    a.click();
                    return a.innerText || "clicked";
                }
            }
            return "no_result_found";
        })()
        """
        res = engine.execute_script(click_js)
        if res and res != "no_result_found":
            spoken = "Opening the first search result."
            return BrowserResult(
                success=True,
                action_type=plan.action_type,
                message=spoken,
                spoken_response=spoken,
            )

        # Fallback via extracted search items
        items = engine.extract_search_results(limit=1)
        if items and items[0].get("url"):
            target_url = items[0]["url"]
            engine.open_url(target_url)
            spoken = f"Opening {items[0].get('title', 'the first result')}."
            return BrowserResult(
                success=True,
                action_type=plan.action_type,
                message=spoken,
                spoken_response=spoken,
                url=target_url,
            )

        return BrowserResult(
            success=False,
            action_type=plan.action_type,
            message="Could not find a clickable search result.",
            spoken_response="I couldn't find a clickable search result.",
            error="Result element not found",
        )
