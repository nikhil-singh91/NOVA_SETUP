# NOVA Capability Registry & Execution Catalog

This document catalogs all verified capabilities built into NOVA, mapping each capability from user intent down to OS-level execution and verification.

---

## 📋 Comprehensive Capability Catalog

### 1. Filesystem Capabilities

| Capability ID | Description | Intent | Executor | OS / API | Verification | Risk Level |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `fs.create_folder` | Create a folder on Desktop or designated directory | `CREATE_FOLDER` | `FileSystemManager.create_folder` | `pathlib.Path.mkdir` | `Path.is_dir()` check | LOW |
| `fs.create_file` | Create source code or document file | `CREATE_FILE` | `FileSystemManager.create_files` | `pathlib.Path.write_text` | `Path.is_file()` check | LOW |
| `fs.open_folder` | Open directory in Finder | `OPEN_FOLDER` | `FileSystemManager` | `subprocess.run(["open", path])` | Finder state check | LOW |
| `fs.safe_move_to_trash`| Move file or directory to macOS Trash | `DELETE_ITEM` | `FileSystemManager.safe_move_to_trash` | `osascript` / `send2trash` | `not Path.exists()` | **HIGH (Conf. Req.)** |

### 2. Document & Code Capabilities

| Capability ID | Description | Intent | Executor | OS / API | Verification | Risk Level |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `doc.write_and_open` | Generate AI document and open in editor | `GENERATE_AND_WRITE_DOCUMENT` | `DocumentEditor.write_and_open_document` | `ProviderManager` + `open` | Document path exists | LOW |
| `code.scaffold_project`| Generate code project scaffolding | `SCAFFOLD_PROJECT` | `CodeFileManager` | `pathlib.Path` | Files created check | LOW |

### 3. Application Control

| Capability ID | Description | Intent | Executor | OS / API | Verification | Risk Level |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `app.launch` | Launch any macOS application | `LAUNCH_APP` | `AppLauncher.launch` | `subprocess.run(["open", "-a", app])` | Process active check | LOW |
| `app.close` | Close or terminate macOS application | `CLOSE_APP` | `AppLauncher.close` | `osascript quit` / `pkill` | Process terminated | MEDIUM |

### 4. Browser Capabilities

| Capability ID | Description | Intent | Executor | OS / API | Verification | Risk Level |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `browser.open_site` | Navigate to website URL | `OPEN_SITE` | `MacOSNativeBrowserEngine.open_url` | AppleScript Chrome/Safari | URL match check | LOW |
| `browser.search_web` | Search Google for query | `SEARCH_WEB` | `GoogleSkill.search` | URL navigation | Tab loaded check | LOW |
| `browser.search_site`| Search inside Amazon/GitHub/YouTube | `SEARCH_SITE` | `SiteSkill.search` | URL search queries | Tab loaded check | LOW |
| `browser.open_new_tab`| Open a new browser tab | `OPEN_NEW_TAB` | `MacOSNativeBrowserEngine.open_new_tab` | AppleScript `make new tab` | Tab count delta | LOW |
| `browser.search_current_tab`| Search within current tab | `SEARCH_CURRENT_TAB`| `MacOSNativeBrowserEngine.search_current_tab`| AppleScript active tab URL | URL updated check | LOW |
| `browser.scroll` | Scroll page up / down / top / bottom | `SCROLL_DOWN` / `SCROLL_UP` | `MacOSNativeBrowserEngine.scroll_page` | AppleScript JavaScript scroll | Success bool | LOW |
| `browser.auto_shorts`| Continuous YouTube Shorts scrolling | `START_AUTO_SHORTS` | `YouTubeShortsScroller` | Background timer + key event | Active flag check | LOW |
| `browser.research` | Multi-step deep web research | `RESEARCH_TOPIC` | `BrowserTaskPlanner.execute_research` | HTTP extractor + LLM | Extracted summary | LOW |

### 5. Visual UI & Screen Perception (NOVA Eyes)

| Capability ID | Description | Intent | Executor | OS / API | Verification | Risk Level |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `visual.click_element` | Click UI button/link by label | `CLICK_UI_ELEMENT` | `ComputerAgent.execute_visual_goal` | Quartz `CGEvent` mouse click | Screen state change | MEDIUM |
| `visual.type_text` | Type text into input field | `TYPE_UI_TEXT` | `ComputerAgent.type_into_focused_or_target` | Quartz `CGEvent` keyboard | OCR text delta | LOW |
| `visual.close_popup` | Close active modal dialog/popup | `CLOSE_POPUP` | `ComputerAgent.close_popup` | Quartz click on close button | Popup removed | LOW |
| `visual.scroll_until` | Scroll until text is visible | `SCROLL_UNTIL_VISIBLE` | `ComputerAgent.scroll_until_visible` | Quartz scroll + OCR loop | Target found in OCR | LOW |
| `visual.observe_screen`| Summarize/explain screen | `WHAT_AM_I_LOOKING_AT` | `ComputerAgent.explain_screen_content` | Quartz frame + Vision OCR | Non-empty description| LOW |

### 6. System & Hardware Control

| Capability ID | Description | Intent | Executor | OS / API | Verification | Risk Level |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `system.volume` | Adjust or mute system volume | `CONTROL_VOLUME` | `mac_control.actions.volume` | AppleScript `set volume` | Volume query check | LOW |
| `system.brightness` | Adjust display brightness | `CONTROL_BRIGHTNESS` | `mac_control.actions.brightness` | `brightness` CLI / AppleScript | Brightness query | LOW |
| `system.wifi` | Toggle or query Wi-Fi | `CONTROL_WIFI` | `mac_control.actions.wifi` | `networksetup` CLI | Interface power status | MEDIUM |
| `system.bluetooth` | Query or toggle Bluetooth | `CONTROL_BLUETOOTH` | `mac_control.actions.bluetooth` | `blueutil` CLI / AppleScript | Status query | MEDIUM |
| `system.lock_screen` | Lock macOS screen | `LOCK_SCREEN` | `mac_control.actions.system.lock_screen` | `CGSession -suspend` | Success return | LOW |
| `system.shutdown` | Shut down host machine | `SYSTEM_SHUTDOWN` | `mac_control.actions.system` | AppleScript shutdown | **HIGH (Conf. Req.)** |
| `camera.open_camera` | Open camera viewfinder | `OPEN_CAMERA` | `CameraManager.open_camera` | `open -a "Photo Booth"` | App active check | LOW |
| `camera.take_photo` | Take snapshot photo | `TAKE_PHOTO` | `CameraManager.capture_photo` | AVFoundation / Imagesnap | File created check | LOW |
| `screen.capture` | Take full screenshot | `SCREEN_CAPTURE` | `ScreenshotService.capture_full_screen` | macOS `screencapture` CLI | Screenshot file exists | LOW |
| `screen.record_start`| Start background screen record | `START_SCREEN_RECORDING`| `ScreenRecordingManager.start_recording` | Background `screencapture -v` | Process active check | LOW |
| `screen.record_stop` | Stop background screen record | `STOP_SCREEN_RECORDING` | `ScreenRecordingManager.stop_recording` | `kill` recording process | Video file exists | LOW |
| `clipboard.get` | Read clipboard text | `GET_CLIPBOARD` | `mac_control.actions.clipboard.get_clipboard` | `pbpaste` CLI | Text return | LOW |
| `clipboard.set` | Write clipboard text | `SET_CLIPBOARD` | `mac_control.actions.clipboard.set_clipboard` | `pbcopy` CLI | Read-back check | LOW |
| `clipboard.clear` | Clear clipboard text | `CLEAR_CLIPBOARD` | `mac_control.actions.clipboard.clear_clipboard` | `pbcopy` empty string | Empty string check | LOW |
