# NOVA Code Status & Architecture Audit

---

## 1. Classification Methodology

- **ACTIVE**: Core production subsystem currently in the active execution path for Voice, Desktop, Browser, Computer Agent, and Autonomous Task Agent.
- **LEGACY**: Earlier implementations superseded by newer layers but retained for fallback compatibility.
- **DUPLICATE**: Overlapping utilities or multiple paths handling similar requests.
- **UNUSED / ARCHIVED**: Code in archive folders or isolated modules not imported in the active turn lifecycle.
- **UNCERTAIN**: Implementation exists with partial wiring or pending runtime validation.

---

## 2. Subsystem Status Matrix

| Subsystem Component | File Path | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Main Application** | `main.py` | **ACTIVE** | Central orchestrator coordinating TurnRequests, Voice V2, IntentEngine, DesktopManager, BrowserManager, ComputerAgent, TaskExecutor, and Lifecycle. |
| **Voice Subsystem V2** | `voice/manager.py`, `voice/listener.py`, `voice/transcriber.py`, `voice/speaker.py`, `voice/vad.py` | **ACTIVE** | Real-time audio loop, Silero VAD, Faster-Whisper, Kokoro TTS. |
| **Local Command Router** | `voice/commands.py` | **ACTIVE** | Local regex & Levenshtein distance matcher for fast shutdown commands. |
| **Intent Engine & Matcher** | `intent/engine.py`, `intent/matcher.py`, `intent/models.py`, `intent/router.py` | **ACTIVE** | Layered intent parser routing across 40+ canonical intents with confidence scoring. |
| **Desktop Action Manager** | `desktop/manager.py`, `desktop/files.py`, `desktop/apps.py`, `desktop/editor.py`, `desktop/code.py`, `desktop/safety.py` | **ACTIVE** | Core filesystem, app launching, document writing, and code file creation. |
| **Camera Manager** | `desktop/camera.py` | **ACTIVE (SECONDARY)** | Handled via fallback in `DesktopActionManager.process_input()`. |
| **Browser Action Manager** | `browser/manager.py`, `browser/engine.py`, `browser/router.py`, `browser/sites/*` | **ACTIVE** | Native Chrome/Safari automation, tab control, site search, and web scraping. |
| **Media Service** | `media/service.py`, `media/collector.py`, `media/scorer.py`, `media/parser.py` | **ACTIVE** | YouTube track resolution, candidate ranking, official/remix modifiers. |
| **Environment Awareness V1** | `core/environment.py` | **ACTIVE** | Real-time environment observation (`EnvironmentContext`), deictic pronoun resolution (`it`, `this`). |
| **Computer Agent V2** | `core/computer_agent.py`, `core/visual/*` | **ACTIVE** | On-demand screen OCR, visual element targeting, clicking, typing, popup dismissals. |
| **Autonomous Task Agent V3**| `core/task_agent/*` | **ACTIVE** | Goal planning (`TaskPlanner`), dependency execution (`TaskExecutor`), dynamic replanning (`DynamicReplanner`), capability registry. |
| **Screen Recording Manager** | `core/screen_recording.py` | **ACTIVE** | Background video recording via macOS `screencapture` CLI. |
| **macOS Control Manager** | `mac_control/manager.py`, `mac_control/actions/*` | **ACTIVE (SECONDARY)** | Hardware volume/brightness and system state fallback. |
| **Multi-Provider AI** | `providers/provider_manager.py`, `providers/*` | **ACTIVE** | Multi-model routing (Gemini, Groq, Cerebras, OpenRouter). |
| **Terminal UI & Diagnostics**| `ui/terminal_dashboard.py`, `ui/health_checker.py`, `ui/doctor.py` | **ACTIVE** | System health diagnostics and stats dashboard. |
| **Legacy Voice Backup** | `archive/legacy_voice/`, `archive/main_backup.py` | **UNUSED / ARCHIVED** | Historical backups preserved in `/archive/`. |
| **Plugins Directory** | `plugins/` | **UNUSED (PLACEHOLDER)**| Empty directory reserved for upcoming plugins/skills architecture. |
| **Models Directory** | `models/` | **UNUSED (PLACEHOLDER)**| Empty root directory; data models are stored inside subsystem directories. |

---

## 3. Duplicate & Overlapping Code Areas

1. **Application Launching**:
   - `desktop/apps.py` (`AppLauncher`) vs `mac_control/actions/applications.py`.
   - *Status*: `desktop/apps.py` is the primary active handler with verification; `mac_control` acts as fallback.
2. **Folder Opening**:
   - `desktop/files.py` (`FileSystemManager.find_folders_by_name`) vs `mac_control/actions/finder.py` (`FOLDER_MAP`).
   - *Status*: `desktop/files.py` searches dynamic workspace/Desktop paths and resolves `"it"`; `mac_control` only has fixed keys.
3. **Browser Automation**:
   - `browser/manager.py` (Full V2 session engine with site skills) vs `mac_control/actions/browser.py` (minimal AppleScript).
   - *Status*: `browser/manager.py` is the primary active engine.
