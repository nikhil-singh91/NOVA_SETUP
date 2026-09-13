# NOVA Reuse Matrix

This matrix establishes the engineering policy for how future autonomous agents and modules must interact with existing NOVA subsystems.

---

## 📊 Subsystem Reuse & Integration Table

| NOVA Subsystem | Architecture Action | Preferred Entry Point / Class | Do NOT Duplicate | Rationale & Integration Rules |
| :--- | :--- | :--- | :--- | :--- |
| **AI Providers** | **REUSE DIRECTLY** | `providers.provider_manager.ProviderManager` | ❌ DO NOT CREATE new LLM clients | Centralizes token stats, rate limiting, and automatic fallback across Gemini, Groq, OpenRouter, Cerebras. |
| **Memory System** | **REUSE DIRECTLY** | `memory.memory_manager.MemoryManager` | ❌ DO NOT CREATE separate storage | Atomic JSON storage with category partitioning (`coding`, `projects`, `conversations`) and quarantine resilience. |
| **Semantic Search** | **WRAP / ADAPT** | `memory.vector_store.VectorStore` | ❌ DO NOT CREATE vector engines | Provides ChromaDB semantic document retrieval with in-memory fallback. |
| **Voice V2 (STT/TTS)**| **REUSE DIRECTLY** | `voice.manager.VoiceManager` | ❌ DO NOT CREATE new audio pipelines | Integrates PyAudio, Silero VAD, Faster-Whisper, and Edge-TTS into an event-synchronized pipeline. |
| **Audio Events** | **REUSE DIRECTLY** | `voice.audio_events.AudioEventDetector` | ❌ DO NOT REBUILD | Acoustic detection for coughs, sneezes, laughter, and sighs with empathetic responses. |
| **Browser Engine** | **REUSE DIRECTLY** | `browser.engine.MacOSNativeBrowserEngine` | ❌ DO NOT CREATE browser drivers | Native AppleScript control for Chrome/Safari tabs, URLs, DOM extraction, and search. |
| **Browser Manager** | **REUSE DIRECTLY** | `browser.manager.BrowserManager` | ❌ DO NOT REBUILD browser routers | Coordinates browser skills (YouTube, Amazon, Google, GitHub, generic) and multi-step research. |
| **Auto-Scroll Engine**| **REUSE DIRECTLY** | `browser.auto_scroll.YouTubeShortsScroller` | ❌ DO NOT REBUILD | Non-blocking thread-safe scrolling for YouTube Shorts and web feeds. |
| **Computer Agent** | **WRAP / ADAPT** | `core.computer_agent.ComputerAgent` | ❌ DO NOT CREATE mouse/keyboard code | Full `SEE -> UNDERSTAND -> PLAN -> ACT -> VERIFY` loop using Quartz & Accessibility. |
| **NOVA Eyes (Perception)** | **REUSE DIRECTLY** | `core.eyes.manager.NovaEyesManager` | ❌ DO NOT STREAM screen to cloud | In-memory Retina screen capture (`CGWindowListCreateImage`) and Apple Vision OCR. |
| **Environment Observer** | **REUSE DIRECTLY** | `core.environment.EnvironmentObserver` | ❌ DO NOT REBUILD OS state monitors | Real-time frontmost app, window title, active URL, and Finder selection queries via AppleScript. |
| **Context Resolver** | **REUSE DIRECTLY** | `core.environment.ContextResolver` | ❌ DO NOT REBUILD pronoun logic | Deterministically resolves "this", "that", "it", "here" to active files, tabs, or apps. |
| **Recent Interaction Context** | **REUSE DIRECTLY** | `core.context.RecentInteractionContext` | ❌ DO NOT CREATE turn history buffers | Tracks bounded 10-turn interaction history, verified targets, and search queries. |
| **Task Planner** | **EXTEND** | `core.task_agent.planner.TaskPlanner` | ❌ DO NOT REBUILD step models | LLM-driven task goal decomposition into atomic `TaskStep` chains. Future agents can register domain prompts. |
| **Task Executor** | **REUSE DIRECTLY** | `core.task_agent.executor.TaskExecutor` | ❌ DO NOT REBUILD execution runners | Executes plans step-by-step with timeout handling, cancellation checks, and pre/post verification. |
| **Task Replanner** | **REUSE DIRECTLY** | `core.task_agent.replanner.DynamicReplanner` | ❌ DO NOT REBUILD recovery loops | Automatically generates recovery plans when a step fails based on real-time screen inspection. |
| **Capability Registry**| **EXTEND** | `core.task_agent.registry.CapabilityRegistry` | ❌ DO NOT HARDCODE capabilities | Central registry for all executable tools (`fs.*`, `browser.*`, `visual.*`, `system.*`). |
| **Desktop Actions** | **REUSE DIRECTLY** | `desktop.manager.DesktopActionManager` | ❌ DO NOT REBUILD app launchers | Manages app launch/close (`AppLauncher`), camera (`CameraManager`), and AI docs (`DocumentEditor`). |
| **Filesystem Manager**| **REUSE DIRECTLY** | `desktop.files.FileSystemManager` | ❌ DO NOT WRITE unsafe file tools | Multi-root search, safe trash integration, overwrite protection, and folder creation. |
| **macOS Control** | **REUSE DIRECTLY** | `mac_control.manager.MacControlManager` | ❌ DO NOT REBUILD system scripts | Native control for volume, brightness, Wi-Fi, Bluetooth, clipboard, lock screen, and shutdown. |
| **EventBus** | **REUSE DIRECTLY** | `core.event_bus.EventBus` | ❌ DO NOT CREATE secondary buses | Central thread-safe publish/subscribe bus for all lifecycle, voice, task, and UI events. |
| **UI Server & Gateway**| **REUSE DIRECTLY** | `ui.backend.server.NovaUIServer` | ❌ DO NOT CREATE new web servers | Async WebSocket and HTTP REST gateway on `127.0.0.1:8765` bridging UI and core. |
| **Safety Policies** | **REUSE DIRECTLY** | `desktop.safety.DesktopSafetyPolicy` | ❌ NEVER BYPASS safety checks | Sandboxing, destructive action confirmations, and dangerous URL blocking. |
