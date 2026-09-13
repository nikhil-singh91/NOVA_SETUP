# 01 — NOVA Macro Architecture & Lifecycle

## Architecture Overview
NOVA follows a layered, modular, event-driven architecture designed for local-first execution on macOS.

```
                    ┌──────────────────────────────────────────────┐
                    │               USER INTERFACES                │
                    │  React 18 Desktop App / Electron / Terminal  │
                    └──────────────────────┬───────────────────────┘
                                           │ WebSocket / REST (127.0.0.1:8765)
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             NOVA APPLICATION CORE                                │
│                                                                                  │
│  ┌────────────────────────┐  ┌───────────────────────┐  ┌─────────────────────┐  │
│  │    Turn Queue Loop     │  │   Service Lifecycle   │  │   EventBus (PubSub) │  │
│  │   `NovaApplication`    │  │  `ServiceLifecycle`   │  │     `NovaEvent`     │  │
│  └───────────┬────────────┘  └───────────────────────┘  └─────────────────────┘  │
│              │                                                                   │
│              ▼                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                   PERCEPTION & CONTEXT ENGINE (EYES)                       │  │
│  │  • `EnvironmentObserver` (Active App, Window, Tab, URL, Finder Selection)   │  │
│  │  • `ContextResolver` (Deterministic "this" / "that" pronoun resolution)    │  │
│  │  • `NovaEyesManager` (In-memory Quartz Retina capture + Apple Vision OCR)  │  │
│  │  • `RecentInteractionContext` (10-turn verified interaction history)       │  │
│  └─────────────────────────────────────┬──────────────────────────────────────┘  │
│                                        │                                         │
│                                        ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                     LAYERED INTENT & ROUTING ENGINE                        │  │
│  │  • Fast Regex Matcher -> CanonicalIntent Matcher -> Entity Extractor      │  │
│  │  • Fallback to AI Provider for high-level semantic reasoning               │  │
│  └─────────────────────────────────────┬──────────────────────────────────────┘  │
│                                        │                                         │
│                                        ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                     CAPABILITY & EXECUTION LAYER (HANDS)                   │  │
│  │                                                                            │  │
│  │  ┌───────────────────┐ ┌───────────────────┐ ┌──────────────────────────┐  │  │
│  │  │  Browser Manager  │ │  Computer Agent   │ │ Autonomous Task Agent V3 │  │  │
│  │  │  (Chrome/Safari)  │ │ (Quartz / Mouse)  │ │ (Planner, Replanner, Ex) │  │  │
│  │  └───────────────────┘ └───────────────────┘ └──────────────────────────┘  │  │
│  │  ┌───────────────────┐ ┌───────────────────┐ ┌──────────────────────────┐  │  │
│  │  │  Desktop Manager  │ │  macOS Control    │ │ Memory & Vector Store    │  │  │
│  │  │ (Files, Apps, Doc)│ │ (Vol, Bright, Net)│ │ (JSON + ChromaDB)        │  │  │
│  │  └───────────────────┘ └───────────────────┘ └──────────────────────────┘  │  │
│  └─────────────────────────────────────┬──────────────────────────────────────┘  │
│                                        │                                         │
│                                        ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                    MULTI-PROVIDER AI BRAIN (REASONING)                     │  │
│  │  • `ProviderManager` (Gemini, Groq, OpenRouter, Cerebras)                  │  │
│  │  • Automatic Task Routing (Coding, Reasoning, Fast, Cheap, General)        │  │
│  │  • Instant fallback & rate limit recovery                                  │  │
│  └─────────────────────────────────────┬──────────────────────────────────────┘  │
│                                        │                                         │
│                                        ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                   RESPONSE ORCHESTRATION & DELIVERY                        │  │
│  │  • `ResponseOrchestrator`: Cleans markdown & emits dual-channel output:    │  │
│  │    1. Rich UI Display Text -> Activity Feed / Terminal                     │  │
│  │    2. Natural Spoken Audio -> Edge-TTS / Kokoro Voice Output               │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Subsystem Threading Model
- **Main Thread:** Executes the `_run_event_loop()` draining `_turn_queue`.
- **Background Worker Threads:**
  - `nova-console-input`: Listens for terminal typed commands and slash-commands.
  - `voice-listener`: Continuous PyAudio streaming and Silero VAD analysis.
  - `nova-ui-server`: Asyncio event loop running HTTP REST + WebSocket server on port 8765.
  - `nova-eyes-polling`: Passive proactive perception monitor for screen errors.
- **Locking:** All shared resources utilize `threading.RLock` or `threading.Lock` to prevent race conditions.
