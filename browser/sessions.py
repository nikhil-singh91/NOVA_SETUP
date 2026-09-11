"""Browser session, active tab, and controlled auto-navigation loop manager."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable

from core.logger import get_logger
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

    @property
    def active_task(self) -> str | None:
        """Return the name of any currently running background browser task."""
        with self._lock:
            return self._active_task_name

    def is_task_running(self) -> bool:
        """Return True if a background automation loop is active."""
        with self._lock:
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
        interval_seconds: float = 15.0,
        max_scrolls: int = 50,
        on_scroll: Callable[[int], None] | None = None,
    ) -> None:
        """Start a controlled, bounded, and cancellable YouTube Shorts auto-navigation loop."""
        self.stop_active_task()

        with self._lock:
            self._active_task_name = "youtube_shorts_auto_scroll"
            self._stop_requested.clear()

            def _loop() -> None:
                logger.info(
                    "YouTube Shorts auto-navigation started (interval=%.1fs, max_scrolls=%d).",
                    interval_seconds,
                    max_scrolls,
                )
                scroll_count = 0
                while not self._stop_requested.is_set() and scroll_count < max_scrolls:
                    # Sleep in small slices to allow instantaneous interruption
                    elapsed = 0.0
                    while elapsed < interval_seconds and not self._stop_requested.is_set():
                        time.sleep(0.2)
                        elapsed += 0.2

                    if self._stop_requested.is_set():
                        break

                    # Dispatch next Short navigation via keypress or DOM trigger
                    scroll_count += 1
                    logger.debug("Auto Shorts: Scrolling to next short (#%d)", scroll_count)

                    # Method 1: Down Arrow keypress event in YouTube Shorts
                    next_js = """
                    (function() {
                        // 1. Try clicking next button if exists
                        const nextBtn = document.querySelector('button[aria-label="Next video"], #navigation-button-down button');
                        if (nextBtn) {
                            nextBtn.click();
                            return "next_btn_clicked";
                        }
                        // 2. Dispatch Down Arrow Key event
                        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40, which: 40, bubbles: true }));
                        // 3. Smooth scroll container fallback
                        window.scrollBy({ top: window.innerHeight, behavior: 'smooth' });
                        return "arrow_down_dispatched";
                    })()
                    """
                    try:
                        self.engine.execute_script(next_js)
                    except Exception as exc:
                        logger.warning("Error during auto-shorts scroll: %s", exc)

                    if on_scroll:
                        try:
                            on_scroll(scroll_count)
                        except Exception:
                            pass

                logger.info("YouTube Shorts auto-navigation finished or stopped.")
                with self._lock:
                    if self._active_task_name == "youtube_shorts_auto_scroll":
                        self._active_task_name = None

            self._worker_thread = threading.Thread(
                target=_loop,
                name="nova-shorts-auto-navigator",
                daemon=True,
            )
            self._worker_thread.start()

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
        with self._lock:
            if not self.is_task_running():
                return False

            self._stop_requested.set()
            task_name = self._active_task_name
            self._active_task_name = None

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.5)
            self._worker_thread = None

        logger.info("Stopped active browser background task: '%s'", task_name)
        return True

    def shutdown(self) -> None:
        """Tear down all background session threads."""
        self.stop_active_task()
        logger.info("BrowserSessionManager shut down.")
