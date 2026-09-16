# NOVA Capability Status Matrix

This document is the machine-readable, authoritative capability status truth table for the NOVA Autonomous Assistant.
Last Audited: 2026-09-17 (Post Forensic Cleanup & Non-Terminal UI Removal)
Repository: `nikhil-singh91/NOVA_SETUP`
Authoritative Runtime: Terminal UI (`ui/terminal_dashboard.py`), `main.py`

Status Categories:
- **WORKING**: Code exists, is wired into runtime, tested, and verified operating correctly.
- **PARTIAL**: Operates under standard conditions, but has known gaps, rate-limits, or degraded fallback states.
- **BROKEN**: Code exists and is reachable, but execution fails or yields unverified/false-success output.
- **DISABLED**: Code exists, but is gated or requires missing local external dependencies.
- **REMOVED**: Obsolete or non-functional legacy code safely excised from codebase.
- **NOT VERIFIED**: Code exists and is imported, but relies on interactive physical hardware or live external hardware without automated test harness.

---

| Capability ID / Feature | Subsystem | Code Exists | Reachable (`main.py`) | Tested | Verified Working | Status | Notes & Limitations |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **Voice: Microphone Stream** | `voice.microphone` | YES | YES | YES | YES | **WORKING** | PyAudio 16kHz mono streaming with auto-reconnect |
| **Voice: VAD (Voice Activity)** | `voice.vad` | YES | YES | YES | YES | **WORKING** | Silero VAD / WebRTC energy gating; speech quality filters |
| **Voice: ASR (Speech-to-Text)** | `voice.speech_recognizer` | YES | YES | YES | YES | **WORKING** | Faster-Whisper local engine (supports `base`, `small`, `medium`) |
| **Voice: TTS (Text-to-Speech)** | `voice.tts` | YES | YES | YES | YES | **WORKING** | Primary `edge-tts` with offline `pyttsx3` fallback |
| **Voice: Interruption / Barge-in** | `voice.barge_in` | YES | YES | YES | YES | **WORKING** | Active listening cancels TTS playback instantly |
| **Voice: Quality Gate / ASR Confidence** | `voice.quality_gate` | YES | YES | YES | YES | **WORKING** | Drops low-probability hallucinations / background noise |
| **AI: Gemini Provider** | `providers.gemini_provider` | YES | YES | YES | YES | **WORKING** | Google GenAI SDK (`gemini-2.5-flash`, `gemini-1.5-pro`) |
| **AI: Groq Provider** | `providers.groq_provider` | YES | YES | YES | YES | **WORKING** | Groq Cloud SDK (`llama-3.3-70b-versatile`) |
| **AI: OpenRouter Provider** | `providers.openrouter_provider` | YES | YES | YES | YES | **WORKING** | OpenRouter REST API integration |
| **AI: Cerebras Provider** | `providers.cerebras_provider` | YES | YES | YES | YES | **WORKING** | Cerebras Cloud SDK (`llama3.1-8b`, `llama3.3-70b`) |
| **AI: ProviderManager Fallback** | `providers.manager` | YES | YES | YES | YES | **WORKING** | Multi-tier failover: Gemini -> Groq -> OpenRouter -> Cerebras |
| **AI: Deterministic Bypass** | `intent.engine` | YES | YES | YES | YES | **WORKING** | Regex/pattern matching bypasses LLM latency for fast commands |
| **Browser: Chrome Detection** | `browser.detector` | YES | YES | YES | YES | **WORKING** | Resolves running Chrome, Brave, Safari, Edge via AppleScript/psutil |
| **Browser: Open URL / Search** | `browser.actions` | YES | YES | YES | YES | **WORKING** | Direct AppleScript and CLI dispatch |
| **Browser: YouTube Music Search** | `media.service` | YES | YES | YES | YES | **PARTIAL** | Scrapes `ytInitialData`; susceptible to YouTube rate-limiting |
| **Browser: YouTube Shorts Auto-Scroll**| `browser.sites.youtube` | YES | YES | YES | YES | **WORKING** | Timed or voice-driven down-arrow scrolling |
| **Browser: DOM Deep Extraction** | `browser.engine` | YES | YES | NO | NO | **DISABLED** | Requires external CDP / Playwright bridge not attached in CLI mode |
| **Computer: Mouse Click** | `desktop.mouse` | YES | YES | YES | YES | **WORKING** | PyObjC / Quartz CoreGraphics native mouse events |
| **Computer: Mouse Move & Drag** | `desktop.mouse` | YES | YES | YES | YES | **WORKING** | Native Quartz event generation |
| **Computer: Keyboard Typing** | `desktop.keyboard` | YES | YES | YES | YES | **WORKING** | Native keycode mapping with modifiers |
| **Computer: Hotkey Execution** | `desktop.keyboard` | YES | YES | YES | YES | **WORKING** | Cmd/Opt/Ctrl/Shift shortcuts |
| **Computer: Retina Coordinate Mapping** | `desktop.coordinate_mapper`| YES | YES | YES | YES | **WORKING** | Scales logical points to physical Retina framebuffer pixels |
| **Eyes: Screen Capture (Native)** | `core.screenshot_service`| YES | YES | YES | YES | **WORKING** | macOS screencapture CLI + Quartz framebuffer grab |
| **Eyes: OCR (Text Detection)** | `core.screen_observer` | YES | YES | YES | YES | **WORKING** | Apple Vision Framework (VNRecognizeTextRequest) via PyObjC |
| **Eyes: UI Element Targeting** | `core.visual.resolver` | YES | YES | YES | YES | **WORKING** | Fuzzy text & fuzzy bounding box target matcher |
| **Mac Control: Volume (Get/Set/Step)**| `mac_control.system` | YES | YES | YES | YES | **WORKING** | Pure AppleScript `set volume output volume` |
| **Mac Control: Brightness (Step)** | `mac_control.system` | YES | YES | YES | YES | **PARTIAL** | Brightness stepping works; direct percentage read requires `brightness` CLI |
| **Mac Control: Wi-Fi Status/SSID** | `mac_control.system` | YES | YES | YES | YES | **PARTIAL** | SSID requires Location permissions on macOS Sonoma/Sequoia |
| **Mac Control: Bluetooth Status** | `mac_control.system` | YES | YES | YES | YES | **WORKING** | `blueutil` binary if installed, system_profiler fallback |
| **Mac Control: App Launch / Quit** | `mac_control.applications`| YES | YES | YES | YES | **WORKING** | NSWorkspace / open / osascript |
| **Filesystem: Create / Delete Folder** | `core.task_agent.capabilities.filesystem` | YES | YES | YES | YES | **WORKING** | Sandboxed to `~/Desktop` and project roots; verify before return |
| **Filesystem: Create / Read / Write File**| `core.task_agent.capabilities.filesystem` | YES | YES | YES | YES | **WORKING** | Atomic file writes with post-write stat verification |
| **Filesystem: Trash Safety (No hard rm)** | `core.task_agent.capabilities.filesystem` | YES | YES | YES | YES | **WORKING** | Uses `send2trash` or macOS trash folder |
| **Memory: Short-Term Conversation** | `memory.conversation_memory`| YES | YES | YES | YES | **WORKING** | Sliding window context buffer for active turn disambiguation |
| **Memory: Long-Term Semantic (JSON)** | `memory.long_term_memory` | YES | YES | YES | YES | **WORKING** | Local JSON file persistence for user preferences |
| **Memory: Vector DB (Chroma)** | `memory.vector_store` | YES | YES | YES | NO | **DISABLED** | PyTorch / Chroma dependency optional; gracefully falls back |
| **Task Agent: Goal Decomposition** | `core.task_agent.planner`| YES | YES | YES | YES | **WORKING** | LLM + Rule-based multi-step plan generation |
| **Task Agent: Step Execution** | `core.task_agent.executor` | YES | YES | YES | YES | **WORKING** | Sequenced step execution with retry limits |
| **Task Agent: Action Verification** | `core.task_agent.verifier` | YES | YES | YES | YES | **WORKING** | Post-action assertion checks (file exists, app running, etc.) |
| **Task Agent: Dynamic Replanning** | `core.task_agent.replanner`| YES | YES | YES | YES | **WORKING** | Alternative step substitution on capability failure |
| **Task Agent: Pause / Resume / Cancel**| `core.task_agent.executor` | YES | YES | YES | YES | **WORKING** | Atomic flag checks between step transitions |
| **Safety: Risk Confirmation Gates** | `core.task_agent.models` | YES | YES | YES | YES | **WORKING** | High risk actions pause for user confirmation |
| **Safety: Secret Masking** | `core.event_bus` | YES | YES | YES | YES | **WORKING** | Masks API keys, tokens, passwords in event payloads |
| **EventBus: In-Process Pub/Sub** | `core.event_bus` | YES | YES | YES | YES | **WORKING** | Synchronous + thread-safe dispatch with subscriber isolation |
| **UI: Terminal Dashboard** | `ui.terminal_dashboard`| YES | YES | YES | YES | **WORKING** | Rich-based multi-panel terminal dashboard (Authoritative) |
| **UI: Diagnostic Doctor Suite** | `ui.doctor` | YES | YES | YES | YES | **WORKING** | Full pre-flight system self-check |
| **UI: Non-Terminal React/Electron UI** | `ui.desktop`, `ui.backend` | NO | NO | NO | NO | **REMOVED** | Safely deleted; was disconnected, duplicated, and broken |
