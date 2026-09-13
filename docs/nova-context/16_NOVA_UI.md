# 16 — NOVA Frontend, Electron, & Backend Architecture

## Overview
NOVA features a modern dual-UI layer:
1. **Interactive Desktop App:** Built with Electron, React 18, TypeScript, Tailwind CSS, Lucide icons, and Vite.
2. **Terminal Operations Dashboard:** Built with Python `rich`, providing an interactive activity feed, latency tracking, and command console.

---

## 🖥️ Desktop Application Architecture (`ui/desktop/`)
- **Main Process (`electron/main.cjs`):** Manages native frameless window, titlebar, transparency, and IPC.
- **Frontend Core (`src/App.tsx`):** Maintains WebSocket connection to `ws://127.0.0.1:8765`, streaming real-time avatar states and activity blocks.
- **Interactive Avatar (`src/components/Avatar/NovaAvatar.tsx`):** Dynamic reactive orb displaying animated visual states:
  - `IDLE`: Subtle breathing glow.
  - `LISTENING`: Active audio frequency pulse.
  - `THINKING`: Rapid rotating particle halo.
  - `PLANNING`: Multi-node geometric matrix.
  - `EXECUTING`: Concentric progress wave.
  - `SPEAKING`: Expressive voice amplitude wave.
  - `SUCCESS`: Radiant emerald flash.
  - `ERROR`: Crimson warning pulse.
- **Screens:**
  - `HomeScreen`: Quick actions, system status, active avatar.
  - `ChatScreen`: Full conversational history with dual speech/display rendering.
  - `TasksScreen`: Autonomous multi-step task tracker with step progress bars and replanning logs.
  - `VoiceScreen`: Voice V2 audio diagnostics, mic levels, and transcript logs.
  - `ActivityScreen`: Real-time audit log of all system actions, resolutions, and outcomes.
  - `SystemScreen`: Hardware metrics, AI provider status, and latency charts.
  - `PermissionsScreen`: macOS permission diagnostic checklist.
  - `SettingsScreen`: Theme, voice selection, and provider preferences.

---

## 🔌 UI Backend Gateway (`ui/backend/`)
- **`server.py`:** Asyncio HTTP REST and WebSocket server.
- **`command_gateway.py`:** Funnels UI text/voice commands into `NovaApplication._turn_queue`.
- **`event_bridge.py`:** Translates `NovaEvent` from `EventBus` into WebSocket broadcasts.
