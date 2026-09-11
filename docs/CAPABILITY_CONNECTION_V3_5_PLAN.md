# NOVA V3.5 Capability Connection & Natural Language Expansion Implementation Plan

---

## 1. Executive Strategy

The objective of **NOVA V3.5** is to:
1. **Connect Existing Capabilities**: Promote existing functionality (Camera, Clipboard, Wi-Fi, Bluetooth, Local Cancel) into first-class canonical intents with structured routing and verification.
2. **Expand Natural Language Reachability**: Enable fluid conversational variants (`"Can you open VS Code"`, `"Hey NOVA, launch Chrome"`, `"Take my picture"`, `"What's in my clipboard?"`, `"Turn off Wi-Fi"`) without altering core arguments.
3. **Register Validated Tools with Task Agent V3**: Expose safe, validated capabilities (`camera.open_camera`, `camera.take_photo`, `clipboard.get`, `clipboard.set`, `clipboard.clear`, `system.wifi`, `system.bluetooth`, `screen.record_start`, `screen.record_stop`) to `CapabilityRegistry`.
4. **Preserve Subsystem Architecture**: Retain 100% of working Voice V2, Browser Actions, Desktop Actions, Environment Awareness V1, Computer Agent V2, and Task Agent V3.

---

## 2. Prioritized Capability Connection Plan

### Priority 1: Implemented But Not Reliably Reachable

#### 1. Camera Capabilities
- **Capability**: `OPEN_CAMERA`, `TAKE_PHOTO`
- **Current Status**: Implemented in `desktop/camera.py` (`CameraManager`), but missing in `CanonicalIntent`. Reached only via fallback `GENERAL_CONVERSATION` $\rightarrow$ `DesktopActionManager`.
- **Current Command Path**: User $\rightarrow$ Intent Engine (returns `GENERAL_CONVERSATION`) $\rightarrow$ Fallback loop $\rightarrow$ `DesktopActionManager.process_input()` $\rightarrow$ `CameraManager`.
- **Problem**: 100-300ms fallback latency; not recognized as high-confidence structured intent.
- **Target Command Path**: User $\rightarrow$ `TextNormalizer` $\rightarrow$ `intent/matcher.py` (`CanonicalIntent.OPEN_CAMERA` / `TAKE_PHOTO`) $\rightarrow$ `RoutingDomain.DESKTOP_APP` / `CameraManager` $\rightarrow$ Verification $\rightarrow$ Spoken Result.
- **Natural Variations**: `"Open camera"`, `"Launch camera"`, `"Open Photo Booth"`, `"Take a picture"`, `"Take my photo"`, `"Click a photo"`, `"Capture a photo"`, `"NOVA, take a picture"`.
- **Files Changing**: `intent/models.py`, `intent/matcher.py`, `intent/router.py`, `main.py`, `core/task_agent/registry.py`.
- **Risk Level**: LOW (Existing `desktop/camera.py` already tested).
- **Test Plan**: Add direct and conversational camera intent tests in `tests/test_v3_5_capabilities.py`.

#### 2. Clipboard Capabilities
- **Capability**: `GET_CLIPBOARD`, `SET_CLIPBOARD`, `CLEAR_CLIPBOARD`
- **Current Status**: Implemented in `mac_control/actions/clipboard.py`, but missing in `CanonicalIntent`.
- **Current Command Path**: Unreachable from primary natural language intent engine.
- **Problem**: User cannot query or clear clipboard via voice.
- **Target Command Path**: User $\rightarrow$ `intent/matcher.py` (`CanonicalIntent.GET_CLIPBOARD`, `CLEAR_CLIPBOARD`, `SET_CLIPBOARD`) $\rightarrow$ `RoutingDomain.SYSTEM` / `ClipboardAction` $\rightarrow$ Spoken Result.
- **Natural Variations**: `"What is in my clipboard?"`, `"Show my clipboard"`, `"What did I copy?"`, `"Clear my clipboard"`, `"Empty the clipboard"`, `"Copy this to clipboard"`.
- **Files Changing**: `intent/models.py`, `intent/matcher.py`, `intent/router.py`, `main.py`, `core/task_agent/registry.py`.
- **Risk Level**: LOW.
- **Test Plan**: Unit test clipboard read, write, and clear in `tests/test_v3_5_capabilities.py`.

---

### Priority 2: Reachable Only Through Fallback Logic

#### 3. Wi-Fi Control
- **Capability**: `CONTROL_WIFI`
- **Current Status**: Implemented in `mac_control/actions/wifi.py` (`networksetup -setairportpower`), reachable only via secondary fallback regex.
- **Target Command Path**: `CanonicalIntent.CONTROL_WIFI` $\rightarrow$ `RoutingDomain.SYSTEM` $\rightarrow$ `WifiAction` $\rightarrow$ Spoken verification.
- **Natural Variations**: `"Turn off Wi-Fi"`, `"Turn on Wi-Fi"`, `"Enable Wi-Fi"`, `"Disable Wi-Fi"`, `"Is Wi-Fi on?"`, `"Check Wi-Fi status"`.
- **Files Changing**: `intent/models.py`, `intent/matcher.py`, `intent/router.py`, `main.py`, `core/task_agent/registry.py`.
- **Risk Level**: LOW.

#### 4. Bluetooth Control
- **Capability**: `CONTROL_BLUETOOTH`
- **Current Status**: Implemented in `mac_control/actions/bluetooth.py` (`blueutil` / AppleScript fallback), reachable only via fallback regex.
- **Target Command Path**: `CanonicalIntent.CONTROL_BLUETOOTH` $\rightarrow$ `RoutingDomain.SYSTEM` $\rightarrow$ `BluetoothAction` $\rightarrow$ Spoken verification.
- **Natural Variations**: `"Turn on Bluetooth"`, `"Turn off Bluetooth"`, `"Enable Bluetooth"`, `"Disable Bluetooth"`, `"Is Bluetooth on?"`.
- **Files Changing**: `intent/models.py`, `intent/matcher.py`, `intent/router.py`, `main.py`, `core/task_agent/registry.py`.
- **Risk Level**: LOW.

#### 5. Local Command Router Direct Cancel Handler
- **Capability**: `CANCEL_ACTION` Fast-Path
- **Current Status**: Defined in `voice/commands.py`, but callback not registered in `main.py`.
- **Target Command Path**: Register `self.command_router.register_handler("cancel", self._execute_local_cancel)` in `main.py` for sub-millisecond local bypass of active tasks.
- **Files Changing**: `main.py`.
- **Risk Level**: LOW.

---

### Priority 3: Missing Natural Language Variations & Action Aliases

#### 6. Natural Language Normalization & Wrappers
- **Scope**: Reusable conversational prefix/suffix stripping while strictly preserving query arguments:
  - Wake-word prefixes (`"NOVA,"`, `"Hey NOVA,"`, `"Okay NOVA,"`).
  - Conversational wrappers (`"Can you please"`, `"Could you"`, `"I want you to"`, `"Please"`, `"Would you mind"`).
  - Polite suffixes (`"please"`, `"for me"`, `"quickly"`).
- **Argument Preservation Invariant**: File names (`"DSA"`, `"main.cpp"`), URLs, search queries (`"Python tutorial"`), song names (`"Kesariya"`), and code snippets are never modified or stripped.
- **Action Aliases**:
  - `OPEN` / `LAUNCH` / `START` $\rightarrow$ Application launch / URL navigation.
  - `STOP` / `CANCEL` / `ABORT` / `NEVER MIND` $\rightarrow$ Task cancellation.
  - `CREATE` / `MAKE` $\rightarrow$ File/Folder creation.
  - `DELETE` / `REMOVE` $\rightarrow$ Trash deletion (with safety confirmation).
  - `SHOW` / `READ` / `WHAT IS ON` $\rightarrow$ Visual / Page extraction.
- **Files Changing**: `intent/normalizer.py`, `intent/matcher.py`.
- **Risk Level**: LOW.

---

### Priority 4: Autonomous Task Agent Capabilities

#### 7. V3 Capability Registry Expansion
- **Registered Capabilities Added**:
  - `camera.open_camera` (Risk: LOW)
  - `camera.take_photo` (Risk: LOW)
  - `clipboard.get` (Risk: LOW)
  - `clipboard.set` (Risk: LOW)
  - `clipboard.clear` (Risk: LOW)
  - `system.wifi` (Risk: MEDIUM)
  - `system.bluetooth` (Risk: MEDIUM)
  - `screen.record_start` (Risk: LOW)
  - `screen.record_stop` (Risk: LOW)
- **Safety Invariant**: Strictly typed, validated parameters; zero arbitrary AI shell execution.
- **Files Changing**: `core/task_agent/registry.py`.
- **Risk Level**: LOW.

---

## 3. Verification & Testing Matrix

1. **Unit & Variation Tests**: `tests/test_natural_language_variations.py` (Validating Direct, Wake-word, Conversational, and Alias forms across all categories).
2. **Capabilities Tests**: `tests/test_v3_5_capabilities.py` (Testing Camera, Clipboard, Wi-Fi, Bluetooth, Local Cancel, and Task Agent integration).
3. **Full Regression Suite**: Run all 156+ repository tests via `PYTHONPATH=. .venv/bin/pytest`.
