# macOS Permissions Setup Guide for NOVA

This guide details all macOS system privacy permissions NOVA requires to operate hardware controls, window inspection, visual UI control, camera operations, and audio listening.

---

## 1. Summary of Required Permissions

| Permission Name | macOS Settings Location | Required By Feature | Severity |
| :--- | :--- | :--- | :--- |
| **Microphone** | Privacy & Security $\rightarrow$ Microphone | Voice V2 Real-Time Listening | **Critical** (for Voice) |
| **Accessibility** | Privacy & Security $\rightarrow$ Accessibility | Mouse Clicking, Keystroke Typing, Active Window Tracking | **Critical** (for Hands/UI) |
| **Screen Recording** | Privacy & Security $\rightarrow$ Screen Recording | Computer Agent Visual OCR, UI Analysis, Screen Video Capture | **Critical** (for Eyes/Visual) |
| **Automation / AppleEvents** | Privacy & Security $\rightarrow$ Automation | Google Chrome, Safari, Finder, System Events Control | **Critical** (for Browser/Finder) |
| **Camera** | Privacy & Security $\rightarrow$ Camera | Camera Viewfinder & Photo Snapshot Capture | **Optional** (for Camera) |
| **Files & Folders** | Privacy & Security $\rightarrow$ Files and Folders | Desktop, Documents, Downloads Workspace Management | **Standard** |

---

## 2. Detailed Permission Walkthroughs

### 1. Accessibility (`AXIsProcessTrusted`)
- **Why NOVA Needs It**:
  - Allows NOVA to query open window titles via `CGWindowListCopyWindowInfo`.
  - Enables Computer Agent V2 to click coordinates `(x, y)` and type characters into UI text fields.
- **Which Features Use It**:
  - `core/computer_agent.py` (`ComputerAgent.execute_visual_goal`, `type_into_focused_or_target`)
  - `core/environment.py` (`EnvironmentObserver`)
  - `desktop/apps.py` (`AppLauncher`)
- **How to Grant**:
  1. Open **System Settings** $\rightarrow$ **Privacy & Security** $\rightarrow$ **Accessibility**.
  2. Toggle **Terminal** (or **iTerm2** / **VS Code**, whichever is running `python main.py`) to **ON**.
- **How to Verify in Terminal**:
  ```bash
  python3 -c "import ApplicationServices; print('Accessibility Granted:', ApplicationServices.AXIsProcessTrusted())"
  ```

---

### 2. Screen Recording (`CGDisplayStream` / `screencapture`)
- **Why NOVA Needs It**:
  - On-demand screen capture for visual inspection and error explanation.
  - Video recording of screen sessions (`~/Movies/NOVA_Recordings/`).
- **Which Features Use It**:
  - `core/computer_agent.py` (`ScreenObserver.capture_screen()`, `VisualVerifier`)
  - `core/screen_recording.py` (`ScreenRecordingManager.start_recording()`)
- **How to Grant**:
  1. Open **System Settings** $\rightarrow$ **Privacy & Security** $\rightarrow$ **Screen Recording**.
  2. Add and toggle **Terminal** (or **iTerm2** / **VS Code**) to **ON**.
- **How to Verify**:
  ```bash
  screencapture -x -r /tmp/nova_test_screen.png && ls -l /tmp/nova_test_screen.png
  ```

---

### 3. Automation / AppleEvents (`osascript`)
- **Why NOVA Needs It**:
  - Controls Google Chrome and Safari tabs, navigates URLs, and queries Finder paths.
- **Which Features Use It**:
  - `browser/engine.py` (`MacOSNativeBrowserEngine`)
  - `desktop/files.py` (Finder opening bridge)
  - `mac_control/actions/` (Volume, Brightness, Screen Lock)
- **How to Grant**:
  1. When prompted by macOS dialog: *"Terminal wants to control Google Chrome"*, click **Allow**.
  2. To check: Open **System Settings** $\rightarrow$ **Privacy & Security** $\rightarrow$ **Automation**. Ensure Google Chrome, Safari, and System Events are checked under your Terminal app.
- **How to Verify**:
  ```bash
  osascript -e 'tell application "System Events" to get name of every application process'
  ```

---

### 4. Microphone (`AVAudioSession` / PyAudio)
- **Why NOVA Needs It**:
  - Captures live audio streams for Silero VAD and Whisper voice transcription.
- **Which Features Use It**:
  - `voice/listener.py` (`AudioListener`)
- **How to Grant**:
  1. Open **System Settings** $\rightarrow$ **Privacy & Security** $\rightarrow$ **Microphone**.
  2. Toggle **Terminal** (or **iTerm2**) to **ON**.
- **How to Verify**:
  Run `python main.py doctor` or:
  ```bash
  python3 -c "import sounddevice; print(sounddevice.query_devices())"
  ```

---

### 5. Camera (`AVFoundation` / Photo Booth)
- **Why NOVA Needs It**:
  - Opens Photo Booth viewfinder and captures snapshot photos.
- **Which Features Use It**:
  - `desktop/camera.py` (`CameraManager`)
- **How to Grant**:
  1. Open **System Settings** $\rightarrow$ **Privacy & Security** $\rightarrow$ **Camera**.
  2. Toggle **Terminal** / **Photo Booth** to **ON**.
- **How to Verify**:
  ```bash
  open -a "Photo Booth"
  ```

---

## 3. Automated Diagnostic Command

NOVA includes an automated diagnostic tool to verify all system components and permissions:
```bash
python main.py doctor
```
