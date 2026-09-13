# 02 — NOVA Capabilities & Reachability Map

## Overview
NOVA contains 35+ first-class capabilities accessible via text, voice, and autonomous task agent plans.

### 1. System Hardware Controls (`mac_control/actions/`)
- **Volume:** `increase volume`, `decrease volume`, `set volume to X%`, `mute`, `unmute`, `get volume`.
  - Executed via AppleScript `set volume output volume X`.
- **Brightness:** `increase brightness`, `decrease brightness`, `set brightness to X%`, `check brightness`.
  - Executed via native `brightness` CLI or AppleScript display service.
- **Wi-Fi:** `is wi-fi on`, `turn wi-fi on`, `turn wi-fi off`, `what wi-fi am i connected to`.
  - Executed via macOS `networksetup -setairportpower`.
- **Bluetooth:** `check bluetooth status`, `turn bluetooth on/off`.
  - Executed via `blueutil` CLI with native fallback.
- **Clipboard:** `what is in my clipboard`, `clear clipboard`, `copy this to clipboard`.
  - Executed via macOS `pbcopy` and `pbpaste`.
- **Lock Screen & Shutdown:** `lock my mac`, `shut down my mac`.
  - System shutdown requires explicit spoken/typed confirmation.

### 2. Application & Desktop Controls (`desktop/`)
- **App Launcher (`AppLauncher`):** Launches and closes applications (e.g. VS Code, Chrome, Safari, Terminal, Telegram, Spotify, TextEdit).
- **Camera (`CameraManager`):** Opens Photo Booth viewfinder and takes snapshot photos saved to `~/Pictures/NOVA`.
- **Filesystem (`FileSystemManager`):** Safe multi-root search across Desktop, Documents, Downloads, Projects, and Workspace. Creates folders, creates files, and safely moves items to macOS Trash.
- **AI Document Editor (`DocumentEditor`):** Uses AI Provider to generate structured notes/essays and automatically creates and opens them in TextEdit.

### 3. Native Browser Automation (`browser/`)
- **Browser Engines:** Chrome and Safari via `MacOSNativeBrowserEngine` (AppleScript).
- **Navigation & Search:** `open <url>`, `search Google for <query>`, `search <site> for <query>`.
- **Tab Management:** `open a new tab`, `search inside this tab`, `close tab`, `switch to tab N`.
- **Media Skills:** YouTube playback, search artist/song, auto-play next, YouTube Shorts auto-scrolling (`YouTubeShortsScroller`).
- **Web Extraction:** Reads and extracts article text, summaries, and structured content from generic webpages (`WebpageExtractor`).

### 4. NOVA Eyes & Computer Control (`core/eyes/`, `core/computer_agent.py`)
- **Vision & OCR:** In-memory Retina screen grabs (`CGWindowListCreateImage`) with Apple Vision framework OCR (`VNRecognizeTextRequest`).
- **Accessibility:** Queries active windows, UI buttons, and input fields via `AXUIElement`.
- **UI Interaction:** Clicks UI buttons by label, types text into active focus, closes popups, and scrolls viewports until target text is found.
- **Screen Understanding:** `what am I looking at`, `explain this error`, `summarize this page`, `what is at my cursor`.

### 5. Multi-Step Task Planning (`core/task_agent/`)
- **Task Planner:** Decomposes complex natural language instructions into ordered steps.
- **Task Executor:** Executes steps sequentially with verification and cancellation support.
- **Dynamic Replanner:** Automatically analyzes errors, inspects screen state, and generates alternative plans when steps fail.
