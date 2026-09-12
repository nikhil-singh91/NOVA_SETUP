"""Browser automation abstraction and reliable macOS native implementation for NOVA."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Any

from config.settings import settings
from core.logger import get_logger
from browser.models import BrowserError, BrowserLaunchError, BrowserNotFoundError, NavigationError, PageContent

logger = get_logger(__name__)


def log_browser_diagnostics(action: str, result: str, url: str = "", title: str = "", tab_idx: int | None = None, extra: str = "") -> None:
    """Helper to output structured browser diagnostics when debug mode is active."""
    is_debug = bool(settings.nova_browser_debug or os.getenv("NOVA_BROWSER_DEBUG", "").lower() in ("true", "1"))
    if not is_debug:
        return

    print("========================================")
    print("🔍 [BROWSER DIAGNOSTICS]")
    print(f"Action:         {action}")
    if tab_idx is not None:
        print(f"Active Tab:     {tab_idx}")
    if title:
        print(f"Page Title:     {title[:60]}")
    if url:
        print(f"URL:            {url[:70]}")
    print(f"Action Result:  {result}")
    if extra:
        print(f"Details:        {extra[:120]}")
    print("========================================")


class BaseBrowserEngine(ABC):
    """Abstract interface for browser automation backends."""

    @property
    @abstractmethod
    def browser_name(self) -> str:
        """Return the active browser name."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize engine resources or browser instance."""

    @abstractmethod
    def open_url(self, url: str, new_tab: bool = False) -> bool:
        """Navigate to a URL."""

    @abstractmethod
    def click(self, selector: str) -> bool:
        """Click an element matching a CSS selector."""

    @abstractmethod
    def type_text(self, selector: str, text: str) -> bool:
        """Type text into an input element."""

    @abstractmethod
    def wait_for(self, selector: str, timeout_seconds: float = 5.0) -> bool:
        """Wait until an element matching the CSS selector is present in DOM."""

    @abstractmethod
    def execute_script(self, script: str) -> Any:
        """Execute a JavaScript snippet in the active page."""

    @abstractmethod
    def get_page_info(self) -> dict[str, str]:
        """Return title and URL of the active tab."""

    @abstractmethod
    def refresh_browser_state(self) -> dict[str, Any]:
        """Query real-time frontmost browser window, active tab index, title, and URL."""

    @abstractmethod
    def get_active_tab_index(self) -> int:
        """Return the 1-indexed active tab index."""

    @abstractmethod
    def set_active_tab_index(self, index: int) -> bool:
        """Switch front window to the given 1-indexed tab."""

    @abstractmethod
    def get_tab_count(self) -> int:
        """Return total number of tabs open in front window."""

    @abstractmethod
    def list_tabs(self) -> list[dict[str, Any]]:
        """Return list of open tabs with index, title, and URL."""

    @abstractmethod
    def next_tab(self) -> tuple[bool, int, str]:
        """Switch to next tab in front window. Returns (success, new_index, new_title)."""

    @abstractmethod
    def previous_tab(self) -> tuple[bool, int, str]:
        """Switch to previous tab in front window. Returns (success, new_index, new_title)."""

    @abstractmethod
    def switch_to_tab_by_title_or_url(self, query: str) -> tuple[bool, int, str]:
        """Switch to tab matching title or URL keyword. Returns (success, new_index, new_title)."""

    @abstractmethod
    def close_tab(self) -> bool:
        """Close the currently active tab."""

    @abstractmethod
    def navigate_back(self) -> bool:
        """Go back in browser history."""

    @abstractmethod
    def navigate_forward(self) -> bool:
        """Go forward in browser history."""

    @abstractmethod
    def scroll_page(self, direction: str = "down", amount: str | int = "medium") -> bool:
        """Scroll the active page up or down."""

    @abstractmethod
    def scroll_to_top(self) -> bool:
        """Scroll active tab to top of page."""

    @abstractmethod
    def scroll_to_bottom(self) -> bool:
        """Scroll active tab to bottom of page."""

    @abstractmethod
    def extract_page_content(self) -> PageContent:
        """Extract readable sanitized text and headings from active page."""

    @abstractmethod
    def extract_search_results(self, limit: int = 5) -> list[dict[str, str]]:
        """Extract organic search results from active search results page."""

    def open_new_tab(self, url: str = "chrome://newtab/") -> tuple[bool, int, str, str]:
        """Open a new tab and return (success, tab_index, title, url)."""
        succ = self.open_url(url, new_tab=True)
        st = self.refresh_browser_state()
        return succ, st.get("active_tab", 1), st.get("title", ""), st.get("url", url)

    def search_current_tab(self, query: str) -> tuple[bool, int, str, str]:
        """Search query directly in the current frontmost tab and return (success, tab_index, title, url)."""
        import urllib.parse
        st = self.refresh_browser_state()
        cur_url = st.get("url", "").lower()
        encoded = urllib.parse.quote_plus(query)
        if "flipkart.com" in cur_url:
            search_url = f"https://www.flipkart.com/search?q={encoded}"
        elif "amazon" in cur_url:
            search_url = f"https://www.amazon.in/s?k={encoded}"
        elif "youtube.com" in cur_url:
            search_url = f"https://www.youtube.com/results?search_query={encoded}"
        else:
            search_url = f"https://www.google.com/search?q={encoded}"
        succ = self.open_url(search_url, new_tab=False)
        time.sleep(0.3)
        nst = self.refresh_browser_state()
        return succ, nst.get("active_tab", 1), nst.get("title", ""), nst.get("url", search_url)

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanly close automation sessions."""


class MacOSNativeBrowserEngine(BaseBrowserEngine):
    """Native macOS browser automation engine using AppleScript and Quartz events.

    Controls Google Chrome, Safari, Brave, Microsoft Edge, and Arc natively on macOS.
    Operates without requiring developer menu toggles or separate webdriver binaries.
    """

    def __init__(self, browser: str | None = None) -> None:
        self.requested_browser = (browser or settings.default_browser or "chrome").lower()
        self._app_name = self._resolve_app_name(self.requested_browser)
        self._is_initialized = False

    @property
    def browser_name(self) -> str:
        return self._app_name

    def _resolve_app_name(self, name: str) -> str:
        """Map generic browser names to macOS Application names."""
        mapping = {
            "chrome": "Google Chrome",
            "google chrome": "Google Chrome",
            "safari": "Safari",
            "brave": "Brave Browser",
            "edge": "Microsoft Edge",
            "arc": "Arc",
        }
        return mapping.get(name.lower(), "Google Chrome")

    def initialize(self) -> None:
        """Verify that the browser is installed on macOS."""
        if self._is_initialized:
            return

        script = f'id of application "{self._app_name}"'
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            if proc.returncode != 0:
                if self._app_name != "Safari":
                    logger.warning(
                        "Browser '%s' not found. Falling back to Safari.", self._app_name
                    )
                    self._app_name = "Safari"
                else:
                    raise BrowserNotFoundError(f"Browser application '{self._app_name}' not found on macOS.")
        except subprocess.TimeoutExpired:
            logger.warning("Browser check timed out. Proceeding with %s.", self._app_name)

        self._is_initialized = True
        logger.info("MacOSNativeBrowserEngine initialized with '%s'.", self._app_name)

    def _run_applescript(self, script: str, timeout: float = 8.0) -> tuple[bool, str]:
        """Execute an AppleScript command and return (success, output)."""
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode == 0:
                return True, proc.stdout.strip()
            else:
                return False, proc.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "AppleScript execution timed out."
        except Exception as exc:
            return False, str(exc)

    def open_url(self, url: str, new_tab: bool = False) -> bool:
        """Open or navigate to a URL in the frontmost browser window."""
        if not self._is_initialized:
            self.initialize()

        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://") and not clean_url.startswith("chrome://"):
            clean_url = f"https://{clean_url}"

        logger.info("Opening URL in %s: %s (new_tab=%s)", self._app_name, clean_url, new_tab)

        if "Chrome" in self._app_name or "Brave" in self._app_name or "Edge" in self._app_name:
            if new_tab:
                script = f'''
                tell application "{self._app_name}"
                    activate
                    if (count of windows) = 0 then
                        make new window
                        set URL of active tab of front window to "{clean_url}"
                    else
                        tell front window to make new tab with properties {{URL:"{clean_url}"}}
                    end if
                end tell
                '''
            else:
                script = f'''
                tell application "{self._app_name}"
                    activate
                    if (count of windows) = 0 then
                        make new window
                        set URL of active tab of front window to "{clean_url}"
                    else
                        set URL of active tab of front window to "{clean_url}"
                    end if
                end tell
                '''
        elif "Safari" in self._app_name:
            if new_tab:
                script = f'''
                tell application "Safari"
                    activate
                    if (count of windows) = 0 then
                        make new document with properties {{URL:"{clean_url}"}}
                    else
                        tell front window
                            set current tab to (make new tab with properties {{URL:"{clean_url}"}})
                        end tell
                    end if
                end tell
                '''
            else:
                script = f'''
                tell application "Safari"
                    activate
                    if (count of windows) = 0 then
                        make new document with properties {{URL:"{clean_url}"}}
                    else
                        set URL of current tab of front window to "{clean_url}"
                    end if
                end tell
                '''
        else:
            try:
                subprocess.Popen(["open", "-a", self._app_name, clean_url])
                return True
            except Exception as exc:
                raise NavigationError(f"Failed to open URL: {exc}") from exc

        success, err = self._run_applescript(script)
        log_browser_diagnostics(
            action="OPEN_URL",
            result="SUCCESS" if success else f"FAILED: {err}",
            url=clean_url,
        )
        return success

    def refresh_browser_state(self) -> dict[str, Any]:
        """Query real-time frontmost browser window, active tab index, title, and URL."""
        if "Chrome" in self._app_name or "Brave" in self._app_name or "Edge" in self._app_name:
            script = f'''
            tell application "{self._app_name}"
                if (count of windows) > 0 then
                    set curIdx to active tab index of front window
                    set totalTabs to count of tabs of front window
                    set curTitle to title of active tab of front window
                    set curURL to URL of active tab of front window
                    return (curIdx as text) & "|||" & (totalTabs as text) & "|||" & curTitle & "|||" & curURL
                end if
                return "NO_WINDOW"
            end tell
            '''
        elif "Safari" in self._app_name:
            script = f'''
            tell application "Safari"
                if (count of windows) > 0 then
                    set curIdx to index of current tab of front window
                    set totalTabs to count of tabs of front window
                    set curTitle to name of current tab of front window
                    set curURL to URL of current tab of front window
                    return (curIdx as text) & "|||" & (totalTabs as text) & "|||" & curTitle & "|||" & curURL
                end if
                return "NO_WINDOW"
            end tell
            '''
        else:
            return {"active_tab": 1, "total_tabs": 1, "title": "", "url": ""}

        success, out = self._run_applescript(script)
        if success and "|||" in out:
            parts = out.split("|||", 3)
            try:
                idx = int(parts[0])
            except ValueError:
                idx = 1
            try:
                total = int(parts[1])
            except ValueError:
                total = 1
            return {
                "active_tab": idx,
                "total_tabs": total,
                "title": parts[2].strip(),
                "url": parts[3].strip() if len(parts) > 3 else "",
            }
        return {"active_tab": 1, "total_tabs": 1, "title": "", "url": ""}

    def get_page_info(self) -> dict[str, str]:
        """Query active tab title and URL."""
        state = self.refresh_browser_state()
        return {"title": state.get("title", ""), "url": state.get("url", "")}

    def get_active_tab_index(self) -> int:
        """Return the active tab index (1-indexed)."""
        state = self.refresh_browser_state()
        return state.get("active_tab", 1)

    def set_active_tab_index(self, index: int) -> bool:
        """Switch front window to the given 1-indexed tab."""
        if index < 1:
            return False
        if "Chrome" in self._app_name or "Brave" in self._app_name or "Edge" in self._app_name:
            script = f'''
            tell application "{self._app_name}"
                activate
                if (count of windows) > 0 then
                    set active tab index of front window to {index}
                    return "switched"
                end if
            end tell
            '''
        elif "Safari" in self._app_name:
            script = f'''
            tell application "Safari"
                activate
                if (count of windows) > 0 then
                    set current tab of front window to tab {index} of front window
                    return "switched"
                end if
            end tell
            '''
        else:
            return False

        success, _ = self._run_applescript(script)
        return success

    def get_tab_count(self) -> int:
        """Return total number of tabs open in front window."""
        state = self.refresh_browser_state()
        return state.get("total_tabs", 1)

    def list_tabs(self) -> list[dict[str, Any]]:
        """Return list of open tabs with index, title, and URL."""
        if "Chrome" in self._app_name or "Brave" in self._app_name or "Edge" in self._app_name:
            script = f'''
            tell application "{self._app_name}"
                if (count of windows) > 0 then
                    set outList to {{}}
                    set totalTabs to count of tabs of front window
                    repeat with i from 1 to totalTabs
                        set tTitle to title of tab i of front window
                        set tURL to URL of tab i of front window
                        set end of outList to (i as text) & "::" & tTitle & "::" & tURL
                    end repeat
                    set AppleScript's text item delimiters to "|||"
                    return outList as text
                end if
                return ""
            end tell
            '''
        elif "Safari" in self._app_name:
            script = f'''
            tell application "Safari"
                if (count of windows) > 0 then
                    set outList to {{}}
                    set totalTabs to count of tabs of front window
                    repeat with i from 1 to totalTabs
                        set tTitle to name of tab i of front window
                        set tURL to URL of tab i of front window
                        set end of outList to (i as text) & "::" & tTitle & "::" & tURL
                    end repeat
                    set AppleScript's text item delimiters to "|||"
                    return outList as text
                end if
                return ""
            end tell
            '''
        else:
            return []

        success, out = self._run_applescript(script)
        tabs: list[dict[str, Any]] = []
        if success and out:
            items = out.split("|||")
            for item in items:
                parts = item.split("::", 2)
                if len(parts) >= 2:
                    try:
                        idx = int(parts[0])
                    except ValueError:
                        idx = len(tabs) + 1
                    tabs.append({
                        "index": idx,
                        "title": parts[1].strip(),
                        "url": parts[2].strip() if len(parts) > 2 else "",
                    })
        return tabs

    def next_tab(self) -> tuple[bool, int, str]:
        """Switch to the next tab in the frontmost browser window."""
        state = self.refresh_browser_state()
        cur_idx = state.get("active_tab", 1)
        total = state.get("total_tabs", 1)
        next_idx = cur_idx + 1 if cur_idx < total else 1

        success = self.set_active_tab_index(next_idx)
        time.sleep(0.2)
        new_state = self.refresh_browser_state()
        new_title = new_state.get("title", "")
        log_browser_diagnostics("NEXT_TAB", "SUCCESS" if success else "FAILED", tab_idx=next_idx, title=new_title)
        return success, next_idx, new_title

    def previous_tab(self) -> tuple[bool, int, str]:
        """Switch to the previous tab in the frontmost browser window."""
        state = self.refresh_browser_state()
        cur_idx = state.get("active_tab", 1)
        total = state.get("total_tabs", 1)
        prev_idx = cur_idx - 1 if cur_idx > 1 else total

        success = self.set_active_tab_index(prev_idx)
        time.sleep(0.2)
        new_state = self.refresh_browser_state()
        new_title = new_state.get("title", "")
        log_browser_diagnostics("PREV_TAB", "SUCCESS" if success else "FAILED", tab_idx=prev_idx, title=new_title)
        return success, prev_idx, new_title

    def switch_to_tab_by_title_or_url(self, query: str) -> tuple[bool, int, str]:
        """Search open tabs by keyword in title/URL and switch front window to it."""
        clean_q = query.lower().strip()
        tabs = self.list_tabs()

        for tab in tabs:
            title_l = tab.get("title", "").lower()
            url_l = tab.get("url", "").lower()
            if clean_q in title_l or clean_q in url_l:
                idx = tab.get("index", 1)
                success = self.set_active_tab_index(idx)
                time.sleep(0.2)
                new_state = self.refresh_browser_state()
                log_browser_diagnostics("SWITCH_TAB", "SUCCESS" if success else "FAILED", tab_idx=idx, title=tab["title"])
                return success, idx, tab["title"]

        log_browser_diagnostics("SWITCH_TAB", "NOT_FOUND", extra=f"Query '{query}' not in open tabs")
        return False, 0, ""

    def close_tab(self) -> bool:
        """Close the active tab in frontmost window."""
        if "Chrome" in self._app_name or "Brave" in self._app_name or "Edge" in self._app_name:
            script = f'''
            tell application "{self._app_name}"
                if (count of windows) > 0 then
                    close active tab of front window
                    return "closed"
                end if
            end tell
            '''
        elif "Safari" in self._app_name:
            script = f'''
            tell application "Safari"
                if (count of windows) > 0 then
                    close current tab of front window
                    return "closed"
                end if
            end tell
            '''
        else:
            return False

        success, _ = self._run_applescript(script)
        log_browser_diagnostics("CLOSE_TAB", "SUCCESS" if success else "FAILED")
        return success

    def navigate_back(self) -> bool:
        """Go back in browser history."""
        js = "window.history.back(); return 'back';"
        res = self.execute_script(js)
        log_browser_diagnostics("NAVIGATE_BACK", "SUCCESS")
        return True

    def navigate_forward(self) -> bool:
        """Go forward in browser history."""
        js = "window.history.forward(); return 'forward';"
        res = self.execute_script(js)
        log_browser_diagnostics("NAVIGATE_FORWARD", "SUCCESS")
        return True

    def open_new_tab(self, url: str = "chrome://newtab/") -> tuple[bool, int, str, str]:
        """Open a dedicated new browser tab and return verified tab state."""
        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://") and not clean_url.startswith("chrome://"):
            clean_url = f"https://{clean_url}"

        logger.info("Opening new tab in %s: %s", self._app_name, clean_url)
        success = self.open_url(clean_url, new_tab=True)
        time.sleep(0.3)
        state = self.refresh_browser_state()
        idx = state.get("active_tab", 1)
        title = state.get("title", "New Tab")
        cur_url = state.get("url", clean_url)
        log_browser_diagnostics("OPEN_NEW_TAB", "SUCCESS" if success else "FAILED", tab_idx=idx, title=title, url=cur_url)
        return success, idx, title, cur_url

    def search_current_tab(self, query: str) -> tuple[bool, int, str, str]:
        """Search for a query directly inside the active browser tab without opening a new tab."""
        import urllib.parse
        state = self.refresh_browser_state()
        cur_url = (state.get("url") or "").lower()
        encoded = urllib.parse.quote_plus(query.strip())

        if "flipkart.com" in cur_url:
            search_url = f"https://www.flipkart.com/search?q={encoded}"
        elif "amazon" in cur_url:
            search_url = f"https://www.amazon.in/s?k={encoded}"
        elif "youtube.com" in cur_url:
            search_url = f"https://www.youtube.com/results?search_query={encoded}"
        elif "github.com" in cur_url:
            search_url = f"https://github.com/search?q={encoded}"
        else:
            search_url = f"https://www.google.com/search?q={encoded}"

        logger.info("Searching current tab in %s: %s -> %s", self._app_name, query, search_url)
        success = self.open_url(search_url, new_tab=False)
        time.sleep(0.35)
        new_state = self.refresh_browser_state()
        idx = new_state.get("active_tab", 1)
        title = new_state.get("title", f"{query} - Search")
        new_url = new_state.get("url", search_url)
        log_browser_diagnostics("SEARCH_CURRENT_TAB", "SUCCESS" if success else "FAILED", query=query, url=new_url, tab_idx=idx)
        return success, idx, title, new_url

    def scroll_page(self, direction: str = "down", amount: str | int = "medium") -> bool:
        """Scroll the active browser window smoothly via native Quartz CGEvent."""
        # 1. Bring browser window to front
        self._run_applescript(f'tell application "{self._app_name}" to activate')
        time.sleep(0.1)

        # 2. Determine scroll delta
        if isinstance(amount, int):
            delta = amount // 50
        elif amount == "small":
            delta = 6
        elif amount == "large":
            delta = 25
        else:  # medium
            delta = 14

        sign = -1 if direction == "down" else 1
        clicks = sign * delta

        try:
            import Quartz
            for _ in range(4):
                ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 1, clicks // 4 or sign)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.04)

            log_browser_diagnostics("SCROLL_PAGE", "SUCCESS", extra=f"direction={direction}, amount={amount}")
            return True
        except Exception as exc:
            logger.debug("Quartz scroll error: %s", exc)
            # Fallback JavaScript scroll
            scroll_px = 500 if direction == "down" else -500
            self.execute_script(f"window.scrollBy({{ top: {scroll_px}, behavior: 'smooth' }});")
            return True

    def scroll_to_top(self) -> bool:
        """Scroll active tab to top of page."""
        self._run_applescript(f'tell application "{self._app_name}" to activate')
        try:
            import Quartz
            for _ in range(10):
                ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 1, 50)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.02)
            log_browser_diagnostics("SCROLL_TO_TOP", "SUCCESS")
            return True
        except Exception:
            self.execute_script("window.scrollTo({ top: 0, behavior: 'smooth' });")
            return True

    def scroll_to_bottom(self) -> bool:
        """Scroll active tab to bottom of page."""
        self._run_applescript(f'tell application "{self._app_name}" to activate')
        try:
            import Quartz
            for _ in range(10):
                ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 1, -50)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                time.sleep(0.02)
            log_browser_diagnostics("SCROLL_TO_BOTTOM", "SUCCESS")
            return True
        except Exception:
            self.execute_script("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });")
            return True

    def execute_script(self, js_code: str) -> Any:
        """Run JavaScript in the active tab (when permitted by browser)."""
        escaped_js = js_code.replace('\\', '\\\\').replace('"', '\\"')

        if "Chrome" in self._app_name or "Brave" in self._app_name or "Edge" in self._app_name:
            script = f'''
            tell application "{self._app_name}"
                if (count of windows) > 0 then
                    tell active tab of front window
                        return execute javascript "{escaped_js}"
                    end tell
                end if
            end tell
            '''
        elif "Safari" in self._app_name:
            script = f'''
            tell application "Safari"
                if (count of windows) > 0 then
                    tell current tab of front window
                        return do JavaScript "{escaped_js}"
                    end tell
                end if
            end tell
            '''
        else:
            return None

        success, result = self._run_applescript(script)
        if success:
            try:
                return json.loads(result)
            except Exception:
                return result
        return None

    def click(self, selector: str) -> bool:
        """Click the first DOM element matching selector."""
        js = f"""
        (function() {{
            const el = document.querySelector("{selector}");
            if (el) {{
                el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                el.click();
                return "clicked";
            }}
            return "not_found";
        }})()
        """
        res = self.execute_script(js)
        return res == "clicked"

    def type_text(self, selector: str, text: str) -> bool:
        """Type text into an input field matching selector."""
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')
        js = f"""
        (function() {{
            const el = document.querySelector("{selector}");
            if (el) {{
                el.value = "{escaped_text}";
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return "typed";
            }}
            return "not_found";
        }})()
        """
        res = self.execute_script(js)
        return res == "typed"

    def wait_for(self, selector: str, timeout_seconds: float = 5.0) -> bool:
        """Poll until selector is present in DOM."""
        start_t = time.monotonic()
        js = f'document.querySelector("{selector}") !== null'
        while time.monotonic() - start_t < timeout_seconds:
            if self.execute_script(js) is True or self.execute_script(js) == "true":
                return True
            time.sleep(0.3)
        return False

    def extract_page_content(self) -> PageContent:
        """Extract sanitized readable content from the active tab using PageContentExtractor."""
        from browser.extractor import PageContentExtractor
        extractor = PageContentExtractor()
        return extractor.extract_page(self)

    def extract_search_results(self, limit: int = 5) -> list[dict[str, str]]:
        """Extract organic search results from active tab using PageContentExtractor."""
        from browser.extractor import PageContentExtractor
        extractor = PageContentExtractor()
        return extractor.extract_search_results(self, limit=limit)

    def shutdown(self) -> None:
        """Shutdown engine resources."""
        self._is_initialized = False
        logger.info("MacOSNativeBrowserEngine shut down.")
