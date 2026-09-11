# NOVA Browser Actions V2.1 Real-World Reliability Diagnosis

## Executive Summary
Real-world testing on macOS revealed critical reliability failures where mocked tests previously passed. This diagnosis identifies the exact root causes across macOS AppleScript constraints, browser developer settings, tab state tracking, intent parser regexes, and content extraction.

---

## 1. Root Cause Analysis of Failures

### A. Tab Switching Failure
* **Root Cause:**
  1. `BrowserSessionManager.switch_tab()` in `browser/sessions.py` was executing a dummy JavaScript snippet: `js = "return true;"`.
  2. Because JavaScript execution through AppleScript was blocked by Chrome's default security setting (`Allow JavaScript from Apple Events` off), and even if it were on, `window` JavaScript inside a web page cannot switch browser tabs.
  3. Meanwhile, native AppleScript properties (`active tab index of front window`) were not being utilized for tab switching.
* **Exact Responsible Files/Functions:**
  - `browser/sessions.py`: `switch_tab()`
  - `browser/engine.py`: Missing native AppleScript tab indexing methods (`get_active_tab_index()`, `set_active_tab_index()`, `list_tabs()`).

---

### B. Active Page Detection Failure
* **Root Cause:**
  1. `BrowserManager.execute_command()` did not synchronize with the actual frontmost browser window before processing context-dependent commands ("What is written on this page?", "Read this page").
  2. If the user manually clicked to a different tab in Chrome or opened a new page, NOVA was either using stale context or calling `get_page_info()` without frontmost window activation.
* **Exact Responsible Files/Functions:**
  - `browser/manager.py`: `execute_command()`, `execute_plan()` missing `refresh_browser_state()`
  - `browser/context.py`: `BrowserContextManager` lacked synchronization with active browser state.

---

### C. Webpage Content Extraction Failure
* **Root Cause:**
  1. `PageContentExtractor.extract_page()` relied primarily on `engine.execute_script(extraction_js)`.
  2. In Google Chrome and Safari on macOS, AppleScript `execute javascript` is disabled by default for security (`View > Developer > Allow JavaScript from Apple Events` in Chrome, `Developer > Allow JavaScript from Apple Events` in Safari).
  3. When `execute_script` failed with error code 12 or 8, the engine returned `None`. The extractor fell back to returning just the URL string instead of the page's actual body text.
* **Exact Responsible Files/Functions:**
  - `browser/extractor.py`: `extract_page()`, `extract_search_results()`
  - `browser/engine.py`: `execute_script()` lacking fallback extraction.

---

### D. Scrolling Failure
* **Root Cause:**
  1. `MacOSNativeBrowserEngine.scroll_page()` executed `window.scrollBy(...)` via `execute_script()`.
  2. As noted above, AppleScript JavaScript execution is blocked by default, causing `scroll_page()` to fail silently without scrolling the actual browser page.
  3. AppleScript keystrokes via `System Events` failed with error `1002` (osascript not allowed to send keystrokes without Accessibility permissions).
  4. Native macOS PyObjC `Quartz.CGEventCreateScrollWheelEvent` posts smooth hardware-level scroll wheel events directly to the window server without requiring developer menu toggles or Accessibility permissions.
* **Exact Responsible Files/Functions:**
  - `browser/engine.py`: `scroll_page()`

---

### E. Google / Website Discovery Failure (e.g. "Open Mirai School of Technology website")
* **Root Cause:**
  1. `BrowserIntentParser._parse_open_site_commands()` only checked a hardcoded `TRUSTED_SITES` dictionary.
  2. When the user said `"Open Mirai School of Technology website"`, it failed to match `TRUSTED_SITES` and was either misclassified or passed to Google search results without navigating to the actual school website.
  3. The system lacked an automated website discovery resolver to search, filter out ads, extract the official domain (`https://miraisot.com/`), and navigate directly.
* **Exact Responsible Files/Functions:**
  - `browser/parser.py`: `_parse_open_site_commands()`
  - `browser/sites/generic.py`: `GenericSiteSkill.execute()`

---

### F. YouTube Search & Playback Failure (e.g. "Play song Mere Liye")
* **Root Cause:**
  1. **Parser mangling:** Regex in `_parse_play_commands()` was stripping out keywords aggressively or losing context, producing incomplete queries.
  2. **Failed link clicking:** `YouTubeSkill._handle_play_media()` opened the search results page (`youtube.com/results?search_query=...`) and attempted to click the first video using `execute_script()`. Because JavaScript from Apple Events was blocked, the video was never clicked, leaving the user on the search page with no playback!
  3. **Direct video resolution:** Direct resolution of the top YouTube watch URL (`https://www.youtube.com/watch?v=...`) was missing. Opening the direct watch URL guarantees instant video playback and audio without needing DOM JavaScript execution.
* **Exact Responsible Files/Functions:**
  - `browser/parser.py`: `_parse_play_commands()`
  - `browser/sites/youtube.py`: `_handle_play_media()`

---

## 2. Mocked Tests vs. Real Browser Discrepancy

| Test Case | Mocked Test Behavior | Real Browser Behavior (Pre-Overhaul) | Root Discrepancy |
| :--- | :--- | :--- | :--- |
| `test_page_content_extraction` | `MockBrowserEngine` returned synthetic JSON with mock headings and text. | Real Chrome threw AppleScript error code 12 (`JavaScript from Apple Events disabled`). Extractor returned empty text. | Mock bypassed macOS security model completely. |
| `test_youtube_skill_execution` | Mock claimed video was clicked and playing. | Real Chrome opened search results page and stayed there; playback never started. | Mock assumed DOM `click()` always succeeds. |
| `test_v2_tab_switching` | Mock flipped an in-memory integer. | Real Chrome tab never switched on screen. | Mock never executed AppleScript window commands. |
| `test_scroll_page` | Mock recorded string `"scroll_down_500"`. | Real Chrome window position never moved. | Mock bypassed window server event posting. |

---

## 3. Targeted Overhaul Architecture (V2.1)

1. **Unified Reliable macOS Control Engine:**
   - Native AppleScript window and tab indexing (`active tab index`, `set active tab index`, `count of tabs`, `title of tab`, `URL of tab`).
   - PyObjC Quartz native event posting (`CGEventCreateScrollWheelEvent`) for real window scrolling (`scroll_page`, `scroll_to_top`, `scroll_to_bottom`).
   - Direct HTTP / Readability parser with SSL/certifi support for 100% reliable page content extraction and search result parsing.
2. **Tab Management V2.1:**
   - Real-time `refresh_browser_state()`.
   - Native switching: `next_tab()`, `previous_tab()`, `switch_to_tab_index(n)`, `switch_to_tab_by_title_or_url(query)`.
3. **Website Discovery Engine:**
   - Search-backed domain resolution for arbitrary entities (*"Open Mirai School of Technology website"* -> discovers `https://miraisot.com/` and navigates).
4. **YouTube Playback V2.1:**
   - Query preservation without destructive stripping.
   - Search-to-watch-URL resolver (`/watch?v=...`) directly launching the watch page with verified audio playback.
5. **Action Verification & Debug Mode:**
   - Verify post-conditions (active tab changed, watch URL reached, content non-empty).
   - Configurable `NOVA_BROWSER_DEBUG=true` logging.
