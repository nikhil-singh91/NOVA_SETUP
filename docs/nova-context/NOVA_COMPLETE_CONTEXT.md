# NOVA Master Architecture & System Context

> **Target Audience:** Autonomous AI Agent Builders, Core Engineers, System Architects  
> **Status:** Verified Active Codebase Reference (NOVA v3.5 / Core v0.1.0)  
> **Test Suite Status:** 881 Tests Passed (100% Green)

---

## 1. Executive Summary & Philosophy

NOVA is a modular, voice-first, multimodal personal AI operating system tailored specifically for macOS. It bridges high-level reasoning, perceptual awareness (vision, audio events, OS state), and concrete system execution (desktop actions, browser automation, file operations, hardware control) into a unified, responsive companion.

### Core Architectural Pillars:
1. **Perception-Action Loop (EYES & HANDS):** Real-time awareness of frontmost applications, browser tabs, Finder selections, and screen state enables deterministic resolution of natural deictic references ("this file", "that tab", "here").
2. **Layered Intent Architecture:** Natural language inputs are classified through deterministic regex matching and semantic entity extraction before falling back to LLM reasoning, ensuring sub-10ms response times for common actions.
3. **Resilient AI Provider Failover:** ProviderManager automatically balances between Gemini, Groq, OpenRouter, and Cerebras with zero downtime if any provider experiences rate limits or network degradation.
4. **Local-First Safety & Isolation:** Destructive operations (deletion, system shutdown) require explicit user confirmation. Computer vision and screen inspection occur 100% in-memory without unneeded disk dumps or cloud video streaming.

---

## 2. Global Repository Structure

```
NOVA_SETUP/
├── config/
│   └── settings.py               # Pydantic Settings v2 central configuration schema
├── core/
│   ├── computer_agent.py         # OBSERVE -> UNDERSTAND -> PLAN -> ACT -> VERIFY engine
│   ├── constants.py              # System-wide static constants & timeouts
│   ├── context.py                # RecentInteractionContext & ResolvedEntity tracker
│   ├── environment.py            # EnvironmentObserver & ContextResolver (macOS AppleScript)
│   ├── event_bus.py              # Application-wide thread-safe publish/subscribe EventBus
│   ├── exceptions.py             # Canonical exception hierarchy (AIProviderError, etc.)
│   ├── lifecycle.py              # Global ServiceLifecycle registry for start/stop hooks
│   ├── logger.py                 # Structured logging configuration
│   ├── paths.py                  # Standardized directory paths (data, logs, memory, media)
│   ├── registry.py               # Global service singleton registry
│   ├── response_cleaner.py       # LLM output sanitization (markdown/thinking stripping)
│   ├── screen_recording.py       # ScreenRecordingManager (AVFoundation / ffmpeg / screencapture)
│   ├── screenshot.py             # ScreenshotService (Desktop/NOVA Screenshots)
│   ├── eyes/                     # In-memory Quartz/Vision perception engine
│   │   ├── accessibility.py      # macOS AXUIElement accessibility tree traversal
│   │   ├── capture.py            # CGWindowListCreateImage screen grabber
│   │   ├── interaction.py        # Quartz CGEvent mouse/keyboard injector
│   │   ├── manager.py            # NovaEyesManager background polling & proactive checks
│   │   ├── planner.py            # EyesTargetResolver (spatial/label mapping)
│   │   ├── proactive.py          # ProactiveAssistanceEngine (error/opportunity detector)
│   │   ├── state.py              # ScreenState, ProductCandidate, PageCategory data models
│   │   ├── verifier.py           # Pre/post-action UI delta verifier
│   │   └── vision_ocr.py         # Apple VNRecognizeTextRequest / OCR bridge
│   ├── task_agent/               # Autonomous Task Agent V3 subsystem
│   │   ├── executor.py           # TaskExecutor (step dispatch, recovery, replanning)
│   │   ├── models.py             # TaskGoal, TaskPlan, TaskStep, TaskContext data models
│   │   ├── planner.py            # TaskPlanner (LLM goal decomposition into atomic steps)
│   │   ├── registry.py           # CapabilityRegistry (catalog of verified system capabilities)
│   │   └── replanner.py          # DynamicReplanner (automatic failure recovery & alternative plans)
│   └── visual/                   # Visual models & screen analysis wrappers
├── browser/                      # Browser automation subsystem
│   ├── auto_scroll.py            # YouTube Shorts & infinite scroll background driver
│   ├── context.py                # BrowserContextManager (active tabs, page state)
│   ├── engine.py                 # MacOSNativeBrowserEngine (AppleScript Chrome/Safari bridge)
│   ├── extractor.py              # Webpage article & structured text extractor
│   ├── manager.py                # BrowserManager orchestrator
│   ├── models.py                 # BrowserActionPlan, BrowserResult, ActionType
│   ├── parser.py                 # BrowserIntentParser (rule-based action parser)
│   ├── planner.py                # BrowserTaskPlanner (multi-step web research)
│   ├── router.py                 # BrowserActionRouter (dispatches to site skills)
│   ├── safety.py                 # BrowserSafetyPolicy (URL validation & confirmation checks)
│   ├── sessions.py               # BrowserSessionManager (cookie & session preservation)
│   └── sites/                    # Domain-specific web skills
│       ├── amazon.py             # Amazon search, product filtering, price checking
│       ├── github.py             # GitHub repo search & code navigation
│       ├── google.py             # Google Search query builder & result extractor
│       └── youtube.py            # YouTube search, video playback, auto-play next, Shorts
├── desktop/                      # Desktop & filesystem actions
│   ├── apps.py                   # AppLauncher (macOS open/kill/pkill bridge)
│   ├── camera.py                 # CameraManager (Photo Booth, snapshot capture)
│   ├── code.py                   # CodeFileManager (smart code editing & project scaffolding)
│   ├── context.py                # DesktopContext (active project, folder paths)
│   ├── editor.py                 # DocumentEditor (AI document generation & opening)
│   ├── files.py                  # FileSystemManager (multi-root search, safe trash, folder creation)
│   ├── manager.py                # DesktopActionManager orchestrator
│   ├── models.py                 # DesktopActionPlan, DesktopActionResult
│   ├── parser.py                 # DesktopIntentParser
│   ├── planner.py                # DesktopTaskPlanner
│   └── safety.py                 # DesktopSafetyPolicy (path validation & sandbox roots)
├── intent/                       # Natural Language Intent & Routing Engine
│   ├── disambiguator.py          # Disambiguation engine for ambiguous commands
│   ├── engine.py                 # NaturalLanguageIntentEngine (3-tier intent classification)
│   ├── entity_resolver.py        # Entity & parameter extraction (apps, targets, queries)
│   ├── fallback.py               # Conversational LLM fallback wrapper
│   ├── matcher.py                # Fast regex pattern matcher for canonical intents
│   ├── models.py                 # CanonicalIntent enum, StructuredAction dataclass
│   ├── normalizer.py             # Spoken text normalizer (ASR typo correction, numbers)
│   └── router.py                 # RoutingDomain mapper & structured plan converters
├── mac_control/                  # Native macOS system controls
│   ├── manager.py                # MacControlManager orchestrator
│   ├── models.py                 # MacCommand, MacResult, CommandCategory
│   ├── parser.py                 # MacControlParser
│   ├── router.py                 # MacControlRouter
│   └── actions/                  # Subsystem executors
│       ├── bluetooth.py          # Bluetooth status & blueutil toggle bridge
│       ├── brightness.py         # Display brightness query & adjustment
│       ├── clipboard.py          # macOS pbcopy/pbpaste bridge
│       ├── finder.py             # Finder reveal & file selection
│       ├── media.py              # System media key simulation
│       ├── network.py            # Network interface diagnosis
│       ├── screenshot.py         # screencapture CLI executor
│       ├── system.py             # Lock screen & shutdown handlers
│       ├── volume.py             # System audio volume query, set, mute, unmute
│       └── wifi.py               # networksetup Wi-Fi power toggle & SSID query
├── memory/                       # Persistent & Semantic Memory
│   ├── memory_manager.py         # MemoryManager (atomic JSON storage, CRUD, categories)
│   └── vector_store.py           # VectorStore (ChromaDB semantic search with mock fallback)
├── personality/                  # Character & Response Generation
│   ├── emotion_engine.py         # ConversationMode detector (Coding, Study, Casual, etc.)
│   ├── response_orchestrator.py  # Dual-channel response formatting (TTS speech vs Rich display)
│   └── system_prompt.py          # Modular SystemPromptManager & prompt profiles
├── providers/                    # Multi-provider AI Gateway
│   ├── base_provider.py          # BaseProvider abstract base class with stats/timing
│   ├── cerebras.py               # CerebrasCloudProvider (qwen-3.8-27b)
│   ├── gemini.py                 # GeminiProvider (google-genai SDK, gemini-2.5-flash)
│   ├── groq.py                   # GroqProvider (groq SDK, compound-mini)
│   ├── openrouter.py             # OpenRouterProvider (openai SDK, gpt-4o-mini)
│   └── provider_manager.py       # ProviderManager routing priorities & automatic failover
├── ui/                           # Frontend & Visualization
│   ├── doctor.py                 # Rich CLI diagnostic doctor suite
│   ├── health_checker.py         # DashboardStatsManager activity & latency tracker
│   ├── terminal_dashboard.py     # Rich terminal activity feed & telemetry UI
│   ├── backend/                  # Async WebSocket & HTTP REST server
│   │   ├── command_gateway.py    # UI -> Core turn queue command bridge
│   │   ├── event_bridge.py       # EventBus -> WebSocket client broadcaster
│   │   ├── launcher.py           # Background subprocess launcher for Electron/UI
│   │   ├── models.py             # Pydantic models for UI events, commands, avatar state
│   │   └── server.py             # Python asyncio HTTP REST & WebSocket server (127.0.0.1:8765)
│   └── desktop/                  # Electron + React 18 + Vite + Tailwind desktop app
│       ├── electron/main.cjs     # Electron main process (frameless window, IPC)
│       └── src/                  # React UI components (Avatar, Screens, TopBar, Sidebar)
├── voice/                        # Voice V2 Audio Pipeline
│   ├── audio_events.py           # Non-speech acoustic detector (cough, laugh, sneeze, sigh)
│   ├── commands.py               # Local keyword recognizer & fast voice command router
│   ├── diagnostics.py            # Audio hardware & PortAudio diagnostic checks
│   ├── listener.py               # VoiceListener background audio recording thread
│   ├── manager.py                # VoiceManager orchestrator
│   ├── microphone.py             # PyAudio stream manager
│   ├── preprocessing.py          # RMS normalization & silence trimming
│   ├── quality.py                # TranscriptQualityGate (hallucination & noise filter)
│   ├── speaker.py                # Edge-TTS / Pygame / Kokoro audio playback
│   ├── state.py                  # VoiceState, TranscriptionResult, SpeechOutputResult
│   ├── transcriber.py            # Faster-Whisper localized speech-to-text
│   └── vad.py                    # Silero VAD energy & voice activity detector
└── main.py                       # NovaApplication entry point, turn queue loop, graceful shutdown
```

---

## 3. Subsystem Deep Dives

### 3.1 Orchestration Loop (`main.py`)
`NovaApplication` acts as the primary coordinator:
- **Startup:** Initializes subsystems in parallel threads (`_initialize_memory`, `_initialize_providers`, `_initialize_personality`, `_initialize_mac_control`, `_initialize_desktop`, `_initialize_browser`, `_initialize_computer_agent`).
- **Turn Queue (`_turn_queue`):** Consumes `TurnRequest` instances from voice or typed input.
- **Turn Execution Pipeline:**
  1. Environment snapshot capture via `EnvironmentObserver.refresh()`.
  2. Pending confirmation resolution (e.g. confirming file deletion or shutdown).
  3. Local voice command intercept (e.g. immediate local shutdown or cancellation).
  4. Layered intent parsing via `NaturalLanguageIntentEngine`.
  5. Action dispatch to the designated domain (`TASK_AGENT`, `BROWSER`, `DESKTOP_APP`, `FILESYSTEM`, `DOCUMENT_WRITING`, `SYSTEM`, `VISUAL`).
  6. Conversational fallback via `ProviderManager.generate_response()` with personality and memory injection.
  7. Response orchestration via `ResponseOrchestrator` separating clean spoken audio for TTS from rich formatted text for UI.

### 3.2 AI Providers (`providers/`)
- **Base Interface:** `BaseProvider` enforces `generate_response()`, `stream_response()`, `health_check()`, `initialize()`, and `shutdown()`.
- **Automatic Routing Priority:**
  - **CODING:** Gemini $\to$ Groq $\to$ OpenRouter $\to$ Cerebras
  - **REASONING:** Gemini $\to$ OpenRouter $\to$ Groq $\to$ Cerebras
  - **FAST:** Groq $\to$ Cerebras $\to$ Gemini $\to$ OpenRouter
  - **CHEAP:** Cerebras $\to$ Groq $\to$ Gemini $\to$ OpenRouter
  - **GENERAL:** Gemini $\to$ Groq $\to$ OpenRouter $\to$ Cerebras
- **Failover:** If a provider raises `AIProviderError` (e.g. rate limit 429, timeout, network failure), `ProviderManager` automatically catches it, records the error, and falls back to the next provider in the priority list.

### 3.3 Voice V2 Subsystem (`voice/`)
- **Capture:** `MicrophoneManager` streams 16kHz mono audio via `PyAudio`.
- **VAD:** `VoiceActivityDetector` uses energy thresholding and Silero VAD parameters to segment utterances.
- **ASR:** `TranscriptionManager` runs localized `faster-whisper` (default model: `small.en` / `base`), generating text hypotheses, confidence scores, and alternative candidates.
- **Audio Event Detection:** `AudioEventDetector` intercepts acoustic patterns (coughs, sneezes, laughter, sighs) to trigger caring responses without conversational LLM overhead.
- **TTS:** `SpeakerManager` generates speech using Microsoft `edge-tts` (voice: `hi-IN-SwaraNeural` or customizable) or native `pyttsx3`/Kokoro fallback.

### 3.4 Perception & Computer Control (`core/eyes/`, `core/computer_agent.py`)
- **Observation:** `NovaEyesManager` captures Retina screen frames directly into memory using Quartz `CGWindowListCreateImage` and extracts text bounding boxes with Apple Vision OCR (`VNRecognizeTextRequest`).
- **Accessibility:** `AccessibilityInspector` traverses macOS `AXUIElement` trees to identify buttons, text inputs, windows, and modal popups.
- **ComputerAgent Loop:** `SEE -> UNDERSTAND -> PLAN -> ACT -> OBSERVE AGAIN -> VERIFY`.
- **Quartz Interaction:** Injects hardware-level mouse clicks, scrolling, and keyboard events using macOS `CGEventCreateMouseEvent` and `CGEventCreateKeyboardEvent`.

### 3.5 Autonomous Task Agent V3 (`core/task_agent/`)
- **Goal Decomposition:** `TaskPlanner` uses LLM reasoning to decompose complex goals into discrete `TaskStep` definitions with dependencies.
- **Execution:** `TaskExecutor` executes each step through `CapabilityRegistry`, verifying postconditions via registered verifiers.
- **Dynamic Replanning:** `DynamicReplanner` intercepts step failures, analyzes the error context and current screen state, and generates adaptive alternative steps (up to `max_replans=3`).

### 3.6 UI & Communication Bridge (`ui/`)
- **Backend Server:** `NovaUIServer` runs an `asyncio` HTTP REST and WebSocket server on `127.0.0.1:8765`.
- **Command Gateway:** `CommandGateway` funnels UI inputs directly into `NovaApplication._turn_queue`.
- **Event Bridge:** `EventBridge` subscribes to `NovaEvent` on the `EventBus` and broadcasts structured JSON payloads to all connected WebSocket clients.
- **Frontend:** React 18 + TypeScript + Vite desktop client wrapped in Electron with interactive Avatar states (`IDLE`, `LISTENING`, `THINKING`, `PLANNING`, `EXECUTING`, `SPEAKING`, `SUCCESS`, `ERROR`).

---

## 4. Invariants for Future Autonomous Development

When building future autonomous capabilities on top of NOVA:
1. **Never reinvent browser automation:** Reuse `BrowserManager` and `MacOSNativeBrowserEngine`.
2. **Never reinvent mouse/keyboard control:** Reuse `ComputerAgent` and `EyesInteractionManager`.
3. **Never bypass safety policies:** Always respect `DesktopSafetyPolicy` and `BrowserSafetyPolicy`.
4. **Never create secondary AI provider clients:** Route all model queries through `ProviderManager`.
5. **Never expose or hardcode secrets:** Adhere strictly to `config.settings.settings`.
