# 21 — NOVA Startup, Bootstrap, & Lifecycle Management

## Overview
NOVA initializes subsystems via parallel threading during bootstrap to minimize startup latency, registers teardown handlers with `ServiceLifecycle`, and ensures graceful state persistence on exit.

---

## 🚀 Startup Sequence (`main.py`)
```
1. Bootstrap & Logging:
   - `setup_logging()` configures structured logger.
   - `lifecycle.start()` initializes ServiceLifecycle registry.
   - `EventBus` singleton instantiated and registered.

2. Parallel Subsystem Initializations (Worker Threads):
   ├── Thread 'nova-init-memory': MemoryManager, VectorStore index population.
   ├── Thread 'nova-init-providers': ProviderManager, AI API clients.
   ├── Thread 'nova-init-personality': SystemPromptManager, EmotionEngine.
   ├── Thread 'nova-init-mac_control': MacControlManager.
   ├── Thread 'nova-init-desktop': DesktopActionManager, CameraManager.
   ├── Thread 'nova-init-browser': BrowserManager, MacOSNativeBrowserEngine.
   └── Thread 'nova-init-computer_agent': ComputerAgent, NovaEyesManager perception loop.

3. Voice V2 Initialization:
   - Initializes Microphone, VAD, Faster-Whisper, and Speaker.
   - Determines `voice_available` boolean.

4. Signal Handlers:
   - Registers SIGINT and SIGTERM handlers to trigger graceful shutdown.

5. Terminal Operations Dashboard:
   - Renders Rich terminal overview (`TerminalDashboard.render()`).

6. Context-Aware Startup Greeting:
   - Queries last active project from `MemoryManager`.
   - Generates and delivers natural startup greeting via active AI provider.
   - Publishes `NovaEvent.APPLICATION_STARTED`.

7. Engage Background Workers:
   - Starts typed console thread (`_console_input_loop`).
   - Starts Voice V2 continuous listening loop.
   - Enters main `_run_event_loop()` draining `_turn_queue`.
```

---

## 🛑 Graceful Shutdown Sequence
```
1. Capture Session Breadcrumb:
   - Writes `last_session_summary` (project, last topic, session duration) to Memory.

2. Stop Audio & Background Services:
   - Stops VoiceListener and terminates PyAudio streams.
   - Stops NovaEyes perception loop and video recorders.

3. Close External Connections:
   - Shuts down AI provider client sessions and WebSocket streams.

4. Lifecycle Teardown:
   - Publishes `NovaEvent.APPLICATION_SHUTDOWN`.
   - Invokes all registered teardown callbacks via `lifecycle.shutdown()`.
```
