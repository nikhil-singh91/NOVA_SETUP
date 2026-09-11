# NOVA UI V1 Architecture & Integration Guide

---

## 1. System Overview

**NOVA UI V1** provides a modern, responsive, glassmorphic desktop interface for the NOVA AI personal assistant. It is decoupled from the Python backend through a dedicated integration layer (`ui/backend/`) and connected via a local real-time WebSocket and HTTP REST bridge (`127.0.0.1:8765`).

```text
┌─────────────────────────────────────────────────────────────┐
│                    NOVA Desktop UI (React 18 + TS)          │
│  ┌──────────────┬────────────────────────────────────────┐  │
│  │ Navigation   │ Screens:                               │  │
│  │ • Home       │ • Expressive Female AI Avatar          │  │
│  │ • Chat       │ • Real-time Voice Audio Visualizer     │  │
│  │ • Voice      │ • Multi-Step Task Agent Tracker        │  │
│  │ • Tasks      │ • Activity Timeline                    │  │
│  │ • Activity   │ • Privacy Bar (Mic/Cam/Screen)         │  │
│  │ • Settings   │ • macOS Security Dashboard             │  │
│  │ • Security   │                                        │  │
│  └──────────────┴────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │ WebSocket / REST (127.0.0.1:8765)
┌──────────────────────────────▼──────────────────────────────┐
│                    UI Integration Layer                     │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │   Command Gateway     │       │     Event Bridge      │  │
│  │ (Validation & Routing)│       │ (Sanitization & Sync) │  │
│  └───────────┬───────────┘       └───────────▲───────────┘  │
└──────────────┼───────────────────────────────┼──────────────┘
               │ TurnRequest                   │ NovaEvent
┌──────────────▼───────────────────────────────┴──────────────┐
│                    NOVA Python Core Engine                  │
│  • Voice V2 (Silero + Whisper + Kokoro TTS)                 │
│  • Natural Language Intent Engine                           │
│  • Autonomous Task Agent V3 (Decomposition & Replanning)    │
│  • Computer Agent V2 (Visual OCR & Click Target Resolver)   │
│  • Desktop Actions V1 & Browser Actions V2                  │
│  • Mac Control (Hardware, System & Safety Interceptors)     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Decoupled UI Integration Layer (`ui/backend/`)

- **`models.py`**: Pydantic data schemas defining `AvatarState` (11 states), `UIEvent` envelopes, `PrivacyState`, and `CommandRequest`.
- **`event_bridge.py`**: Subscribes to the central `EventBus`, filters out private credentials/keys, and broadcasts structured events to connected WebSocket clients.
- **`command_gateway.py`**: Enqueues user text commands or push-to-talk triggers into `NovaApplication._turn_queue` without bypassing confirmation policies.
- **`server.py`**: Async WebSocket & HTTP REST server running on `127.0.0.1:8765`.
- **`launcher.py`**: Process entry point for starting the UI gateway and backend loop.

---

## 3. Desktop Shell & React Frontend (`ui/desktop/`)

- **React 18 + TypeScript + Vite**: Ultra-fast component rendering with minimal CPU overhead.
- **Electron macOS Shell**: Frameless glassmorphic native desktop window (`1180x780`) with native title bar integration.
- **Avatar Engine (`NovaAvatar.tsx`)**: Layered vector SVG with animated breathing, saccadic eye movements, dynamic eyelids (blinking), reactive eyebrows, and speech lip-sync simulation across 11 states.
