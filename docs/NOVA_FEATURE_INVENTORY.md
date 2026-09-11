# NOVA Complete Feature Inventory

---

## 1. Subsystem Architecture Overview

| Subsystem Layer | Primary Responsibility | Key Files |
| :--- | :--- | :--- |
| **Voice & Speech (V2)** | Real-time audio capture, Silero VAD speech activity detection, Faster-Whisper transcription, Kokoro/Piper TTS. | `voice/listener.py`, `voice/transcriber.py`, `voice/speaker.py`, `voice/manager.py` |
| **Intent Classification** | Layered rule-based regex parsing + semantic confidence evaluation + LLM fallback. | `intent/engine.py`, `intent/matcher.py`, `intent/models.py`, `intent/router.py` |
| **Browser Automation** | Chrome/Safari native automation, tab switching, site search, web extraction, YouTube playback. | `browser/manager.py`, `browser/engine.py`, `browser/router.py`, `browser/sites/*` |
| **Desktop & Filesystem** | Desktop folder/file creation, code templating, app launching, safe trash deletion. | `desktop/manager.py`, `desktop/files.py`, `desktop/apps.py`, `desktop/editor.py` |
| **Environment Awareness (V1)** | Real-time active window, URL, Finder selection tracking, pronoun resolution (`it`, `this`). | `core/environment.py` |
| **Computer Agent (V2)** | On-demand screen OCR, visual UI element detection, mouse clicking, text typing, popup closing. | `core/computer_agent.py`, `core/visual/*` |
| **Autonomous Task Agent (V3)** | High-level goal decomposition, multi-step dependency execution, dynamic replanning, goal verification. | `core/task_agent/*` |
| **macOS System Control** | Native volume, brightness, battery, lock screen, sleep, and hardware commands. | `mac_control/manager.py`, `mac_control/actions/*` |
| **Media & Music Service** | Intelligent YouTube track resolution, candidate scoring, official/remix modifier handling. | `media/service.py`, `media/collector.py`, `media/scorer.py` |
| **Screen Recording** | Bounded background video recording (`screencapture` / AVFoundation). | `core/screen_recording.py` |
| **Multi-Provider AI** | Dynamic provider selection (Gemini, Groq, Cerebras, OpenRouter) based on task type. | `providers/provider_manager.py`, `providers/*` |

---

## 2. Comprehensive Feature Breakdown

### Feature: Native Application Launching & Management
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text, Task Agent
- **Command Examples**: `"Open VS Code"`, `"Launch Chrome"`, `"Open TextEdit"`, `"Close VS Code"`
- **Source Files**: `desktop/apps.py`, `desktop/manager.py`, `intent/matcher.py`
- **Entry Point**: `CanonicalIntent.LAUNCH_APP` / `CanonicalIntent.CLOSE_APP` $\rightarrow$ `DesktopActionManager.process_input()`
- **Dependencies**: Native macOS `/Applications`, `mdfind` / Spotlight CLI
- **Permissions**: None
- **Verification Method**: Process inspection via `pgrep` and `NSWorkspace.runningApplications`
- **Test Coverage**: `tests/test_desktop_actions.py`, `tests/test_natural_language_intents.py`
- **Known Limitations**: Non-standard third-party app bundle names may require exact app name.

---

### Feature: Desktop & Safe Filesystem Management
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text, Task Agent
- **Command Examples**: `"Create a folder called DSA on Desktop"`, `"Open DSA folder"`, `"Create main.cpp inside it"`
- **Source Files**: `desktop/files.py`, `desktop/manager.py`, `desktop/safety.py`
- **Entry Point**: `CanonicalIntent.CREATE_DESKTOP_FOLDER`, `CanonicalIntent.OPEN_FOLDER`, `CanonicalIntent.CREATE_DESKTOP_FILE`
- **Dependencies**: Python standard `pathlib`, `shutil`
- **Permissions**: Standard user folder read/write permissions
- **Verification Method**: Direct `Path.exists()` and `Path.is_dir()` assertion
- **Test Coverage**: `tests/test_desktop_actions.py`, `tests/test_task_agent_matrix.py`
- **Known Limitations**: Restricted system directories (`/System`, `/Library`, `/usr`) are blocked by `DesktopSafetyPolicy`.

---

### Feature: Safe Delete & Trash Management
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text, Task Agent
- **Command Examples**: `"Delete this folder"`, `"Delete that file"`, `"Move this to trash"`
- **Source Files**: `desktop/files.py`, `core/environment.py`, `main.py`
- **Entry Point**: `CanonicalIntent.DELETE_ITEM` $\rightarrow$ Intercepted for user confirmation $\rightarrow$ `FileSystemManager.safe_move_to_trash()`
- **Dependencies**: macOS `~/.Trash`
- **Permissions**: User file permissions
- **Verification Method**: Target path checked to verify disappearance from original location and relocation into `~/.Trash`
- **Test Coverage**: `tests/test_desktop_actions.py`, `tests/test_environment_context.py`
- **Known Limitations**: Permanent shredding is intentionally disallowed; all deletions go safely to `~/.Trash`.

---

### Feature: AI Document Generation & Editor Launch
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text, Task Agent
- **Command Examples**: `"Write an application for college leave"`, `"Write an apology email for delay"`
- **Source Files**: `desktop/editor.py`, `providers/provider_manager.py`
- **Entry Point**: `CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT` $\rightarrow$ `DocumentEditor.write_and_open_document()`
- **Dependencies**: AI language model (`ProviderManager`), macOS `TextEdit`
- **Permissions**: None
- **Verification Method**: File existence check at `~/Documents/NOVA_Documents/<topic>.txt`
- **Test Coverage**: `tests/test_desktop_actions.py`, `tests/test_natural_language_intents.py`
- **Known Limitations**: Requires valid API key configured in `.env` for LLM content generation.

---

### Feature: Browser & Website Automation
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text, Task Agent
- **Command Examples**: `"Go to AKTU website"`, `"Open Flipkart"`, `"Search Google for Python tutorial"`, `"In Flipkart search mobile phones"`, `"Next tab"`, `"Close this tab"`
- **Source Files**: `browser/manager.py`, `browser/engine.py`, `browser/router.py`, `browser/sites/*`
- **Entry Point**: `RoutingDomain.BROWSER` $\rightarrow$ `BrowserManager.execute_command()`
- **Dependencies**: Google Chrome or Safari, AppleScript engine
- **Permissions**: macOS Automation / AppleEvents permission
- **Verification Method**: Tab count, active URL verification via browser AppleScript bridge
- **Test Coverage**: `tests/test_browser_actions.py`, `tests/test_browser_actions_v2.py`
- **Known Limitations**: Works primarily with Google Chrome and Safari; custom electron-based browsers are not automated.

---

### Feature: Intelligent Media & Music Playback
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text
- **Command Examples**: `"Play Kesariya"`, `"Play Believer"`, `"Open YouTube Shorts"`, `"Next Short"`, `"Stop Shorts"`
- **Source Files**: `media/service.py`, `media/collector.py`, `media/scorer.py`, `browser/sites/youtube.py`
- **Entry Point**: `CanonicalIntent.PLAY_MEDIA` / `CanonicalIntent.WATCH_SHORTS`
- **Dependencies**: Web access to YouTube, YouTube candidate parser
- **Permissions**: Internet access
- **Verification Method**: Target video URL launched in browser session
- **Test Coverage**: `tests/test_media_matching.py`, `tests/test_browser_actions.py`
- **Known Limitations**: Does not bypass YouTube video advertisements; native media key simulation is handled separately.

---

### Feature: Environment Awareness & Context Resolution
- **Status**: Production-ready candidate (🟢)
- **User Access**: Seamless background context across all turns
- **Command Examples**: `"Open it"` (after folder create), `"Summarize this"` (on active webpage), `"Explain this error"` (on active window)
- **Source Files**: `core/environment.py`
- **Entry Point**: `EnvironmentObserver.refresh()`, `ContextResolver.resolve_target()`
- **Dependencies**: `CGWindowListCopyWindowInfo`, AppleScript Finder/Browser introspection
- **Permissions**: macOS Accessibility and Automation privileges
- **Verification Method**: Context assertions in turn loop
- **Test Coverage**: `tests/test_environment_context.py`, `tests/test_environment_voice_matrix.py`
- **Known Limitations**: Cross-turn context window resets if NOVA application is completely restarted.

---

### Feature: Computer Agent Visual UI Control (V2)
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text, Task Agent
- **Command Examples**: `"What am I looking at?"`, `"Explain this error"`, `"Click search"`, `"Close this popup"`, `"Scroll until you find pricing"`
- **Source Files**: `core/computer_agent.py`, `core/visual/*`
- **Entry Point**: `CanonicalIntent.CLICK_UI_ELEMENT`, `CanonicalIntent.TYPE_UI_TEXT`, `CanonicalIntent.CLOSE_POPUP`, `CanonicalIntent.SCROLL_UNTIL_VISIBLE`, `CanonicalIntent.EXPLAIN_SCREEN_ERROR`
- **Dependencies**: `screencapture`, `Apple Vision / pytesseract` OCR, CoreGraphics / PyAutoGUI mouse control
- **Permissions**: macOS Screen Recording, Accessibility
- **Verification Method**: Post-action screen delta verification (`VisualVerifier`)
- **Test Coverage**: `tests/test_computer_agent.py`, `tests/test_computer_agent_matrix.py`, `tests/test_ui_resolver.py`
- **Known Limitations**: Dual-monitor setups default to primary display (Display 0).

---

### Feature: Autonomous Task Agent Goal Planning & Dynamic Replanning (V3)
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text
- **Command Examples**: `"Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders"`, `"Create a C++ project with main.cpp and README.md"`, `"Find a Python tutorial and save the useful link in a text file"`
- **Source Files**: `core/task_agent/*`, `intent/matcher.py`, `main.py`
- **Entry Point**: `CanonicalIntent.AUTONOMOUS_TASK` $\rightarrow$ `TaskPlanner.plan_goal()` $\rightarrow$ `TaskExecutor.execute_plan()`
- **Dependencies**: Verified `CapabilityRegistry`, `DynamicReplanner`
- **Permissions**: Respective subsystem permissions
- **Verification Method**: Step-by-step verification + Holistic post-task goal verification
- **Test Coverage**: `tests/test_task_models.py`, `tests/test_task_planner.py`, `tests/test_task_executor.py`, `tests/test_task_replanning.py`, `tests/test_task_agent_matrix.py`
- **Known Limitations**: Replan iterations capped at 3 to avoid unbounded execution loops.

---

### Feature: Screen Recording Manager
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text
- **Command Examples**: `"Start recording screen"`, `"Stop recording"`
- **Source Files**: `core/screen_recording.py`, `intent/matcher.py`, `main.py`
- **Entry Point**: `CanonicalIntent.START_SCREEN_RECORDING`, `CanonicalIntent.STOP_SCREEN_RECORDING`
- **Dependencies**: macOS `screencapture` CLI / AVFoundation
- **Permissions**: macOS Screen Recording
- **Verification Method**: Process PID tracking and output file validation in `~/Movies/NOVA_Recordings/`
- **Test Coverage**: `tests/test_screen_recording.py`
- **Known Limitations**: Only 1 active recording session can run concurrently.

---

### Feature: macOS System Hardware & Volume Control
- **Status**: Production-ready candidate (🟢)
- **User Access**: Voice, Text
- **Command Examples**: `"Set volume to 50%"`, `"Mute"`, `"Unmute"`, `"Set brightness to 80%"`, `"Lock screen"`
- **Source Files**: `mac_control/manager.py`, `mac_control/actions/*`
- **Entry Point**: `MacControlManager.process_input()`
- **Dependencies**: Native `osascript`, `brightness` CLI
- **Permissions**: Accessibility / System Events
- **Verification Method**: AppleScript return code and system status queries
- **Test Coverage**: `tests/test_end_to_end_voice_turn.py`
- **Known Limitations**: External third-party monitors might not support software brightness adjustments via DDC.
