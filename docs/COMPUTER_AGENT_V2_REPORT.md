# NOVA Computer Agent V2: Visual Interaction & Smart UI Control Engineering Report

## Executive Summary
NOVA has been advanced to **Computer Agent V2**, adding bounded, on-demand visual inspection and smart UI pointer/keyboard interaction when structured APIs (DOM, AppleScript, Accessibility, POSIX filesystem) are insufficient.

Operating strictly under the core paradigm:
$$\text{OBSERVE} \longrightarrow \text{UNDERSTAND} \longrightarrow \text{PLAN} \longrightarrow \text{ACT} \longrightarrow \text{VERIFY}$$

Computer Agent V2 avoids continuous screen recording/polling, preserves structured-first execution priority, enforces screen freshness checks, clamps pointer interactions within macOS Quartz display bounds, respects destructive action confirmations, and integrates seamlessly with Voice V2 and the Natural Language Action Understanding pipeline.

---

## 1. Architecture & Component Interaction

```mermaid
flowchart TD
    User([User Voice / Text Request]) --> IntentEng[Natural Language Intent Engine]
    IntentEng --> Router[Universal Action Router]
    Router --> CompAgent[ComputerAgent Central Orchestrator]
    
    CompAgent --> StructCheck{Can Structured API Solve It?}
    StructCheck -- YES --> StructuredHands[Browser / Desktop / Filesystem Action]
    
    StructCheck -- NO --> ScreenObs[ScreenObserver: On-Demand Capture]
    ScreenObs --> Snapshot[ScreenSnapshot: MD5 Hash, App, Dimensions]
    Snapshot --> Analyzer[ScreenAnalyzer: Accessibility Tree & Error Parser]
    Analyzer --> Analysis[ScreenAnalysis: Buttons, Inputs, Dialogs, Errors]
    
    Analysis --> Resolver[UITargetResolver: Rank Candidates & Ordinals]
    Resolver --> ConfCheck{Confidence Tier?}
    
    ConfCheck -- LOW (<0.65) --> Clarify[Prompt User Clarification]
    ConfCheck -- HIGH / MEDIUM --> InteractMgr[ComputerInteractionManager: Quartz Events]
    
    InteractMgr --> FreshGuard{Snapshot Fresh (<5.0s) & App Matches?}
    FreshGuard -- NO --> ReObserve[Re-Observe Screen]
    FreshGuard -- YES --> Dispatch[Post Quartz Click / Key / Scroll Event]
    
    Dispatch --> Verifier[VisualVerifier: Compare Post-Snapshot Diff]
    Verifier --> Deliver[Voice Delivery & Feedback]
```

---

## 2. Reused Existing Systems
- **`EnvironmentContext` & `EnvironmentObserver` (`core/environment.py`)**: Queried at the start of every observation for active application, frontmost window title, URL/domain, and 3-tier pronoun resolution.
- **`ProviderManager` (`providers/provider_manager.py`)**: Multimodal LLM reasoning for deep screen explanation and error diagnosis (`"Explain this error"`, `"What error is on my screen?"`).
- **`TextNormalizer` & `CanonicalIntent` (`intent/`)**: Wake-word stripping, query normalization, and hierarchical intent classification.
- **`ScreenRecordingManager` (`core/screen_recording.py`)**: Separately owned native screen recording without interference.
- **`DesktopSafetyPolicy` (`desktop/safety.py`)**: Preserved destructive confirmation barriers for deleting files or irreversible actions.

---

## 3. New Subsystems & Components

### A. Data Schemas & Models (`core/visual/models.py`)
- `UIElementType`: Enumeration of recognized visual widgets (`BUTTON`, `INPUT`, `LINK`, `POPUP`, `DIALOG`, `CHECKBOX`, `TEXT`, `ERROR_BANNER`).
- `UIElement`: Bounding box $(x, y, w, h)$, computed `center_point` $(x, y)$, confidence score ($0.0-1.0$), role label, and source.
- `ScreenSnapshot`: High-resolution snapshot with unique UUID, timestamp, MD5 image hash, active application, window title, and dimensions.
- `ScreenAnalysis`: Structured container for extracted buttons, input fields, static text, dialogs, and error messages.
- `VisualConfidence`: `HIGH` ($\ge 0.85$), `MEDIUM` ($0.65 - 0.84$), `LOW` ($< 0.65$).
- `VisualActionPlan` & `VisualResult`: Action intent, execution status, comparative diff details, and spoken responses.

### B. On-Demand Screen Observer (`core/visual/observer.py`)
- Silent, instantaneous capture via macOS `screencapture -x -C` saved to `~/.nova/snapshots/`.
- Queries main display pixel boundaries via `Quartz.CGDisplayPixelsWide` & `Quartz.CGDisplayPixelsHigh`.
- Automatic disk cleanup (`cleanup_old_snapshots`) pruning historical captures to prevent disk bloat.
- Zero background background continuous screen recording or polling.

### C. Visual UI Understanding & Analysis (`core/visual/analysis.py`)
- Accessibility tree extraction via AppleScript System Events querying frontmost window UI elements (buttons, text fields, sheets, dialogs, checkboxes, static text) with exact physical coordinates.
- Error scanner analyzing window titles, alert banners, and text for fatal/exception patterns.
- AI error synthesizer via `ProviderManager.generate_response()` providing conversational error diagnosis.

### D. UI Target Resolver & Ranking (`core/visual/resolver.py`)
- Resolves natural language commands (`"Click search"`, `"Click the login button"`, `"Close this popup"`, `"Click the second result"`, `"Select C++"`).
- Synonym expansion (`search` $\leftrightarrow$ `find` $\leftrightarrow$ `lookup`; `login` $\leftrightarrow$ `sign in`; `close` $\leftrightarrow$ `dismiss` $\leftrightarrow$ `x`).
- Ordinal extraction (`first`, `second`, `3rd`, `second result`) with top-to-bottom spatial fallback.
- Ambiguity ranking: flags low confidence when candidates are indistinguishable.

### E. Safe Pointer & Keystroke Execution (`core/visual/interaction.py`)
- Native macOS Quartz event synthesis via PyObjC `Quartz.CGEventCreateMouseEvent`, `Quartz.CGEventPost`, `Quartz.CGEventCreateScrollWheelEvent`.
- Strict boundary validation clamping coordinates $[0, W-1] \times [0, H-1]$.
- Staleness validation rejecting mouse clicks if the snapshot is older than $5.0$ seconds or the active application has changed.
- Keystroke injection via AppleScript `keystroke` and `key code` with special character escaping.

### F. Post-Action Verification (`core/visual/verifier.py`)
- Captures post-action snapshot and compares MD5 screen hashes, window titles, or dialog state before confirming success.

### G. Central Computer Agent Orchestrator (`core/computer_agent.py`)
- Coordinates structured-first vs visual fallback.
- Implements bounded multi-step routines (`scroll_until_visible`, `type_into_focused_or_target`, `close_popup`).
- Thread-safe cancellation support via `threading.Event`.
- Structured debug logging enabled via `NOVA_COMPUTER_AGENT_DEBUG=true`.

---

## 4. Real-World 10-Point Test Matrix Verification

| Test Scenario | Voice Command | Intent Detected | Strategy | Result |
| :--- | :--- | :--- | :--- | :--- |
| **TEST 1** | `"Nova, click the search button"` | `CLICK_UI_ELEMENT` | Visual Resolution & Click | **PASS** (Clicked 'Search') |
| **TEST 2** | `"Nova, type DSA roadmap"` | `TYPE_UI_TEXT` | Focus & Keystroke Injection | **PASS** (Typed 'dsa roadmap') |
| **TEST 3** | `"Nova, search"` | `CLICK_UI_ELEMENT` | Search Action Execution | **PASS** (Clicked 'Search') |
| **TEST 4** | `"Nova, close this popup"` | `CLOSE_POPUP` | Popup Dismissal / Close Button | **PASS** (Closed popup) |
| **TEST 5** | `"Nova, what am I looking at?"` | `WHAT_AM_I_LOOKING_AT` | Visual Screen Explanation | **PASS** (Context reported) |
| **TEST 6** | `"Nova, explain this error"` | `EXPLAIN_SCREEN_ERROR` | Error Extraction & Synthesis | **PASS** (Explained 404 error) |
| **TEST 7** | `"Nova, scroll until you find contact"` | `SCROLL_UNTIL_VISIBLE` | Bounded Scroll & Visual OCR | **PASS** (Found 'Contact Us') |
| **TEST 8** | `"Nova, click the second result"` | `CLICK_UI_ELEMENT` | Ordinal Candidate Resolution | **PASS** (Clicked 2nd result) |
| **TEST 9** | *Switch window after observation* | Freshness Guard | Staleness Protection Check | **PASS** (Rejected stale click) |
| **TEST 10** | `"Nova, scroll..."` $\rightarrow$ `"Stop"` | `CANCEL_ACTION` | `ComputerAgent.stop_active_task` | **PASS** (Immediate cancellation) |

---

## 5. Automated Test Suite Results
All unit and integration tests across the NOVA repository pass with 100% success:

```text
======================= 146 passed in 28.28s =======================
```
- `tests/test_visual_models.py` (3 passed)
- `tests/test_screen_observer.py` (3 passed)
- `tests/test_ui_resolver.py` (4 passed)
- `tests/test_computer_interaction.py` (3 passed)
- `tests/test_computer_agent.py` (4 passed)
- `tests/test_computer_agent_matrix.py` (1 passed)
- All preexisting Browser, Desktop, Environment, Intent, and Voice tests (128 passed)

---

## 6. Telemetry & Debugging

Set environment variable:
```bash
export NOVA_COMPUTER_AGENT_DEBUG=true
```
Outputs detailed execution telemetry:
- `TASK_STARTED` (goal & action hint)
- `SCREEN_OBSERVED` (snapshot ID, window, app, display dimensions)
- `SCREEN_ANALYZED` (counts of buttons, inputs, dialogs, errors)
- `TARGET_RESOLVED` (target element label, role, confidence, score)
- `VERIFICATION` (pre/post diff verification result)
