"""Short-term browser context, recent pages, search results, and ordinal resolution."""

from __future__ import annotations

import threading

from core.logger import get_logger

from browser.models import BrowserContext, BrowserTaskPlan, PageContent, SearchResultItem

logger = get_logger(__name__)


class BrowserContextManager:
    """Thread-safe manager for short-term browser context, search history, and ordinal references."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._context = BrowserContext()

    def get_context(self) -> BrowserContext:
        """Return a snapshot of current browser context."""
        with self._lock:
            return self._context

    def set_search_results(self, query: str, results: list[dict[str, str]]) -> None:
        """Store structured search results to allow ordinal follow-up ('open the second one')."""
        with self._lock:
            self._context.last_search_query = query
            self._context.last_search_results = [
                SearchResultItem(
                    index=i + 1,
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                )
                for i, item in enumerate(results)
            ]
            logger.debug(
                "Stored %d search results in BrowserContext for query '%s'.",
                len(self._context.last_search_results),
                query,
            )

    def get_result_by_index(self, index: int) -> SearchResultItem | None:
        """Retrieve a specific search result by 1-indexed number (e.g. 1 for first, 2 for second)."""
        with self._lock:
            for item in self._context.last_search_results:
                if item.index == index:
                    return item
            # Fallback 0-indexed lookup if within bounds
            if 0 <= index - 1 < len(self._context.last_search_results):
                return self._context.last_search_results[index - 1]
            return None

    def set_active_page(self, page: PageContent) -> None:
        """Record the active page content and prepend to recent pages."""
        with self._lock:
            self._context.active_page = page
            # Keep up to 5 recent pages
            self._context.recent_pages.insert(0, page)
            self._context.recent_pages = self._context.recent_pages[:5]

    def add_research_tab(self, url: str) -> None:
        """Track a tab created as part of NOVA research operations."""
        with self._lock:
            if url not in self._context.research_tabs:
                self._context.research_tabs.append(url)

    def remove_research_tab(self, url: str) -> None:
        """Remove a tracked research tab."""
        with self._lock:
            if url in self._context.research_tabs:
                self._context.research_tabs.remove(url)

    def get_research_tabs(self) -> list[str]:
        """Return all tracked research tab URLs."""
        with self._lock:
            return list(self._context.research_tabs)

    def clear_research_tabs(self) -> None:
        """Clear list of tracked research tabs."""
        with self._lock:
            self._context.research_tabs.clear()

    def set_current_task(self, task: BrowserTaskPlan | None) -> None:
        """Set or clear active multi-step task plan."""
        with self._lock:
            self._context.current_task = task

    def reset(self) -> None:
        """Reset short-term context."""
        with self._lock:
            self._context = BrowserContext()
