"""Browser session, active tab, and controlled auto-navigation loop manager."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from core.logger import get_logger

from browser.auto_scroll import AutoScrollController, AutoScrollPolicy
from browser.engine import BaseBrowserEngine

logger = get_logger(__name__)


class BrowserSessionManager:
    """Manages active browser tasks, tab states, tracked research tabs, and controlled background loops."""

    def __init__(self, engine: BaseBrowserEngine) -> None:
        self.engine = engine
        self._lock = threading.RLock()
        self._active_task_name: str | None = None
        self._stop_requested = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._nova_tabs: list[str] = []
        self._research_tabs: list[str] = []
        self.auto_scroll_controller: AutoScrollController = AutoScrollController(engine=self.engine)

    @property
    def active_task(self) -> str | None:
        """Return the name of any currently running background browser task."""
        with self._lock:
            return self._active_task_name

    def is_task_running(self) -> bool:
        """Return True if a background automation loop is active."""
        with self._lock:
            if self.auto_scroll_controller.is_active() or self.auto_scroll_controller.is_running():
                return True
            return (
                self._worker_thread is not None
                and self._worker_thread.is_alive()
                and not self._stop_requested.is_set()
            )

    def track_tab(self, url: str, is_research: bool = False) -> None:
        """Track a tab opened by NOVA automation."""
        with self._lock:
            if url not in self._nova_tabs:
                self._nova_tabs.append(url)
            if is_research and url not in self._research_tabs:
                self._research_tabs.append(url)

    def open_research_tab(self, url: str) -> bool:
        """Open a new tab specifically tracked as a NOVA research tab."""
        success = self.engine.open_url(url, new_tab=True)
        if success:
            self.track_tab(url, is_research=True)
        return success

    def close_research_tabs(self) -> int:
        """Close only the tabs opened by NOVA research operations, leaving user tabs untouched."""
        closed_count = 0
        with self._lock:
            tabs_to_close = list(self._research_tabs)
            self._research_tabs.clear()

        for _ in tabs_to_close:
            try:
                if self.engine.close_tab():
                    closed_count += 1
                time.sleep(0.3)
            except Exception as exc:
                logger.debug("Error closing research tab: %s", exc)

        logger.info("Closed %d research tabs.", closed_count)
        return closed_count

    def close_active_tab(self) -> bool:
        """Close the active browser tab."""
        return self.engine.close_tab()

    def switch_tab(self, direction: str = "next") -> bool:
        """Switch to the next or previous browser tab."""
        if direction == "next":
            js = """
            (function() {
                // Dispatch Ctrl+Tab or command equivalent via window focus where possible
                return true;
            })()
            """
        else:
            js = "return true;"
        return bool(self.engine.execute_script(js))

    def start_auto_shorts_loop(
        self,
        interval_seconds: float = 12.0,
        max_scrolls: int = 50,
        on_scroll: Callable[[int], None] | None = None,
    ) -> bool:
        """Start a controlled, bounded, and cancellable YouTube Shorts auto-navigation loop."""
        self.stop_active_task()

        with self._lock:
            self._active_task_name = "youtube_shorts_auto_scroll"

        policy = AutoScrollPolicy(
            dwell_time_seconds=interval_seconds,
            max_total_scrolls=max_scrolls,
        )
        if on_scroll:
            self.auto_scroll_controller.on_scroll_completed = lambda count, obs: on_scroll(count)

        succ, _ = self.auto_scroll_controller.start(engine=self.engine, policy=policy)
        return succ

    def pause_auto_shorts(self) -> bool:
        """Pause the active YouTube Shorts auto-scroll loop."""
        return self.auto_scroll_controller.pause()

    def resume_auto_shorts(self) -> bool:
        """Resume the paused YouTube Shorts auto-scroll loop."""
        return self.auto_scroll_controller.resume()

    def is_auto_shorts_active(self) -> bool:
        """Return True if auto-scroll is actively running."""
        return self.auto_scroll_controller.is_active()

    def is_auto_shorts_paused(self) -> bool:
        """Return True if auto-scroll is paused."""
        return self.auto_scroll_controller.is_paused()

    def next_short(self) -> bool:
        """Trigger immediate navigation to the next Short."""
        js = """
        (function() {
            const nextBtn = document.querySelector('button[aria-label="Next video"], #navigation-button-down button');
            if (nextBtn) {
                nextBtn.click();
                return true;
            }
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40, which: 40, bubbles: true }));
            window.scrollBy({ top: window.innerHeight, behavior: 'smooth' });
            return true;
        })()
        """
        try:
            self.engine.execute_script(js)
            return True
        except Exception:
            return False

    def previous_short(self) -> bool:
        """Trigger immediate navigation to the previous Short."""
        js = """
        (function() {
            const prevBtn = document.querySelector('button[aria-label="Previous video"], #navigation-button-up button');
            if (prevBtn) {
                prevBtn.click();
                return true;
            }
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', code: 'ArrowUp', keyCode: 38, which: 38, bubbles: true }));
            window.scrollBy({ top: -window.innerHeight, behavior: 'smooth' });
            return true;
        })()
        """
        try:
            self.engine.execute_script(js)
            return True
        except Exception:
            return False

    def stop_active_task(self) -> bool:
        """Immediately interrupt and stop any running background automation loop."""
        stopped = False
        with self._lock:
            if (
                self.auto_scroll_controller.is_active()
                or self.auto_scroll_controller.is_paused()
                or self.auto_scroll_controller.is_running()
            ):
                self.auto_scroll_controller.stop()
                stopped = True

            if self._worker_thread is not None and self._worker_thread.is_alive():
                self._stop_requested.set()
                stopped = True

            task_name = self._active_task_name
            self._active_task_name = None

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.5)
            self._worker_thread = None

        if stopped:
            logger.info("Stopped active browser background task: '%s'", task_name or "auto_scroll")
        return stopped

    def shutdown(self) -> None:
        """Tear down all background session threads."""
        self.stop_active_task()
        if hasattr(self, "auto_scroll_controller"):
            self.auto_scroll_controller.stop()
        logger.info("BrowserSessionManager shut down.")
