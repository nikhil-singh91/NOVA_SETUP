# NOVA Complete Command Catalog
**Comprehensive Reference Guide to NOVA's Real Capabilities & Spoken Phrases (V3.5)**

---

## 1. Quick Start

### Activation & Modes
- **Voice Mode**: Continuous microphone listening via `VoiceManager` (Silero VAD + Faster-Whisper / macOS speech recognition).
  - *Wake Word*: `"NOVA"`, `"Hey NOVA"`, `"Hi NOVA"`, `"Okay NOVA"`, `"Suno NOVA"`.
- **Text / CLI Mode**: Direct text entry in the interactive terminal console (`python main.py`). All commands work identically over text.
- **Immediate Task Interruption / Cancel**:
  - Say `"Stop"`, `"Cancel"`, `"Never mind"`, `"Abort"`, `"Stop doing that"`, `"Don't continue"`, or Hindi equivalents (`"रहने दो"`, `"रुको"`).
  - Immediately halts running tasks across Autonomous Task Agent V3, Computer Agent V2, Browser Automation, and Desktop Actions.
- **Shutdown / Exit**:
  - Say `"Shutdown"`, `"Exit"`, `"Quit"`, `"Bye NOVA"`, `"Close yourself"`, `"Go to sleep"`, or Hindi equivalents (`"बाय नोवा"`, `"बंद करो"`).
- **Required macOS Permissions**:
  - **Microphone**: For voice input.
  - **Accessibility**: For mouse clicks, keystroke typing, and active window inspection (`CGWindowListCopyWindowInfo`).
  - **Screen Recording**: For Computer Agent visual observation, OCR, UI coordinate inspection, and video recording.
  - **Camera**: For live camera viewfinder and photo capture.
  - **Automation / AppleEvents**: For controlling System Events, Finder, Safari, and Google Chrome via AppleScript.

---

## 2. Application Control

| What I Want | Commands I Can Say | Status | What NOVA Does | Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **Open VS Code** | `"Open VS Code"`, `"Launch VS Code"`, `"Start VS Code"`, `"Can you open VS Code?"`, `"NOVA, open VS Code"` | 🟢 CONFIRMED IMPLEMENTED | Finds Visual Studio Code in `/Applications` or Spotlight and launches it. | VS Code installed |
| **Open Google Chrome** | `"Open Chrome"`, `"Launch Google Chrome"`, `"Open browser"`, `"Please start Chrome"` | 🟢 CONFIRMED IMPLEMENTED | Launches Google Chrome or brings it to focus. | Chrome installed |
| **Open TextEdit** | `"Open TextEdit"`, `"Launch text editor"`, `"Open Notepad"`, `"Could you open TextEdit?"` | 🟢 CONFIRMED IMPLEMENTED | Launches native TextEdit or creates an open document. | None (Native) |
| **Open Finder** | `"Open Finder"`, `"Launch Finder"`, `"Open Files"` | 🟢 CONFIRMED IMPLEMENTED | Activates macOS Finder. | None (Native) |
| **Open Spotify** | `"Open Spotify"`, `"Launch Spotify"`, `"Can you start Spotify?"` | 🟢 CONFIRMED IMPLEMENTED | Launches Spotify app. | Spotify installed |
| **Open Terminal** | `"Open Terminal"`, `"Launch Terminal"`, `"Open iTerm"` | 🟢 CONFIRMED IMPLEMENTED | Opens native macOS Terminal or iTerm. | None (Native) |
| **Close Application** | `"Close VS Code"`, `"Quit Chrome"`, `"Exit Spotify"`, `"Close Terminal"` | 🟢 CONFIRMED IMPLEMENTED | Sends graceful terminate signal to the target application process. | App running |

---

## 3. Browser & Website Control

### Supported Capabilities
- **Open Website / Platform**:
  - *Commands*: `"Go to AKTU website"`, `"Open Flipkart"`, `"Open YouTube"`, `"Open GitHub"`, `"Open Amazon"`, `"Open Wikipedia"`, `"Can you open Flipkart?"`.
  - *What Happens*: Matches known platform URL from verified catalog or uses fast domain discovery; opens URL in default browser (Chrome) using native AppleScript or direct session.
  - *Code Path*: `Voice/Text` $\rightarrow$ `intent/matcher.py` (`CanonicalIntent.OPEN_WEBSITE`) $\rightarrow$ `browser/router.py` $\rightarrow$ `browser/engine.py`.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Search Web / Search Google**:
  - *Commands*: `"Search Google for Python tutorials"`, `"Search the web for Apple M3 chips"`, `"Search what is recursion"`.
  - *What Happens*: Encodes query and navigates to Google search results page.
  - *Code Path*: `CanonicalIntent.SEARCH_WEB` $\rightarrow$ `browser/sites/generic.py` / `google.py`.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Tab Management**:
  - *Commands*: `"Open a new tab"`, `"Close this tab"`, `"Next tab"`, `"Previous tab"`, `"Switch to Flipkart tab"`, `"Close NOVA tabs"`.
  - *What Happens*: Executes tab navigation shortcuts (`Command+T`, `Command+W`, `Command+Shift+]`, `Command+Shift+[` or URL tab matching) via native browser AppleScript.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **History & Page Navigation**:
  - *Commands*: `"Go back"`, `"Go forward"`, `"Scroll down"`, `"Scroll up"`, `"Scroll to top"`, `"Scroll to bottom"`.
  - *What Happens*: Triggers native browser history navigation and keyboard scroll signals (`PageDown`, `PageUp`, `Home`, `End`).
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Read & Summarize Current Webpage**:
  - *Commands*: `"Read this page"`, `"Summarize this webpage"`, `"What does this article say?"`, `"Get page text"`.
  - *What Happens*: Reads active browser page content, extracts readability text via `BrowserExtractor`, and generates an AI summary using the configured language provider.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 4. In-Website Actions

- **Search on Specific Website**:
  - *Commands*: `"In Flipkart search mobile phones"`, `"On YouTube search lofi music"`, `"On GitHub search fast whisper"`, `"In Amazon search laptop stand"`, `"Search mobile phones in Flipkart"`.
  - *What Happens*: Navigates directly to the target platform's structured search URL endpoint (e.g. `flipkart.com/search?q=...`) without manual clicking.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Visual Click on Web Elements**:
  - *Commands*: `"Click search"`, `"Click login button"`, `"Click add to cart"`, `"Click the second result"`, `"Select C++"`.
  - *What Happens*: Captures screen bounding box, analyzes UI hierarchy and OCR labels via Computer Agent V2 (`UITargetResolver`), computes target element coordinate `(x, y)`, and performs click with verification.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED (Requires Screen Recording permission).
- **Close Modal Popups & Dialogs**:
  - *Commands*: `"Close this popup"`, `"Dismiss dialog"`, `"Close overlay"`.
  - *What Happens*: Detects modal close icons (`✕`, `Close`, `Dismiss`) or executes `Escape` fallback to dismiss dialogs.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Scroll Until Element Visible**:
  - *Commands*: `"Scroll until you find contact us"`, `"Scroll until you find pricing"`, `"Scroll down to reviews"`.
  - *What Happens*: Bounded scroll-observe loop (up to 5 steps) until the target text or button is visible on screen.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 5. File & Folder Actions

- **Create Folder on Desktop**:
  - *Commands*: `"Create a folder called DSA on Desktop"`, `"Make a folder named DSA on Desktop"`, `"Can you create a folder called Projects on Desktop?"`.
  - *Path*: `~/Desktop/DSA` (or `~/Desktop/Projects`).
  - *What Happens*: Validates path against safety policy, creates directory on Desktop, updates `EnvironmentContext.last_created_path`.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Create Source Code File**:
  - *Commands*: `"Create a file called main.cpp"`, `"Create index.html in project folder"`, `"Make app.js inside it"`.
  - *What Happens*: Creates file with appropriate boilerplate starter template if recognized extension (`.cpp`, `.py`, `.html`, `.js`).
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Open Folder in Finder**:
  - *Commands*: `"Open DSA folder"`, `"Open the folder I just created"`, `"Open it"` (after creating a folder).
  - *What Happens*: Resolves folder from name search or context and opens it in macOS Finder (`open <path>`).
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Move File/Folder to Trash (Safety Confirmation)**:
  - *Commands*: `"Delete this folder"`, `"Delete that file"`, `"Move this to trash"`.
  - *Safety Behavior*: NOVA intercepts destructive requests, asks `"Do you want me to delete <name>?"`, and only deletes after the user explicitly says `"Yes"` or `"Confirm"`.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 6. Document Writing

- **Write and Open Document**:
  - *Commands*: `"Write an application for college leave"`, `"Write a leave application"`, `"Write an email apologizing for delay"`, `"Open Notepad and write a project report"`.
  - *What Happens*:
    1. Uses AI provider (`ProviderManager`) to compose the complete document body.
    2. Saves document to `~/Documents/NOVA_Documents/<topic>.txt` (or Desktop if requested).
    3. Automatically opens the generated document in macOS TextEdit for immediate review.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 7. Media & YouTube

- **Play Music Track / Song**:
  - *Commands*: `"Play Kesariya"`, `"Play the song Kesariya"`, `"I want to listen to Kesariya"`, `"Play Believer"`, `"Play Shape of You"`.
  - *What Happens*:
    1. `MediaRequestParser` parses track title and modifiers (`official`, `remix`, `slowed`, `lofi`).
    2. `MediaCollector` queries YouTube and retrieves candidate videos.
    3. `CandidateScorer` scores videos for official uploads, verified channels, and exact title matches.
    4. Opens top video in Google Chrome.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **YouTube Shorts Automation**:
  - *Commands*: `"Open YouTube Shorts"`, `"Watch Shorts"`, `"Start auto Shorts"`, `"Next Short"`, `"Previous Short"`, `"Stop Shorts"`.
  - *What Happens*: Opens `youtube.com/shorts`, navigates between Shorts with `ArrowDown` / `ArrowUp`, and optionally auto-scrolls between Shorts.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 8. Camera (Connected V3.5)

| Feature | Commands I Can Say | Status | What NOVA Does | Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **Open Camera Viewfinder** | `"Open camera"`, `"Launch camera"`, `"Open Photo Booth"`, `"Can you please launch the camera?"` | 🟢 CONFIRMED IMPLEMENTED | Launches macOS Photo Booth to provide a live camera viewfinder. | Camera permission |
| **Capture Photo Snapshot** | `"Take a picture"`, `"Take a photo"`, `"Take my photo"`, `"Click a photo"`, `"Capture a photo"`, `"NOVA, take a picture"` | 🟡 IMPLEMENTED — MANUAL TEST REQUIRED | Uses FFmpeg AVFoundation or native frame grabber to capture snapshot and save to `~/Pictures/NOVA/photo_<timestamp>.jpg`. | Connected Webcam + FFmpeg |

---

## 9. System Clipboard (Connected V3.5)

| Feature | Commands I Can Say | Status | What NOVA Does | Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **Get Clipboard Content** | `"What is in my clipboard?"`, `"What's in my clipboard?"`, `"Show my clipboard"`, `"What did I copy?"` | 🟢 CONFIRMED IMPLEMENTED | Reads current text buffer via `pbpaste` and speaks clipboard text preview. | None |
| **Clear Clipboard** | `"Clear my clipboard"`, `"Empty the clipboard"`, `"Clear clipboard"` | 🟢 CONFIRMED IMPLEMENTED | Empties the macOS pasteboard buffer safely. | None |
| **Copy to Clipboard** | `"Copy this to clipboard"`, `"Copy <text> to clipboard"` | 🟢 CONFIRMED IMPLEMENTED | Copies active context URL/file path or requested text into the pasteboard. | None |

---

## 10. Wi-Fi & Bluetooth (Connected V3.5)

| Feature | Commands I Can Say | Status | What NOVA Does | Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **Turn On Wi-Fi** | `"Turn on Wi-Fi"`, `"Enable Wi-Fi"`, `"Wi-Fi on karo"` | 🟢 CONFIRMED IMPLEMENTED | Calls macOS `networksetup -setairportpower en0 on` and confirms. | Network setup access |
| **Turn Off Wi-Fi** | `"Turn off Wi-Fi"`, `"Disable Wi-Fi"`, `"Wi-Fi off karo"` | 🟢 CONFIRMED IMPLEMENTED | Calls macOS `networksetup -setairportpower en0 off` and confirms. | Network setup access |
| **Check Wi-Fi Status** | `"Is Wi-Fi on?"`, `"Check Wi-Fi status"` | 🟢 CONFIRMED IMPLEMENTED | Queries Wi-Fi hardware power status and speaks result. | None |
| **Turn On Bluetooth** | `"Turn on Bluetooth"`, `"Enable Bluetooth"` | 🟡 IMPLEMENTED — MANUAL TEST REQUIRED | Uses `blueutil --power 1` or AppleScript bluetooth toggle. | `blueutil` CLI installed |
| **Turn Off Bluetooth** | `"Turn off Bluetooth"`, `"Disable Bluetooth"` | 🟡 IMPLEMENTED — MANUAL TEST REQUIRED | Uses `blueutil --power 0` or AppleScript bluetooth toggle. | `blueutil` CLI installed |
| **Check Bluetooth Status** | `"Is Bluetooth on?"`, `"Check Bluetooth status"` | 🟡 IMPLEMENTED — MANUAL TEST REQUIRED | Queries Bluetooth power status and speaks result. | `blueutil` CLI installed |

---

## 11. Screen Recording

- **Start Screen Recording**:
  - *Commands*: `"Start recording screen"`, `"Record my screen"`, `"Start screen recording"`, `"Record screen"`.
  - *What Happens*: Launches `ScreenRecordingManager`, binds macOS `screencapture -v` / AVFoundation background capture, and updates active recording state.
  - *Save Location*: `~/Movies/NOVA_Recordings/recording_<timestamp>.mov`.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Stop Screen Recording**:
  - *Commands*: `"Stop recording"`, `"Stop screen recording"`, `"Finish recording"`.
  - *What Happens*: Terminates background recording process, validates output video file size, and speaks output path.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 12. Visual Interaction (Computer Agent V2)

- **What Am I Looking At?**:
  - *Commands*: `"What am I looking at?"`, `"What is on my screen?"`, `"Describe what you see"`.
  - *What Happens*: Environment Observer checks active window, webpage title, or Finder folder; if unclear, takes an on-demand screen capture and returns a concise description.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Explain Screen Error**:
  - *Commands*: `"Explain this error"`, `"Why did this fail?"`, `"What is wrong with this screen?"`.
  - *What Happens*: Captures screen, performs OCR / visual error pattern recognition, and delivers a plain-language explanation and recommended fix.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Click Visible UI Button / Link**:
  - *Commands*: `"Click the search button"`, `"Click sign in"`, `"Click cancel"`.
  - *What Happens*: Visual UI detector locates bounding box and sends verified hardware mouse click.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 13. macOS Hardware & System Control

- **Volume Control**:
  - *Commands*: `"Set volume to 50%"`, `"Increase volume"`, `"Volume up"`, `"Mute"`, `"Unmute"`.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Brightness Control**:
  - *Commands*: `"Set brightness to 70%"`, `"Increase brightness"`, `"Brightness up"`, `"Dim screen"`.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED (Native MacBook displays).
- **Lock Screen (Connected V3.5)**:
  - *Commands*: `"Lock screen"`, `"Lock my mac"`, `"Lock my computer"`, `"Screen lock karo"`.
  - *What Happens*: Executes macOS native screen lock via System Events / AppleScript.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 14. Autonomous Task Agent (Multi-Step V3)

- **Create Project with Nested Subfolders**:
  - *Command*: `"Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders"`
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Scaffold Code Project with Files**:
  - *Command*: `"Create a C++ project with main.cpp and README.md"`
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
- **Search Web & Save Link in Document**:
  - *Command*: `"Find a Python tutorial and save the useful link in a text file"`
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.

---

## 15. Task Control & Interruption

- **Stop / Cancel Active Action**:
  - *Commands*: `"Stop"`, `"Cancel"`, `"Never mind"`, `"Abort"`, `"Stop doing that"`, `"Don't continue"`, `"रहने दो"`, `"रुको"`.
  - *Subsystems Cancelled*: `TaskExecutor._stop_event`, `ComputerAgent._stop_event`, `BrowserSessionManager.stop_active_task()`, `DesktopActionManager.stop_active_task()`.
  - *What Happens*: Any running multi-step loop or visual interaction aborts immediately and confirms cancellation.
  - *Status*: 🟢 CONFIRMED IMPLEMENTED.
