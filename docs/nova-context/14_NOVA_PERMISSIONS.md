# 14 — macOS Permissions & System Privileges

## Overview
NOVA utilizes standard macOS system capabilities. Operating these capabilities requires specific user grants in **System Settings $\to$ Privacy & Security**.

---

## 🔑 Required macOS Permissions

| Permission | Subsystem / Feature | Required For | Verification Mechanism |
| :--- | :--- | :--- | :--- |
| **Accessibility (`AXUIElement`)** | `core.eyes`, `core.computer_agent` | Inspecting window hierarchies, finding UI buttons, and injecting Quartz clicks | `ApplicationServices.AXIsProcessTrusted()` |
| **Screen Recording (`CGWindowListCreateImage`)** | `core.eyes`, `core.screenshot`, `core.screen_recording` | In-memory frame capture for OCR and visual analysis | Checked at capture time (returns empty/wallpaper if denied) |
| **Microphone** | `voice.microphone`, `voice.manager` | PyAudio 16kHz audio stream capture | Checked during audio stream initialization |
| **Automation / AppleEvents** | `browser.engine`, `desktop.apps`, `mac_control` | AppleScript control of Chrome, Safari, Finder, and System Events | `osascript -e 'tell application "System Events"...'` |
| **Camera** | `desktop.camera` | Photo Booth launch and snapshot photography | OS permission prompt on first launch |
| **Files & Folders** | `desktop.files`, `memory.memory_manager` | Reading/writing in Desktop, Documents, and Downloads | Standard POSIX filesystem permission checks |

---

## 🩺 Permissions Diagnostic
The Permissions screen in the Electron UI (`ui/desktop/src/screens/PermissionsScreen.tsx`) and the CLI Doctor (`ui/doctor.py`) provide live status indicators and step-by-step setup guides for any missing macOS permissions.
