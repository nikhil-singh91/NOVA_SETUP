# NOVA Unreachable & Partially Reachable Features Audit

---

## 1. Executive Summary

This document catalogs components in the NOVA codebase where functional implementation exists, but the feature is either:
1. **Unreachable directly from primary intent classification** (relying on secondary fallback chains).
2. **Missing a high-level `CanonicalIntent` mapping**.
3. **Implemented in legacy subsystems that have been superseded by newer engines**.

---

## 2. Unreachable & Indirect Features Inventory

### 1. Camera Actions (`desktop/camera.py`)
- **Where Code Exists**: `desktop/camera.py` (`CameraManager.open_camera()`, `CameraManager.capture_photo()`).
- **Why It Is Indirectly Reachable**:
  - `intent/models.py` does not define `CanonicalIntent.OPEN_CAMERA` or `CanonicalIntent.TAKE_PHOTO`.
  - `intent/matcher.py` does not have an explicit pattern for camera requests.
  - User commands such as `"Open camera"` or `"Take a photo"` fall back to `CanonicalIntent.GENERAL_CONVERSATION`, which then falls through to `DesktopActionManager.process_input()` where regex matching succeeds.
- **What Is Missing**: Dedicated canonical intents (`OPEN_CAMERA`, `TAKE_PHOTO`) in `intent/models.py` and `intent/matcher.py`.
- **Recommended Action**: **CONNECT** — Add canonical intent mapping in V4 so camera commands bypass fallback latency.

---

### 2. Native Bluetooth & Wi-Fi Toggles (`mac_control/actions/bluetooth.py`, `mac_control/actions/wifi.py`)
- **Where Code Exists**: `mac_control/actions/bluetooth.py`, `mac_control/actions/wifi.py`.
- **Why It Is Indirectly Reachable**:
  - No `CanonicalIntent.CONTROL_BLUETOOTH` or `CanonicalIntent.CONTROL_WIFI` in the primary intent engine.
  - Reachable only if `MacControlManager.process_input()` intercepts the raw string in fallback mode.
- **What Is Missing**: First-class canonical intents and structured intent routing.
- **Recommended Action**: **CONNECT** or **DEPRECATE** — Connect to unified intent engine or leave as secondary fallback.

---

### 3. Clipboard Inspection & Manipulation (`mac_control/actions/clipboard.py`)
- **Where Code Exists**: `mac_control/actions/clipboard.py` (`get_clipboard()`, `set_clipboard()`, `clear_clipboard()`).
- **Why It Is Not Reachable from Voice**:
  - No natural language intent exists in `intent/matcher.py` for reading/writing clipboard text.
- **What Is Missing**: Intent matcher rules for `"What is in my clipboard?"`, `"Copy this to clipboard"`.
- **Recommended Action**: **CONNECT** — Expose clipboard tools to Autonomous Task Agent capability registry and intent engine.

---

### 4. Local Command Router Cancel Handler (`voice/commands.py`)
- **Where Code Exists**: `voice/commands.py` (`CommandRecognizer` defines `"cancel": ["cancel", "stop", "nevermind", "रहने दो", "रुको"]`).
- **Why It Is Not Reached in CommandRouter**:
  - In `main.py` line 134, only `self.command_router.register_handler("shutdown", ...)` is registered.
  - The `"cancel"` local handler is not registered in `VoiceCommandRouter`.
  - *Note*: `"Stop"` and `"Cancel"` are still fully functional and handled immediately via `intent_engine.parse()` $\rightarrow$ `CanonicalIntent.CANCEL_ACTION`.
- **What Is Missing**: Registering the local cancel callback in `VoiceCommandRouter` for sub-millisecond local bypass.
- **Recommended Action**: **CONNECT** — Wire `self.command_router.register_handler("cancel", ...)` in `main.py`.

---

### 5. Unused `plugins/` and `models/` Directories
- **Where Code Exists**: `/Users/nikhilsingh/Desktop/NOVA_SETUP/plugins/` and `/Users/nikhilsingh/Desktop/NOVA_SETUP/models/`.
- **Why It Is Not Reachable**:
  - Both directories are currently empty directories on disk.
  - Models were organized modularly within each subsystem (`desktop/models.py`, `browser/models.py`, `core/task_agent/models.py`).
- **Recommended Action**: **RETAIN AS PLACEHOLDER** — Keep `plugins/` for upcoming Skills & Integrations V4 architecture.
