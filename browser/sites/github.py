"""GitHub repository understanding, README extraction, and search skill."""

from __future__ import annotations

import json
import urllib.parse

from core.logger import get_logger

from browser.engine import BaseBrowserEngine
from browser.models import ActionType, BrowserActionPlan, BrowserResult, PageContent, Platform
from browser.sessions import BrowserSessionManager
from browser.sites.base import BaseSiteSkill

logger = get_logger(__name__)


class GitHubSkill(BaseSiteSkill):
    """Understands GitHub repositories, extracts READMEs, and explains project repositories."""

    @property
    def name(self) -> str:
        return "github_skill"

    def can_handle(self, plan: BrowserActionPlan) -> bool:
        if plan.platform == Platform.GITHUB:
            return True
        if plan.metadata.get("site_key") == "github":
            return True
        return False

    def execute(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
    ) -> BrowserResult:
        """Execute GitHub action or repository explanation."""
        query = (plan.query or "").strip()

        # 1. Explain active GitHub repo or read README
        if plan.action_type in (ActionType.EXPLAIN_PAGE, ActionType.READ_PAGE, ActionType.SUMMARIZE_PAGE):
            return self._handle_repo_explanation(plan, engine)

        # 2. Search GitHub
        if query:
            encoded = urllib.parse.quote_plus(query)
            search_url = f"https://github.com/search?q={encoded}"
            success = engine.open_url(search_url)
            spoken = f"Searching GitHub for '{query}'."
            return BrowserResult(
                success=success,
                action_type=plan.action_type,
                message=spoken,
                spoken_response=spoken,
                url=search_url,
            )

        # 3. Open GitHub homepage
        url = "https://github.com"
        success = engine.open_url(url)
        return BrowserResult(
            success=success,
            action_type=plan.action_type,
            message="Opened GitHub.",
            spoken_response="Opening GitHub.",
            url=url,
        )

    def _handle_repo_explanation(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
    ) -> BrowserResult:
        """Extract repository description, stars, and README snippet from active GitHub page."""
        extract_repo_js = """
        (function() {
            const descEl = document.querySelector('p[data-testid="repo-description"], p.f4.my-3');
            const starsEl = document.querySelector('#repo-stars-counter-star, .Counter[title]');
            const readmeEl = document.querySelector('article.markdown-body, #readme article');
            return JSON.stringify({
                description: descEl ? descEl.innerText.trim() : "",
                stars: starsEl ? starsEl.innerText.trim() : "N/A",
                readme_snippet: readmeEl ? readmeEl.innerText.substring(0, 1000).trim() : ""
            });
        })()
        """
        raw_info = engine.execute_script(extract_repo_js)
        info = {}
        if raw_info:
            try:
                info = json.loads(str(raw_info))
            except Exception:
                pass

        page_info = engine.get_page_info()
        title = page_info.get("title", "GitHub Project")
        desc = info.get("description", "")
        stars = info.get("stars", "")

        if desc:
            spoken = f"This repository is {title}. {desc} (Stars: {stars})."
        else:
            spoken = f"This is {title} on GitHub."

        return BrowserResult(
            success=True,
            action_type=plan.action_type,
            message=spoken,
            spoken_response=spoken,
            page_content=PageContent(
                url=page_info.get("url", ""),
                title=title,
                text=info.get("readme_snippet", desc),
            ),
            metadata=info,
        )
