# 12 — NOVA Automation Systems & Triggers

## Overview
Automation in NOVA extends beyond manual commands to encompass proactive triggers, event-driven perception, background auto-scrolling, and multi-step background workflows.

---

## ⚙️ Active Automation Subsystems

### 1. Proactive Perception Engine (`core.eyes.proactive.ProactiveAssistanceEngine`)
- **Background Screen Monitor:** Periodically inspects active windows for high-urgency errors, compiler exceptions, crashed processes, or unhandled dialogs.
- **Delivery:** Dispatches non-intrusive proactive assistance cards (`ProactiveOpportunity`) to the UI activity feed without interrupting active voice speech.

### 2. Auto-Scroll Automation (`browser.auto_scroll.YouTubeShortsScroller`)
- **Threaded Auto-Scroller:** Executes in a dedicated background daemon thread.
- **Dynamic Controls:** Supports `start`, `pause`, `resume`, and `stop` commands via text or voice.
- **Interval Control:** Configurable via `BROWSER_AUTO_SHORTS_INTERVAL_SECONDS`.

### 3. Screen Recording Subsystem (`core.screen_recording.ScreenRecordingManager`)
- **Background Capture:** Starts and stops macOS screen video recording saved to `~/Desktop/NOVA Recordings`.
- **Telemetry:** Automatically reports start/stop status to `DashboardStatsManager` and EventBus.

### 4. Background Server Daemons
- **UI Async Server:** Python `asyncio` server running on port 8765.
- **Voice Listener Worker:** Continuous audio streaming thread with VAD energy detection.
- **Console Input Worker:** Interactive terminal listener with slash-command capabilities (`/filter`, `/mode`, `/search`, `/scroll`, `/copy`, `/clear`).
