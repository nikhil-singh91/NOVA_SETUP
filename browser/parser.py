"""Natural language intent parser for NOVA Browser Actions V1, V2, and V2.1."""

from __future__ import annotations

import re

from core.logger import get_logger

from browser.models import ActionType, BrowserActionPlan, Platform
from browser.sites.generic import TRUSTED_SITES

logger = get_logger(__name__)


class BrowserIntentParser:
    """Parses natural voice or text commands into structured BrowserActionPlan objects."""

    def parse(self, text: str) -> BrowserActionPlan | None:
        """Parse natural language text into a BrowserActionPlan, or return None if not a browser intent."""
        if not text:
            return None

        clean_text = text.strip()
        lower_text = clean_text.lower()

        # 1. Stop / Cancel / Close Research Commands
        plan = self._parse_stop_commands(lower_text, clean_text)
        if plan:
            return plan

        # 2. Tab Switching & Browser Navigation (Next Tab, Previous Tab, Switch to X, Scroll, Back, Forward)
        plan = self._parse_navigation_commands(lower_text, clean_text)
        if plan:
            return plan

        # 3. Ordinal Search Result Selection ("Open the second one", "Open the 3rd result")
        plan = self._parse_ordinal_result_commands(lower_text, clean_text)
        if plan:
            return plan

        # 4. Webpage Understanding ("What is written on this page?", "Read this page", "Summarize this article", "What is this website about?")
        plan = self._parse_page_understanding_commands(lower_text, clean_text)
        if plan:
            return plan

        # 5. Product Comparison ("Compare these two products", "Find the best laptop under 60000")
        plan = self._parse_comparison_commands(lower_text, clean_text)
        if plan:
            return plan

        # 6. Deep Web Research ("Research Python frameworks", "Find internships for CSE students")
        plan = self._parse_research_commands(lower_text, clean_text)
        if plan:
            return plan

        # 7. YouTube Shorts Navigation (Next / Previous / Auto Scroll)
        plan = self._parse_shorts_commands(lower_text, clean_text)
        if plan:
            return plan

        # 8. Media Playback Commands ("Play song Mere Liye", "Play Kesariya", "Watch Motu Patlu")
        plan = self._parse_play_commands(lower_text, clean_text)
        if plan:
            return plan

        # 9. Search on Specific Sites ("In Flipkart search mobile phones", "Search iPhone here", "Search Amazon for ...")
        plan = self._parse_site_search_commands(lower_text, clean_text)
        if plan:
            return plan

        # 10. General Web Search ("Search Google for ...", "Google ...")
        plan = self._parse_web_search_commands(lower_text, clean_text)
        if plan:
            return plan

        # 11. Open Specific Websites or Entities ("Open Mirai School of Technology website", "Open Instagram", etc.)
        plan = self._parse_open_site_commands(lower_text, clean_text)
        if plan:
            return plan

        # 12. Direct URLs ("Open https://...")
        plan = self._parse_direct_url_commands(lower_text, clean_text)
        if plan:
            return plan

        return None

    def _parse_stop_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect cancel, stop scrolling, stop research, and close commands."""
        # Close all research tabs
        if any(p in lower for p in ["close all research tabs", "close research tabs", "close all nova research tabs", "close research"]):
            return BrowserActionPlan(
                action_type=ActionType.CLOSE_RESEARCH_TABS,
                raw_prompt=raw,
            )

        # Stop auto scrolling
        if any(p in lower for p in [
            "stop auto shorts", "stop scrolling", "stop scroll", "stop shorts",
            "stop auto scroll", "stop auto scrolling", "stop auto-scroll",
            "scrolling band karo", "shorts roko", "shorts auto scroll roko"
        ]):
            return BrowserActionPlan(
                action_type=ActionType.STOP_AUTO_SHORTS,
                platform=Platform.YOUTUBE,
                raw_prompt=raw,
            )

        # Pause auto scrolling
        if any(p in lower for p in [
            "pause scrolling", "pause auto scroll", "pause auto-scroll",
            "pause scroll", "pause shorts", "scrolling pause karo", "shorts pause karo",
        ]) or lower == "pause":
            return BrowserActionPlan(
                action_type=ActionType.PAUSE_AUTO_SHORTS,
                platform=Platform.YOUTUBE,
                raw_prompt=raw,
            )

        # Resume auto scrolling
        if any(p in lower for p in [
            "resume scrolling", "resume auto scroll", "resume auto-scroll",
            "resume scroll", "resume shorts", "continue scrolling", "start again",
            "keep scrolling shorts", "scrolling resume karo", "shorts resume karo"
        ]):
            return BrowserActionPlan(
                action_type=ActionType.RESUME_AUTO_SHORTS,
                platform=Platform.YOUTUBE,
                raw_prompt=raw,
            )

        # Stop research / Stop generic
        if lower in ["stop", "cancel", "roko", "band karo"] or any(p in lower for p in ["stop research", "cancel research", "stop search"]):
            return BrowserActionPlan(
                action_type=ActionType.STOP_ACTION,
                raw_prompt=raw,
            )

        # Close tab / Close browser
        if any(p in lower for p in ["close tab", "close browser tab", "close this tab", "tab band karo", "close youtube", "close google"]):
            return BrowserActionPlan(
                action_type=ActionType.CLOSE_TAB,
                raw_prompt=raw,
            )

        return None

    def _parse_navigation_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect tab switching, history navigation, and scrolling."""
        # Tab switching commands
        if lower in ["next tab", "switch to next tab", "agla tab", "next tab pe jao"]:
            return BrowserActionPlan(action_type=ActionType.SWITCH_TAB, query="next", raw_prompt=raw)

        if lower in ["previous tab", "prev tab", "switch to previous tab", "pichhla tab", "go back to the previous tab"]:
            return BrowserActionPlan(action_type=ActionType.SWITCH_TAB, query="previous", raw_prompt=raw)

        # "switch to tab N"
        m_tab_n = re.search(r"^(?:switch\s+to\s+tab\s+|tab\s+)(\d+)$", lower)
        if m_tab_n:
            idx = int(m_tab_n.group(1))
            return BrowserActionPlan(action_type=ActionType.SWITCH_TAB, query="index", target_index=idx, raw_prompt=raw)

        # "switch to [keyword]" / "return to [keyword]" (e.g. "switch to YouTube", "switch to Google")
        m_switch_kw = re.search(r"^(?:switch\s+to|return\s+to|go\s+to\s+tab)\s+(.+)$", lower)
        if m_switch_kw:
            target = m_switch_kw.group(1).strip()
            # If target ends with "tab", trim it
            target = re.sub(r"\s+tab$", "", target).strip()
            if target and target not in ("website", "page", "app"):
                return BrowserActionPlan(action_type=ActionType.SWITCH_TAB, query=target, raw_prompt=raw)

        # History navigation
        if lower in ["go back", "back", "navigate back", "pichhe jao"]:
            return BrowserActionPlan(action_type=ActionType.NAVIGATE_BACK, raw_prompt=raw)

        if lower in ["go forward", "forward", "navigate forward", "aage jao"]:
            return BrowserActionPlan(action_type=ActionType.NAVIGATE_FORWARD, raw_prompt=raw)

        # Scrolling commands
        if any(p in lower for p in ["scroll to top", "scroll top", "top pe jao"]):
            return BrowserActionPlan(action_type=ActionType.SCROLL_PAGE, query="top", raw_prompt=raw)

        if any(p in lower for p in ["scroll to bottom", "scroll bottom", "bottom pe jao"]):
            return BrowserActionPlan(action_type=ActionType.SCROLL_PAGE, query="bottom", raw_prompt=raw)

        if any(p in lower for p in ["scroll down", "scroll page down", "show more", "neeche scroll karo", "scroll karo", "scroll"]):
            return BrowserActionPlan(action_type=ActionType.SCROLL_PAGE, query="down", raw_prompt=raw)

        if any(p in lower for p in ["scroll up", "scroll page up", "upar scroll karo"]):
            return BrowserActionPlan(action_type=ActionType.SCROLL_PAGE, query="up", raw_prompt=raw)

        return None

    def _parse_ordinal_result_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect ordinal selection from search results ('open the second one', 'open the 3rd result')."""
        ordinal_map = {
            "first": 1, "1st": 1, "one": 1,
            "second": 2, "2nd": 2, "two": 2,
            "third": 3, "3rd": 3, "three": 3,
            "fourth": 4, "4th": 4, "four": 4,
            "fifth": 5, "5th": 5, "five": 5,
        }
        for word, idx in ordinal_map.items():
            patterns = [
                rf"^open (?:the )?{word} (?:result|link|one|page|item|video|repository|repo)$",
                rf"^click (?:the )?{word} (?:result|link|one|page|item)$",
                rf"^{word} (?:result|link|one|page) kholo$",
            ]
            for pat in patterns:
                if re.search(pat, lower):
                    return BrowserActionPlan(
                        action_type=ActionType.OPEN_RESULT,
                        target_index=idx,
                        raw_prompt=raw,
                    )
        return None

    def _parse_page_understanding_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect requests to read, explain, or summarize the active webpage or repository."""
        # GitHub specific
        if any(p in lower for p in ["what is this github project", "explain this repository", "explain this repo", "read the readme"]):
            return BrowserActionPlan(
                action_type=ActionType.EXPLAIN_PAGE,
                platform=Platform.GITHUB,
                raw_prompt=raw,
            )

        # What is written on this page / Read page
        if any(p in lower for p in [
            "what is written on this page",
            "what is on this page",
            "read this page",
            "read the page",
            "read this article",
            "read the article",
            "page padho",
            "what is written here",
        ]):
            return BrowserActionPlan(
                action_type=ActionType.READ_PAGE,
                raw_prompt=raw,
            )

        # Summarize
        if any(p in lower for p in ["summarize this article", "summarize this page", "summarize the page", "summarize this", "page summarize karo"]):
            return BrowserActionPlan(
                action_type=ActionType.SUMMARIZE_PAGE,
                raw_prompt=raw,
            )

        # Explain / What is this website about
        if any(p in lower for p in [
            "what is this website about",
            "what is this page about",
            "explain this webpage",
            "explain this page",
            "explain the page",
            "what are the important points",
            "what are the key points",
        ]):
            return BrowserActionPlan(
                action_type=ActionType.EXPLAIN_PAGE,
                raw_prompt=raw,
            )

        return None

    def _parse_comparison_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect product comparison requests."""
        if any(p in lower for p in ["compare these two products", "compare the first two", "which one is better", "compare products"]):
            return BrowserActionPlan(
                action_type=ActionType.COMPARE_PRODUCTS,
                raw_prompt=raw,
            )

        m = re.search(r"^compare (.+?)(?: and | vs | with )(.+)$", lower)
        if m:
            item1 = m.group(1).strip()
            item2 = m.group(2).strip()
            return BrowserActionPlan(
                action_type=ActionType.COMPARE_PRODUCTS,
                query=f"{item1} vs {item2}",
                raw_prompt=raw,
            )

        return None

    def _parse_research_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect deep multi-step research requests."""
        # "Research [topic]"
        m_res = re.search(r"^(?:please\s+)?research\s+(?:the\s+|about\s+)?(.+)$", lower)
        if m_res:
            query = m_res.group(1).strip()
            return BrowserActionPlan(
                action_type=ActionType.RESEARCH_TOPIC,
                query=query,
                raw_prompt=raw,
            )

        # "Find the best [item] under [price]" -> Research
        m_best = re.search(r"^find (?:the )?best (.+? under .+)$", lower)
        if m_best:
            query = f"best {m_best.group(1).strip()}"
            return BrowserActionPlan(
                action_type=ActionType.RESEARCH_TOPIC,
                query=query,
                raw_prompt=raw,
            )

        # "Search multiple websites and show me the best options"
        if "search multiple websites" in lower or "search multiple sources" in lower:
            clean_q = re.sub(r"search multiple websites (?:for |about )?", "", lower).strip()
            return BrowserActionPlan(
                action_type=ActionType.RESEARCH_TOPIC,
                query=clean_q or "best options",
                raw_prompt=raw,
            )

        # "Search for internships for CSE students"
        m_intern = re.search(r"^search for (.+?internships.+)$", lower)
        if m_intern:
            return BrowserActionPlan(
                action_type=ActionType.RESEARCH_TOPIC,
                query=m_intern.group(1).strip(),
                raw_prompt=raw,
            )

        return None

    def _parse_shorts_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect YouTube Shorts watching, auto-scrolling, next, and previous."""
        if lower in ["next short", "next video", "agla short", "next"]:
            return BrowserActionPlan(
                action_type=ActionType.NEXT_ITEM,
                platform=Platform.YOUTUBE,
                raw_prompt=raw,
            )
        if lower in ["previous short", "prev short", "pichhla short", "previous"]:
            return BrowserActionPlan(
                action_type=ActionType.PREVIOUS_ITEM,
                platform=Platform.YOUTUBE,
                raw_prompt=raw,
            )

        auto_patterns = [
            r"^youtube\s+scroll$",
            r"^start\s+auto\s+scroll$",
            r"^start\s+automatic\s+scrolling$",
            r"^auto\s+scroll$",
            r"^scroll\s+shorts(?:\s+automatically)?$",
            r"^automatically\s+scroll\s+shorts$",
            r"^keep\s+scrolling$",
            r"^start\s+scrolling(?:\s+shorts)?$",
            r"^scroll\s+youtube\s+shorts$",
            r"^auto\s+scroll\s+youtube$",
            r"^shorts\s+auto\s+scroll$",
            r"^(?:start\s+)?auto\s+(?:youtube\s+)?shorts",
            r"^watch\s+(?:youtube\s+)?shorts\s+automatically",
            r"^auto\s+scroll\s+shorts",
            r"^(?:watch|play|show)\s+(.+?)\s+shorts\s+automatically",
        ]
        for pat in auto_patterns:
            m = re.search(pat, lower)
            if m:
                query = m.group(1).strip() if m.groups() and m.group(1) else ""
                return BrowserActionPlan(
                    action_type=ActionType.START_AUTO_SHORTS,
                    platform=Platform.YOUTUBE,
                    query=query,
                    auto_navigation=True,
                    raw_prompt=raw,
                )

        shorts_patterns = [
            r"^(?:show\s+(?:me\s+)?|watch\s+|play\s+|open\s+)?(?:youtube\s+)?shorts$",
            r"^(?:show\s+(?:me\s+)?|watch\s+|play\s+)(.+?)\s+shorts$",
            r"^shorts\s+(?:kholo|chalao|dikhao)$",
        ]
        for pat in shorts_patterns:
            m = re.search(pat, lower)
            if m:
                query = m.group(1).strip() if m.groups() and m.group(1) else ""
                if query in ["youtube", "me", "the"]:
                    query = ""
                return BrowserActionPlan(
                    action_type=ActionType.WATCH_SHORTS,
                    platform=Platform.YOUTUBE,
                    query=query,
                    raw_prompt=raw,
                )

        return None

    def _parse_play_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect playback requests ("Play song Mere Liye", "Play Kesariya on YouTube", "I want to watch Motu Patlu")."""
        # "Play [query] on YouTube" or "Play [query]"
        play_match = re.search(
            r"^(?:can you\s+)?(?:please\s+)?play\s+(?:the\s+)?(?:song\s+|video\s+|track\s+)?(.+?)(?:\s+on\s+youtube)?$",
            lower,
        )
        if play_match:
            query = play_match.group(1).strip()
            query = re.sub(r"\s+on\s+youtube$", "", query).strip()
            if query and query not in ("shorts", "video", "song"):
                return BrowserActionPlan(
                    action_type=ActionType.PLAY_MEDIA,
                    platform=Platform.YOUTUBE,
                    query=query,
                    raw_prompt=raw,
                )

        # "I want to watch [query]" / "Watch [query]"
        watch_match = re.search(
            r"^(?:i\s+want\s+to\s+)?watch\s+(?:the\s+)?(?:video\s+|show\s+|episode\s+)?(.+?)(?:\s+on\s+youtube)?$",
            lower,
        )
        if watch_match:
            query = watch_match.group(1).strip()
            query = re.sub(r"\s+on\s+youtube$", "", query).strip()
            if query and query not in ("shorts", "video", "song"):
                return BrowserActionPlan(
                    action_type=ActionType.WATCH_VIDEO,
                    platform=Platform.YOUTUBE,
                    query=query,
                    raw_prompt=raw,
                )

        # Hindi / Hinglish: "[query] gaana chalao", "[query] bhajao", "[query] bajao", "[query] chala do"
        hi_match = re.search(
            r"^(.+?)\s+(?:gaana\s+|song\s+|songs\s+)?(?:bhajao|bajao|baja\s+do|chala\s+do|chalao|song\s+play\s+karo|play\s+karo|youtube\s+par\s+chalao|chalao)$",
            lower,
        )
        if hi_match:
            query = hi_match.group(1).strip()
            query = re.sub(r"^(?:nova\s*[,:]*\s*)", "", query, flags=re.I).strip()
            query = re.sub(r"\s+(?:ke|ka|wala|wali|song|songs|gaana)$", "", query, flags=re.I).strip()
            if query and len(query) > 1 and query.lower() not in ("shorts", "youtube shorts", "search", "youtube search"):
                return BrowserActionPlan(
                    action_type=ActionType.PLAY_MEDIA,
                    platform=Platform.YOUTUBE,
                    query=query,
                    raw_prompt=raw,
                )

        return None

    def _parse_web_search_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect general web search ("Search Google for ...", "Google ...", "Find info about ...")."""
        m_google = re.search(r"^(?:search\s+google\s+for|search\s+on\s+google\s+for|google)\s+(.+)$", lower)
        if m_google:
            query = m_google.group(1).strip()
            return BrowserActionPlan(
                action_type=ActionType.SEARCH_WEB,
                platform=Platform.GOOGLE,
                query=query,
                raw_prompt=raw,
            )

        m_web = re.search(r"^(?:browse\s+(?:the\s+)?(?:internet|web)\s+(?:and\s+)?(?:search\s+for|look\s+up|find)|search\s+(?:the\s+)?(?:internet|web)\s+for|browse\s+(?:the\s+)?(?:internet|web)\s+for|search\s+(?:the\s+)?web\s+for|search\s+for)\s+(.+)$", lower)
        if m_web:
            query = m_web.group(1).strip()
            return BrowserActionPlan(
                action_type=ActionType.SEARCH_WEB,
                platform=Platform.GOOGLE,
                query=query,
                raw_prompt=raw,
            )

        m_info = re.search(r"^(?:find\s+information\s+about|find\s+info\s+about)\s+(.+)$", lower)
        if m_info:
            query = m_info.group(1).strip()
            return BrowserActionPlan(
                action_type=ActionType.SEARCH_WEB,
                platform=Platform.GOOGLE,
                query=query,
                raw_prompt=raw,
            )

        return None

    def _parse_site_search_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect searches on specific sites ("In Flipkart search mobile phones", "Search Amazon for MacBook accessories")."""
        # 1. "In [site] search [query]"
        m_in_search = re.search(r"^in\s+([a-zA-Z0-9_\-\.]+)\s+search\s+(?:for\s+)?(.+)$", lower)
        if m_in_search:
            site = m_in_search.group(1).strip()
            q = m_in_search.group(2).strip()
            platform_enum = getattr(Platform, site.upper(), Platform.GENERIC)
            return BrowserActionPlan(
                action_type=ActionType.SEARCH_SITE,
                platform=platform_enum,
                query=q,
                metadata={"site_key": site},
                raw_prompt=raw,
            )

        # 2. "Search [query] in [site]"
        m_search_in = re.search(r"^(?:search|find)\s+(.+?)\s+in\s+([a-zA-Z0-9_\-\.]+)$", lower)
        if m_search_in:
            q = m_search_in.group(1).strip()
            site = m_search_in.group(2).strip()
            platform_enum = getattr(Platform, site.upper(), Platform.GENERIC)
            return BrowserActionPlan(
                action_type=ActionType.SEARCH_SITE,
                platform=platform_enum,
                query=q,
                metadata={"site_key": site},
                raw_prompt=raw,
            )

        # 3. "Search [query] here" / "Search [query] on this site"
        m_here = re.search(r"^(?:search|find)\s+(?:for\s+)?(.+?)\s+(?:here|on\s+this\s+site|on\s+this\s+page)$", lower)
        if m_here:
            q = m_here.group(1).strip()
            from core.environment import environment_observer
            ctx = environment_observer.get_context()
            domain = ctx.current_domain or "google.com"
            site_key = domain.replace("www.", "").split(".")[0]
            platform_enum = getattr(Platform, site_key.upper(), Platform.GENERIC)
            return BrowserActionPlan(
                action_type=ActionType.SEARCH_SITE,
                platform=platform_enum,
                query=q,
                metadata={"site_key": site_key, "is_current_site": True},
                raw_prompt=raw,
            )

        # 4. "Search YouTube for [query]"
        m_yt_search = re.search(r"^search\s+youtube\s+for\s+(.+)$", lower)
        if m_yt_search:
            q = m_yt_search.group(1).strip()
            return BrowserActionPlan(
                action_type=ActionType.SEARCH_SITE,
                platform=Platform.YOUTUBE,
                query=q,
                metadata={"site_key": "youtube"},
                raw_prompt=raw,
            )

        # 5. "Go to Flipkart and search for mobile phones" / "Open Amazon and find [query]"
        m_goto_and = re.search(r"^(?:go\s+to|open|visit|navigate\s+to)\s+(?:the\s+)?([a-zA-Z0-9_\-\.]+?)(?:\s+website|\s+site|\s+webpage)?\s+and\s+(?:search\s+for|search|find|look\s+for)\s+(.+)$", lower)
        if m_goto_and:
            site = m_goto_and.group(1).strip()
            q = m_goto_and.group(2).strip()
            platform_enum = getattr(Platform, site.upper(), Platform.GENERIC)
            return BrowserActionPlan(
                action_type=ActionType.SEARCH_SITE,
                platform=platform_enum,
                query=q,
                metadata={"site_key": site},
                raw_prompt=raw,
            )

        pattern = r"^(?:search\s+|find\s+)(.+?)\s+(?:for|on)\s+(.+)$"
        m = re.search(pattern, lower)
        if m:
            first_part = m.group(1).strip()
            second_part = m.group(2).strip()

            if first_part.lower() == "google":
                return BrowserActionPlan(
                    action_type=ActionType.SEARCH_WEB,
                    platform=Platform.GOOGLE,
                    query=second_part,
                    raw_prompt=raw,
                )

            if first_part in TRUSTED_SITES or first_part in [p.value for p in Platform]:
                platform_enum = getattr(Platform, first_part.upper(), Platform.GENERIC)
                return BrowserActionPlan(
                    action_type=ActionType.SEARCH_SITE,
                    platform=platform_enum,
                    query=second_part,
                    metadata={"site_key": first_part},
                    raw_prompt=raw,
                )

            site_candidate = second_part.strip()
            if site_candidate in TRUSTED_SITES or site_candidate in [p.value for p in Platform]:
                actual_query = re.sub(r"^for\s+", "", first_part).strip()
                platform_enum = getattr(Platform, site_candidate.upper(), Platform.GENERIC)
                return BrowserActionPlan(
                    action_type=ActionType.SEARCH_SITE,
                    platform=platform_enum,
                    query=actual_query,
                    metadata={"site_key": site_candidate},
                    raw_prompt=raw,
                )

        return None

    def _parse_open_site_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect requests to open a specific website, official organization website, or entity."""
        # 1. "Open [entity] website", "Find the [entity] website", "Open official website of [entity]"
        m_site_entity = re.search(r"^(?:open|find|launch|go\s+to)\s+(?:the\s+)?(?:official\s+)?(?:website\s+of\s+)?(.+?)(?:\s+website|\s+site)?$", lower)
        if m_site_entity:
            entity = m_site_entity.group(1).strip()
            entity = re.sub(r"^(?:the\s+)?(?:official\s+)?(?:website\s+of\s+)?", "", entity).strip()
            entity = re.sub(r"\s+website$", "", entity).strip()

            if entity:
                # Check if known in TRUSTED_SITES
                if entity in TRUSTED_SITES:
                    platform_key = entity.split()[0].upper()
                    platform_enum = getattr(Platform, platform_key, Platform.GENERIC)
                    return BrowserActionPlan(
                        action_type=ActionType.OPEN_SITE,
                        platform=platform_enum,
                        metadata={"site_key": entity},
                        raw_prompt=raw,
                    )
                # Arbitrary entity website discovery (e.g. "Mirai School of Technology", "OpenAI", "AKTU")
                return BrowserActionPlan(
                    action_type=ActionType.OPEN_SITE,
                    platform=Platform.GENERIC,
                    metadata={"site_key": entity},
                    raw_prompt=raw,
                )

        # 2. Hindi: "[site] kholo" / "[site] open karo"
        m_hi = re.search(r"^(.+?)\s+(?:kholo|open\s+karo)$", lower)
        if m_hi:
            site_target = m_hi.group(1).strip()
            platform_key = site_target.split()[0].upper()
            platform_enum = getattr(Platform, platform_key, Platform.GENERIC)
            return BrowserActionPlan(
                action_type=ActionType.OPEN_SITE,
                platform=platform_enum,
                metadata={"site_key": site_target},
                raw_prompt=raw,
            )

        return None

    def _parse_direct_url_commands(self, lower: str, raw: str) -> BrowserActionPlan | None:
        """Detect raw URLs."""
        if lower.startswith("http://") or lower.startswith("https://") or lower.startswith("www."):
            return BrowserActionPlan(
                action_type=ActionType.OPEN_SITE,
                target_url=raw.strip(),
                raw_prompt=raw,
            )
        return None
