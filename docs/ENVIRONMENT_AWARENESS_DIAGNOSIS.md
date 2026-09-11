# NOVA Environment Awareness & Computer Agent V1 — Diagnosis

## 1. Executive Summary

An architectural audit of NOVA's current subsystems (**Browser Actions**, **Desktop Actions V1**, **MacControlManager**, **Natural Language Intent Engine**, **Voice V2**, and **Memory/Context**) reveals that these subsystems operate in isolated silos. They lack a shared, real-time understanding of the user's operating system environment (active window, current URL, Finder selection, screen recording status). Furthermore, natural language requests with pronouns ("this", "that", "it", "here") or implicit context fail or get misrouted.

---

## 2. Detailed Root-Cause Analysis of Failing Commands

### 1. "Go to AKTU website" / "Open AKTU" / "Take me to AKTU"
- **Observed Behavior:** Fails or misroutes.
- **Root Cause:**
  1. In `main.py`, `DesktopActionManager.process_input()` executes *before* `BrowserManager`.
  2. `DesktopIntentParser` regex `r"^(?:open|launch|start)\s+(?:my\s+)?(?:app\s+|application\s+)?(.+?)(?:\s+app)?$"` treats `"AKTU"` or `"Flipkart"` as an application name, attempts `open -a aktu`, fails, and reports a launch failure instead of routing to browser discovery.
  3. When `BrowserIntentParser` processes `"Go to AKTU website"`, `GenericSiteSkill` performs an unverified DuckDuckGo HTML scrape or falls back to Google search without verifying that the official domain was discovered and loaded.

### 2. "In Flipkart search mobile phones" / "Search mobile phones in Flipkart" / "Search iPhone here"
- **Observed Behavior:** Fails to search on Flipkart; either unrecognized or treated as a general Google search.
- **Root Cause:**
  1. `BrowserIntentParser._parse_site_search_commands()` regex only matches `search <site> for <query>` or `search <query> for/on <site>`. Prepositional forms like `in <site> search <query>` or `search <query> in <site>` fail regex matching.
  2. Contextual searches like `"Search iPhone here"` fail because `BrowserContextManager` is isolated in-memory and does not query the real active browser domain to know what "here" refers to.

### 3. "Create a folder on Desktop" / "Create a folder called Test on Desktop"
- **Observed Behavior:** Either parses incorrectly or creates the folder inside `~/Desktop/NOVA_WORKSPACE/` instead of `~/Desktop/`.
- **Root Cause:**
  1. `DesktopIntentParser` regex `r"^create\s+(?:a\s+)?folder\s+(?:called|named)?\s*([a-zA-Z0-9_\-\s]+?)(?:\s+on\s+my\s+desktop|\s+in\s+workspace)?$"` requires "called/named" or incorrectly matches "on Desktop" as the folder name.
  2. `FileSystemManager.create_folder()` always defaults `base_dir` to `DesktopSafetyPolicy.get_default_workspace()` (`~/Desktop/NOVA_WORKSPACE`), disregarding explicit user intent for `~/Desktop`.

### 4. "Open DSA folder"
- **Observed Behavior:** Fails or falsely claims to open the folder.
- **Root Cause:**
  1. `DesktopIntentParser` tries `open -a "dsa folder"`, which fails.
  2. In `MacControlManager` / `mac_control/actions/finder.py`, `FOLDER_MAP` only contains fixed keys (`desktop`, `downloads`, `documents`, `movies`, `pictures`, `finder`). Any other key (e.g., `dsa`) falls back to `~/` (home directory), opens `~/`, and reports `"Opened Dsa in Finder"`. This is a false claim of success.

### 5. "Write an application for college leave" / "Write a leave application"
- **Observed Behavior:** Fails dynamic AI generation, silently drops to a static fallback template.
- **Root Cause:**
  1. `DocumentEditor.generate_document_text()` calls `provider_mgr.generate(prompt)`. However, `ProviderManager` exposes `generate_response()`, not `generate()`.
  2. An `AttributeError` is raised and caught, silently falling back to a static hardcoded string rather than generating context-aware content.

### 6. "I want to go to the market at 8 PM"
- **Observed Behavior:** Semantic ambiguity; risk of misclassifying as document writing or general chat turn.
- **Root Cause:**
  1. There is no intent classifier distinguishing `REMINDER_REQUEST` / `CALENDAR_REQUEST` / `GENERAL_CONVERSATION`.
  2. Without an explicit clarification pipeline, statements with time references risk triggering notepad writing or falling into ungrounded LLM responses without asking: *"Do you want me to remind you at 8 PM?"*

### 7. "Play Shorts" / "Open YouTube Shorts"
- **Observed Behavior:** Searches YouTube for regular videos titled "shorts".
- **Root Cause:**
  1. `BrowserIntentParser._parse_play_commands()` catches `"Play Shorts"`, extracts query `"shorts"`, and emits `ActionType.PLAY_MEDIA`, navigating to `https://www.youtube.com/results?search_query=shorts` instead of `ActionType.WATCH_SHORTS` (`https://www.youtube.com/shorts`).

### 8. Context Commands using "this", "that", "it", "here"
- **Observed Behavior:** Unhandled or acts on stale memory.
- **Root Cause:**
  1. No canonical `EnvironmentContext` exists.
  2. `DesktopContextManager` and `BrowserContextManager` maintain separate, in-process state that is not grounded in the actual macOS frontmost window, active browser URL, or Finder selection.

### 9 & 10. "Record screen" & "Stop screen recording"
- **Observed Behavior:** Unrecognized command.
- **Root Cause:**
  1. No `ScreenRecordingManager` exists in the codebase.
  2. "Stop recording" is either ignored or misrouted to stopping browser auto-scrolling.

---

## 3. Subsystem Architecture Map & Identified Gaps

| Subsystem | Current State | Gap / Vulnerability |
|---|---|---|
| **Environment Observation** | Non-existent; isolated memory | No real-time awareness of active OS window, active browser tab, or Finder selection |
| **Intent Engine** | Layered regex + LLM fallback | Subsystems evaluate in rigid sequence in `main.py` rather than using a single environment-aware intent router |
| **Browser Controller** | AppleScript native automation | Lacks dynamic in-site search detection and robust official entity website discovery |
| **Desktop / Filesystem** | Sandboxed in `NOVA_WORKSPACE` | Diverts explicit `Desktop` commands to workspace; false claims on folder search |
| **Document Writing** | Bug in `DocumentEditor` | Calls nonexistent method `provider_mgr.generate()`, throwing `AttributeError` |
| **Screen Recording** | Missing | No capture manager, permissions verification, or process lifecycle tracking |
| **Delete Safety** | Missing confirmation flow | No safe Trash integration for contextual deletions |

---

## 4. Architectural Prescription

1. **Central `EnvironmentContext` & `EnvironmentObserver`:** Single source of truth refreshed on-demand before context-sensitive operations via AppleScript / native macOS APIs.
2. **Deterministic Context Resolution Hierarchy:**
   $$\text{Real Current State} \longrightarrow \text{Current App/Browser Context} \longrightarrow \text{Recent NOVA Action}$$
3. **Unified `IntentRouter` & `ActionPlanner`:** Intent classification with domain dispatching (`BROWSER`, `DESKTOP`, `FILESYSTEM`, `DOCUMENT_WRITING`, `SCREEN_RECORDING`, `REMINDER`, etc.).
4. **Safety & Verification on Every Action:** Delete confirmation moving to Trash; verification of URL loading, file creation, and recording process output.
