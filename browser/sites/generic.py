"""Trusted site registry, website discovery, and generic website automation skill."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from core.environment import environment_observer, log_environment_debug
from core.logger import get_logger
from browser.engine import BaseBrowserEngine, log_browser_diagnostics
from browser.models import ActionType, BrowserActionPlan, BrowserResult, Platform
from browser.sessions import BrowserSessionManager
from browser.sites.base import BaseSiteSkill

logger = get_logger(__name__)


# Trusted Site Registry containing official URLs and search endpoints
TRUSTED_SITES: dict[str, dict[str, str]] = {
    "youtube": {
        "url": "https://www.youtube.com",
        "search_url": "https://www.youtube.com/results?search_query={query}",
        "name": "YouTube",
    },
    "google": {
        "url": "https://www.google.com",
        "search_url": "https://www.google.com/search?q={query}",
        "name": "Google",
    },
    "flipkart": {
        "url": "https://www.flipkart.com",
        "search_url": "https://www.flipkart.com/search?q={query}",
        "name": "Flipkart",
    },
    "amazon": {
        "url": "https://www.amazon.com",
        "search_url": "https://www.amazon.com/s?k={query}",
        "name": "Amazon",
    },
    "aktu": {
        "url": "https://aktu.ac.in",
        "search_url": "https://www.google.com/search?q=site%3Aaktu.ac.in+{query}",
        "name": "Dr. A.P.J. Abdul Kalam Technical University (AKTU)",
    },
    "github": {
        "url": "https://github.com",
        "search_url": "https://github.com/search?q={query}",
        "name": "GitHub",
    },
    "wikipedia": {
        "url": "https://www.wikipedia.org",
        "search_url": "https://en.wikipedia.org/wiki/Special:Search?search={query}",
        "name": "Wikipedia",
    },
    "instagram": {
        "url": "https://www.instagram.com",
        "search_url": "https://www.instagram.com/explore/tags/{query}/",
        "name": "Instagram",
    },
    "whatsapp": {
        "url": "https://web.whatsapp.com",
        "search_url": "https://web.whatsapp.com",
        "name": "WhatsApp Web",
    },
    "whatsapp web": {
        "url": "https://web.whatsapp.com",
        "search_url": "https://web.whatsapp.com",
        "name": "WhatsApp Web",
    },
    "netflix": {
        "url": "https://www.netflix.com",
        "search_url": "https://www.netflix.com/search?q={query}",
        "name": "Netflix",
    },
    "spotify": {
        "url": "https://open.spotify.com",
        "search_url": "https://open.spotify.com/search/{query}",
        "name": "Spotify",
    },
    "reddit": {
        "url": "https://www.reddit.com",
        "search_url": "https://www.reddit.com/search/?q={query}",
        "name": "Reddit",
    },
    "twitter": {
        "url": "https://x.com",
        "search_url": "https://x.com/search?q={query}",
        "name": "X",
    },
    "x": {
        "url": "https://x.com",
        "search_url": "https://x.com/search?q={query}",
        "name": "X",
    },
    "linkedin": {
        "url": "https://www.linkedin.com",
        "search_url": "https://www.linkedin.com/search/results/all/?keywords={query}",
        "name": "LinkedIn",
    },
    "leetcode": {
        "url": "https://leetcode.com",
        "search_url": "https://leetcode.com/problemset/all/?search={query}",
        "name": "LeetCode",
    },
    "chatgpt": {
        "url": "https://chatgpt.com",
        "search_url": "https://chatgpt.com",
        "name": "ChatGPT",
    },
    "gmail": {
        "url": "https://mail.google.com",
        "search_url": "https://mail.google.com/mail/u/0/#search/{query}",
        "name": "Gmail",
    },
    "google drive": {
        "url": "https://drive.google.com",
        "search_url": "https://drive.google.com/drive/search?q={query}",
        "name": "Google Drive",
    },
    "drive": {
        "url": "https://drive.google.com",
        "search_url": "https://drive.google.com/drive/search?q={query}",
        "name": "Google Drive",
    },
    "notion": {
        "url": "https://notion.so",
        "search_url": "https://notion.so",
        "name": "Notion",
    },
    "codechef": {
        "url": "https://codechef.com",
        "search_url": "https://www.codechef.com/practice?search={query}",
        "name": "CodeChef",
    },
    "stackoverflow": {
        "url": "https://stackoverflow.com",
        "search_url": "https://stackoverflow.com/search?q={query}",
        "name": "Stack Overflow",
    },
}


class GenericSiteSkill(BaseSiteSkill):
    """Handles generic URL opening, trusted sites, and website discovery for unknown entities."""

    @property
    def name(self) -> str:
        return "generic_site_skill"

    def can_handle(self, plan: BrowserActionPlan) -> bool:
        return True  # Fallback handler for all generic sites and direct URLs

    def discover_official_website(self, entity_name: str) -> str | None:
        """Search and extract the primary official website domain for an organization or entity."""
        entity_clean = entity_name.lower().strip()
        entity_clean = re.sub(r"^(?:the\s+)?(?:official\s+)?(?:website\s+of\s+|website\s+for\s+|site\s+of\s+|site\s+for\s+)?", "", entity_clean).strip()
        entity_clean = re.sub(r"\s+(?:website|site|webpage)$", "", entity_clean).strip()
        entity_clean = re.sub(r"\s+(?:for\s+me|please|kripya|now)$", "", entity_clean).strip()

        # 1. Check direct match in TRUSTED_SITES
        if entity_clean in TRUSTED_SITES:
            return TRUSTED_SITES[entity_clean]["url"]

        # 2. Check if clean name matches known domain pattern (e.g. aktu.ac.in, flipkart.com)
        if "." in entity_clean and not any(w in entity_clean for w in [" ", ","]):
            return f"https://{entity_clean}" if not entity_clean.startswith("http") else entity_clean

        # 3. Dynamic HTTP search-based discovery
        try:
            from browser.extractor import PageContentExtractor
            extractor = PageContentExtractor()
            links = extractor.search_query_links(f"{entity_clean} official website", limit=4)
            if links:
                for item in links:
                    url = item.get("url", "")
                    # Filter out search engines, wiki directories, or ads
                    if url and not any(d in url.lower() for d in ["wikipedia.org", "facebook.com", "instagram.com", "twitter.com", "linkedin.com"]):
                        return url
                if links[0].get("url"):
                    return links[0]["url"]
        except Exception as exc:
            logger.debug("Website discovery error for '%s': %s", entity_clean, exc)
        return None

    def execute(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
    ) -> BrowserResult:
        """Open trusted site, direct URL, or perform discovery for unknown entities."""
        platform_key = (
            plan.metadata.get("site_key")
            or plan.platform.value
            or ""
        ).lower().strip()
        query = (plan.query or "").strip()

        # 1. Close active tab
        if plan.action_type == ActionType.CLOSE_TAB:
            sessions.stop_active_task()
            success = engine.close_tab()
            msg = "Closed the browser tab." if success else "Could not close tab."
            return BrowserResult(
                success=success,
                action_type=plan.action_type,
                message=msg,
                spoken_response=msg,
            )

        # 2. Check trusted site registry
        site_info = TRUSTED_SITES.get(platform_key)

        if site_info:
            site_name = site_info["name"]
            if query and plan.action_type == ActionType.SEARCH_SITE:
                encoded = urllib.parse.quote_plus(query)
                url = site_info["search_url"].format(query=encoded)
                spoken = f"Searching {site_name} for '{query}'."
            else:
                url = site_info["url"]
                spoken = f"Opening {site_name}."
        elif plan.target_url:
            url = plan.target_url
            spoken = f"Opening {url}."
        elif plan.action_type == ActionType.OPEN_SITE and platform_key and platform_key not in ("generic", ""):
            # Website Discovery for unknown entities (e.g. "Mirai School of Technology", "AKTU")
            logger.info("Discovering website for entity: '%s'", platform_key)
            discovered_url = self.discover_official_website(platform_key)
            if discovered_url:
                url = discovered_url
                spoken = f"Opening {platform_key.title()} website."
                log_browser_diagnostics("DISCOVER_WEBSITE", "SUCCESS", url=discovered_url, extra=f"Entity: {platform_key}")
            else:
                encoded = urllib.parse.quote_plus(f"{platform_key} official website")
                url = f"https://www.google.com/search?q={encoded}"
                spoken = f"Searching Google for {platform_key} website."
        elif query and plan.action_type == ActionType.SEARCH_SITE:
            # Check if platform_key is known or search within domain
            discovered_site_url = self.discover_official_website(platform_key) if platform_key and platform_key != "generic" else None
            if discovered_site_url:
                parsed_domain = urllib.parse.urlparse(discovered_site_url).netloc
                encoded = urllib.parse.quote_plus(f"{query} site:{parsed_domain}")
                url = f"https://www.google.com/search?q={encoded}"
                spoken = f"Searching for {query} on {platform_key.title()}."
            else:
                encoded = urllib.parse.quote_plus(f"{query} site:{platform_key}")
                url = f"https://www.google.com/search?q={encoded}"
                spoken = f"Searching Google for {query} on {platform_key}."
        else:
            # Fallback for unknown platform or search
            entity = platform_key or query
            discovered = self.discover_official_website(entity) if entity else None
            if discovered:
                url = discovered
                spoken = f"Opening {entity.title()}."
            else:
                encoded = urllib.parse.quote_plus(entity)
                url = f"https://www.google.com/search?q={encoded}"
                spoken = f"Searching Google for '{entity}'."

        success = engine.open_url(url)

        # Verification step: update environment context
        if success:
            environment_observer.update_action_context(
                action="OPEN_WEBSITE",
                opened_target=url,
            )

        return BrowserResult(
            success=success,
            action_type=plan.action_type,
            message=spoken,
            spoken_response=spoken,
            url=url,
        )
