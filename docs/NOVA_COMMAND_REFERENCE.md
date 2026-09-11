# NOVA — Complete Command Reference

An authoritative, exhaustive personal manual and technical capability reference for **NOVA** (Next-generation Omni Voice Assistant) on macOS.

> **Integrity Guarantee**: Every command, routing pattern, execution pipeline, internal mechanism, permission requirement, and limitation in this document has been verified against the actual NOVA source code. No hypothetical or wish-list capabilities are included.

---

## 1. Quick Start

### How to Talk to NOVA

NOVA accepts input via both continuous voice listening (Microphone $\rightarrow$ Silero VAD $\rightarrow$ Faster-Whisper STT) and text input (`main.py` console / UI).

You can speak to NOVA using plain conversational English or Romanized Hindi/Hinglish. You do **not** need to speak in rigid robotic keywords.

#### Example Spoken Commands:
* *"Nova, open Telegram"*
* *"Nova, increase volume"*
* *"Nova, set volume to 70%"*
* *"Nova, take a screenshot"*
* *"Nova, open YouTube and search for DSA tutorials"*
* *"Nova, write a leave application in TextEdit"*

### Accepted Prefixes & Conversational Wrappers

NOVA's `TextNormalizer` (`intent/normalizer.py`) runs iteratively up to 6 passes to strip wake words and conversational filler without corrupting target parameters.

#### 1. Supported Wake Words:
* `"Nova"`, `"Hey Nova"`, `"Hi Nova"`, `"Hello Nova"`, `"Ok Nova"`, `"Okay Nova"`
* Phonetic Whisper variants: `"Nobba"`, `"No va"`
* Trailing wake words: `"... Nova"` (e.g., *"Take a screenshot, Nova"*)

#### 2. Supported Opening Prefixes:
* Polite addresses: `"Boss"`, `"Sir"`, `"Bhai"`, `"Buddy"`
* Urgency prefixes: `"Now"`, `"Right now"`
* Fillers: `"Okay"`, `"Ok"`, `"Alright"`, `"Well"`, `"So"`
* Polite requests: `"Can you"`, `"Could you"`, `"Would you"`, `"Will you"`
* Polite combos: `"Can you please"`, `"Could you please"`, `"Would you please"`
* Desires: `"I want you to"`, `"I would like you to"`, `"I need you to"`, `"I'd like you to"`, `"I want to"`
* Courtesy: `"Please"`, `"Kindly"`, `"Kripya"`, `"Zara"`
* Helpers: `"Tell me"`, `"Help me to"`, `"Help me"`, `"Go ahead and"`, `"Please go ahead and"`

#### 3. Stripped Trailing Politeness:
* `"... please"`, `"... for me"`, `"... quickly"`, `"... now"`, `"... boss"`, `"... kripya"`
*(Protected by entity guards: if the trailing word is preceded by "named", "called", "into", or "search for", it is preserved as part of the target entity).*

---

## 2. Voice & Conversation

### 2.1 General Conversational AI & Explanations
* **Status**: ✅ WORKING
* **Mac Permissions**: None (Network access required for LLM APIs)
* **What it does internally**:
  1. Input is matched against `CanonicalIntent.GENERAL_CONVERSATION` if no specific system, browser, or desktop intent triggers.
  2. Synthesizes memory context via `MemoryManager.search_memory(user_text)` and injects user profile context.
  3. Dispatches query to `ProviderManager.generate_response(prompt, task_type=TaskType.GENERAL)`.
  4. Routes through active fallback chain: Google Gemini $\rightarrow$ Groq $\rightarrow$ OpenRouter $\rightarrow$ Cerebras.
  5. Speaks response via `SpeakerManager` (Kokoro TTS / Edge-TTS / macOS `say`) and prints to Activity Feed.
  6. Automatically logs turn to conversation history and durable episodic memory.

* **Commands you can say**:
  * *"What is the difference between a process and a thread?"*
  * *"Explain Dijkstra's algorithm in simple terms"*
  * *"Who was Alan Turing?"*
  * *"Help me understand dynamic programming"*
  * *"Why is the sky blue?"*
  * *"Tell me a fun programming joke"*

### 2.2 Follow-up & Conversational Context
* **Status**: ✅ WORKING
* **What it does internally**:
  Maintains sliding context window of past turns (`conversation_history` in `main.py`). Resolves anaphoric pronouns ("it", "that", "the previous one") against recently created files, open folders, or active browser URLs via `ContextResolver`.
* **Commands you can say**:
  * *"Can you explain that in more detail?"*
  * *"Give me an example in C++"*
  * *"What are the time and space complexities for that?"*

---

## 3. Mac System Controls

### 3.1 Volume Control
* **Status**: ✅ WORKING
* **Mac Permissions**: None (Uses native macOS AppleScript audio settings)
* **Implementation File**: `mac_control/actions/volume.py`, `mac_control/dispatcher.py`
* **What it does internally**:
  * Executes AppleScript `set volume output volume <val>`.
  * For relative adjustments: Reads current volume via `output volume of (get volume settings)` and steps $\pm 10$ (or custom step).
  * Clamps levels strictly between $0$ and $100\%$.
  * Spoken response confirms exact resulting volume (e.g., *"Volume increased to 60%"*).

#### Supported Operations:
* **Relative Increase**:
  * *"Increase volume"*
  * *"Turn up the volume"*
  * *"Make it louder"*
  * *"Nova, volume badhao"*
  * *"Increase the volume of my Mac"*
* **Relative Decrease**:
  * *"Decrease volume"*
  * *"Turn down the volume"*
  * *"Lower the volume"*
  * *"Make it quieter"*
  * *"Nova, volume kam karo"*
* **Absolute Percentage**:
  * *"Set volume to 70%"*
  * *"Set volume to 100%"*
  * *"Make volume 50%"*
  * *"Volume 30 percent"*
  * *"Change volume to 85 percent"*
* **Mute / Unmute**:
  * *"Mute volume"* / *"Mute sound"* / *"Mute audio"*
  * *"Unmute volume"* / *"Unmute sound"*
* **Check Status**:
  * *"What is the volume?"* / *"Current volume"* / *"Check volume"*

---

### 3.2 Display Brightness
* **Status**: ✅ WORKING
* **Mac Permissions**: 🔒 REQUIRES PERMISSION (Accessibility permission required for fallback keycode simulation; native CoreGraphics/DisplayServices used if available)
* **Implementation File**: `mac_control/actions/brightness.py`
* **What it does internally**:
  * Attempts native macOS private `DisplayServices` framework (`DisplayServicesSetBrightness`).
  * If unavailable, executes AppleScript `System Events` key code $144$ (Brightness Up) or $145$ (Brightness Down).
  * Bounds checks between $0\%$ and $100\%$.

#### Supported Operations:
* **Relative Adjustments**:
  * *"Increase brightness"* / *"Turn up brightness"* / *"Make screen brighter"* / *"Brighter"*
  * *"Decrease brightness"* / *"Turn down brightness"* / *"Make screen dimmer"* / *"Dim screen"*
* **Absolute Percentage**:
  * *"Set brightness to 80%"*
  * *"Set brightness to 50%"*
  * *"Make brightness 100%"*
  * *"Brightness 40 percent"*
* **Check Status**:
  * *"Check brightness"* / *"What is the brightness?"*

---

### 3.3 Wi-Fi Control
* **Status**: ✅ WORKING
* **Mac Permissions**: None (Runs native `/usr/sbin/networksetup`)
* **Implementation File**: `mac_control/actions/wifi.py`
* **What it does internally**:
  * Dynamically detects active Wi-Fi interface (e.g. `en0`) via `networksetup -listallhardwareports`.
  * Power check: `networksetup -getairportpower <interface>`.
  * Power toggle: `networksetup -setairportpower <interface> on/off`.
  * SSID check: `networksetup -getairportnetwork <interface>` with CoreWLAN fallback.

#### Supported Operations:
* **Check Wi-Fi State**:
  * *"Is Wi-Fi on?"*
  * *"Check Wi-Fi status"*
  * *"What Wi-Fi am I connected to?"*
  * *"What is my current Wi-Fi network?"*
* **Turn Wi-Fi On**:
  * *"Turn Wi-Fi on"*
  * *"Enable Wi-Fi"*
  * *"Switch Wi-Fi on"*
* **Turn Wi-Fi Off**:
  * *"Turn Wi-Fi off"*
  * *"Disable Wi-Fi"*
  * *"Switch Wi-Fi off"*

---

### 3.4 Bluetooth Control
* **Status**: ⚠️ PARTIALLY WORKING
* **Mac Permissions**: 🔒 System Settings / CLI tool dependency
* **Implementation File**: `mac_control/actions/bluetooth.py`
* **What it does internally**:
  * Status check: Uses native `system_profiler SPBluetoothDataType` (no external tools required). Returns accurate ON/OFF state.
  * Power toggle: Requires the third-party CLI utility `blueutil` (`brew install blueutil`).
  * If `blueutil` is missing from system PATH, NOVA cleanly returns an informational error instructing the user to install `blueutil` via Homebrew rather than failing silently.

#### Supported Operations:
* **Check State** (✅ Working natively):
  * *"Is Bluetooth on?"*
  * *"Check Bluetooth status"*
  * *"Bluetooth status"*
* **Toggle State** (⚠️ Requires `blueutil`):
  * *"Turn Bluetooth on"*
  * *"Turn Bluetooth off"*
  * *"Enable Bluetooth"*
  * *"Disable Bluetooth"*

---

### 3.5 Clipboard Management
* **Status**: ✅ WORKING
* **Mac Permissions**: None (Uses native `pbcopy` and `pbpaste`)
* **Implementation File**: `mac_control/actions/clipboard.py`
* **What it does internally**:
  * `get_clipboard`: Streams from `/usr/bin/pbpaste`.
  * `set_clipboard`: Pipes content into `/usr/bin/pbcopy`.
  * `clear_clipboard`: Writes an empty string into `/usr/bin/pbcopy`.

#### Supported Operations:
* *"What is in my clipboard?"* / *"Read clipboard"*
* *"Clear clipboard"* / *"Empty clipboard"*
* *"Copy to clipboard: Hello World"*

---

### 3.6 Lock Screen & System Shutdown
* **Status**: ✅ WORKING
* **Mac Permissions**: 🔒 System shutdown requires user confirmation; Accessibility permission for sleep
* **Implementation File**: `mac_control/actions/system.py`
* **What it does internally**:
  * Lock Screen: Executes native `pmset displaysleepnow` or AppleScript System Events key combo `Command + Control + Q`.
  * System Shutdown: Safeguarded by two-step confirmation (`ctx.pending_confirmation`). NOVA asks *"Are you sure you want to shut down your Mac?"* and only proceeds upon affirmative user confirmation ("yes" / "confirm").

#### Supported Operations:
* *"Lock screen"* / *"Lock my Mac"* / *"Lock computer"*
* *"Shutdown system"* / *"Shut down my Mac"* / *"Turn off computer"*

---

## 4. Application Control

* **Status**: ✅ WORKING
* **Mac Permissions**: None (Uses native macOS `/usr/bin/open` command and AppleScript `tell application "<App>" to quit`)
* **Implementation File**: `desktop/apps.py`

### How Application Resolution Works
NOVA does **not** rely on hardcoded application paths. It dynamically searches:
1. `/Applications`
2. `/System/Applications`
3. `/System/Applications/Utilities`
4. `~/Applications`
5. `/System/Library/CoreServices`

It uses exact matching, case-insensitive substring matching, and an alias dictionary:

| Spoken Alias | Resolved macOS Application |
|--------------|---------------------------|
| `vs code`, `code`, `vscode` | `Visual Studio Code` |
| `chrome`, `google chrome` | `Google Chrome` |
| `notepad`, `text editor`, `textedit` | `TextEdit` |
| `terminal`, `iterm`, `iterm2` | `Terminal` or `iTerm` |
| `spotify` | `Spotify` |
| `telegram` | `Telegram` |
| `finder`, `files` | `Finder` |
| `notes` | `Notes` |
| `calculator`, `calc` | `Calculator` |
| `safari` | `Safari` |
| `slack` | `Slack` |
| `sublime`, `sublime text` | `Sublime Text` |

If an arbitrary app is installed (e.g. `Discord`, `VLC`, `Obsidian`), NOVA resolves its `.app` bundle automatically.

### 4.1 Launch Application
* **Commands**:
  * *"Open Telegram"*
  * *"Open Telegram app"*
  * *"Launch Telegram"*
  * *"Start Telegram"*
  * *"Nova, open Telegram"*
  * *"Now open Telegram app"*
  * *"Open VS Code"*
  * *"Launch Google Chrome"*
  * *"Open Spotify"*
  * *"Open TextEdit"*
  * *"Open Calculator"*
  * *"Open Terminal"*

### 4.2 Close / Quit Application
* **Commands**:
  * *"Close Telegram"*
  * *"Quit Telegram"*
  * *"Close VS Code"*
  * *"Quit Google Chrome"*
  * *"Close TextEdit"*
  * *"Exit Spotify"*

---

## 5. Browser & Web Control

* **Status**: ✅ WORKING
* **Mac Permissions**: 🔒 Automation / AppleScript permission for Google Chrome or Safari
* **Implementation Architecture**:
  * Engine: `MacOSNativeBrowserEngine` (`browser/engine.py`) using AppleScript native Chrome/Safari scripting.
  * Session & Tab Registry: `BrowserSessionManager` (`browser/sessions.py`).
  * Trusted Site Registry: `TRUSTED_SITES` (`browser/sites/generic.py`).

### 5.1 Open Websites & Navigation
NOVA directly routes trusted site keywords to official URLs, and parses arbitrary web domains:
* *"Open YouTube"* $\rightarrow$ `https://www.youtube.com`
* *"Open Google"* $\rightarrow$ `https://www.google.com`
* *"Open Flipkart"* $\rightarrow$ `https://www.flipkart.com`
* *"Open Amazon"* $\rightarrow$ `https://www.amazon.com`
* *"Open GitHub"* $\rightarrow$ `https://github.com`
* *"Open Wikipedia"* $\rightarrow$ `https://www.wikipedia.org`
* *"Open AKTU website"* $\rightarrow$ `https://aktu.ac.in`
* *"Open Instagram"* $\rightarrow$ `https://www.instagram.com`
* *"Open Reddit"* $\rightarrow$ `https://www.reddit.com`
* *"Open LinkedIn"* $\rightarrow$ `https://www.linkedin.com`
* *"Open Netflix"* $\rightarrow$ `https://www.netflix.com`
* Arbitrary URL: *"Open github.com/trending"* or *"Go to developer.apple.com"*

### 5.2 In-Site Search
NOVA parses the target site and query parameters:
* *"Search YouTube for DSA in C++"*
* *"Search Flipkart for mobile phones"*
* *"Search Amazon for mechanical keyboards"*
* *"Search GitHub for fast whisper"*
* *"Search Google for Python asyncio tutorial"*
* *"Search AKTU for syllabus 2026"*

### 5.3 Web Search
When no specific website is specified:
* *"Search the web for best dynamic programming roadmap"*
* *"Search the internet for binary tree problems"*
* *"Google search modern web design principles"*

### 5.4 YouTube Media & Shorts Control
* *"Play Hanuman Chalisa on YouTube"*
* *"Play lofi music on YouTube"*
* *"Open YouTube Shorts"* / *"Play Shorts"* / *"Watch funny shorts"*
* Auto Shorts: *"Start auto shorts"* (scrolls shorts automatically every 15s)
* *"Stop auto shorts"* / *"Stop scrolling"*

### 5.5 Browser Tab Management
* *"Next tab"* / *"Switch to next tab"*
* *"Previous tab"*
* *"Close tab"* / *"Close current tab"*
* *"Close NOVA tabs"* / *"Close research tabs"* (Closes tabs opened during NOVA automated research tasks)

### 5.6 Page Navigation & Scrolling
* *"Scroll down"* / *"Scroll down the page"* / *"Neeche scroll karo"*
* *"Scroll up"* / *"Scroll up the page"* / *"Upar scroll karo"*
* *"Scroll to the top"* / *"Go to top"* / *"Scroll all the way up"*
* *"Scroll to the bottom"* / *"Scroll to end"* / *"Scroll all the way down"*
* *"Go back"* / *"Previous page"*
* *"Go forward"* / *"Next page"*

### 5.7 Page Reading & Summarization
* **Status**: ✅ WORKING
* **What it does internally**:
  Extracts document text from the active browser tab via AppleScript DOM execution (`document.body.innerText`), cleans whitespace, and passes the content to `ProviderManager` with a summarization prompt.
* **Commands**:
  * *"Read what's on this page"*
  * *"Summarize this webpage"*
  * *"Explain this page"*

---

## 6. Screen Control

### 6.1 Screenshot Capture
* **Status**: ✅ WORKING
* **Mac Permissions**: 🔒 REQUIRES PERMISSION (Screen Recording in *System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Screen Recording*)
* **Implementation File**: `core/screenshot.py`
* **What it does internally**:
  1. Performs preflight check via Quartz `CGPreflightScreenCaptureAccess()` and temporary `/tmp` probe.
  2. Creates output directory `~/Desktop/NOVA Screenshots/` if not present.
  3. Executes native macOS command: `/usr/sbin/screencapture -x -T 0 <target_path>`.
  4. Generates formatted timestamped file: `NOVA_Screenshot_YYYY-MM-DD_HH-MM-SS.png`.
  5. Updates `environment_observer` context so subsequent commands can refer to "it" or "the screenshot".
* **Commands**:
  * *"Take a screenshot"*
  * *"Capture screenshot"*
  * *"Capture the screen"*
  * *"Nova, take a screenshot"*
  * *"Screenshot lo"*

---

### 6.2 Screen Recording
* **Status**: ✅ WORKING
* **Mac Permissions**: 🔒 REQUIRES PERMISSION (Screen Recording in *System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Screen Recording*)
* **Implementation File**: `core/screen_recording.py`
* **What it does internally**:
  1. Checks macOS Screen Recording permissions.
  2. Spawns background process group: `screencapture -v ~/Desktop/NOVA Recordings/NOVA_Screen_YYYY-MM-DD_HH-MM-SS.mp4`.
  3. Tracks active recording state (`ctx.active_screen_recording = True`).
  4. On stop: Sends `SIGINT` to the process group, cleanly flushing MP4 video headers, and verifies final video file size.
* **Commands**:
  * **Start**:
    * *"Start screen recording"*
    * *"Start recording my screen"*
    * *"Record the screen"*
    * *"Screen recording shuru karo"*
  * **Stop**:
    * *"Stop screen recording"*
    * *"Stop recording"*
    * *"Finish screen recording"*
    * *"Screen recording band karo"*

---

### 6.3 Screen Understanding & Error Explanation
* **Status**: ✅ WORKING (Semantic Vision + Accessibility Tree)
* **Mac Permissions**: 🔒 Screen Recording & Accessibility permissions
* **Implementation Files**: `core/computer_agent.py`, `core/visual/analysis.py`, `core/visual/observer.py`
* **What it does internally**:
  * NOVA's screen vision is **hybrid**:
    1. **Active Context Observer**: First checks `EnvironmentObserver` for active application, focused window title, current folder, or browser URL.
    2. **Accessibility Tree Extraction**: Queries System Events via AppleScript to extract active buttons, text inputs, sheets, and error dialogs.
    3. **AI Vision & Semantic Analysis**: When deep explanation is required, captures a snapshot and calls `ProviderManager.generate_response(..., task_type=TaskType.REASONING)`.
* **Commands**:
  * *"What am I looking at?"*
  * *"What is on my screen?"*
  * *"What are we looking at?"*
  * *"Screen pe kya hai?"*
  * *"What error is on my screen?"*
  * *"Explain this error"*
  * *"Error samjhao"*

---

## 7. Mouse & Cursor Control

* **Status**: ✅ WORKING
* **Mac Permissions**: 🔒 REQUIRES PERMISSION (Accessibility in *System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Accessibility*)
* **Implementation Files**: `core/visual/interaction.py`, `core/visual/resolver.py`, `core/computer_agent.py`
* **What it does internally**:
  * Uses macOS `Quartz.CGEventCreateMouseEvent` to dispatch real hardware cursor events.
  * Resolves UI element targets using fuzzy match and OCR bounding box coordinates.
  * Safe execution: Checks confidence score ($>0.70$) before clicking; asks clarification if target is ambiguous.

### Supported Operations:
* **Click UI Button / Link**:
  * *"Click Login"*
  * *"Click the Login button"*
  * *"Click Search"*
  * *"Click Submit"*
  * *"Click Download"*
  * *"Tap Sign Up"*
* **Dismiss Popups / Dialogs**:
  * *"Close popup"* / *"Dismiss dialog"* / *"Close alert"* / *"Popup hatao"*
  *(Clicks the modal close button or dispatches hardware `Escape` key)*
* **Visual Search & Scroll**:
  * *"Scroll down until you find Pricing"*
  * *"Scroll until you find Download"*
  *(Sequentially scrolls down up to 6 times while verifying element appearance)*

---

## 8. Keyboard & Typing

* **Status**: ✅ WORKING
* **Mac Permissions**: 🔒 REQUIRES PERMISSION (Accessibility in *System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Accessibility*)
* **Implementation File**: `core/visual/interaction.py`
* **What it does internally**:
  * Uses Quartz `CGEventCreateKeyboardEvent` or AppleScript System Events keystrokes.
  * Supports direct typing into currently focused field or auto-focusing target input elements.

### Supported Operations:
* **Type Text into Field**:
  * *"Type John Doe in Name"*
  * *"Type admin@example.com in the email field"*
  * *"Enter password123 in Password"*
* **Key Presses & Shortcuts**:
  * Hardware `Return` / `Enter` (when `submit=True`)
  * Hardware `Escape` (used in popup dismissal)

---

## 9. Text Editor / Notepad / TextEdit

* **Status**: ✅ WORKING
* **Mac Permissions**: None (Uses native file I/O and `/usr/bin/open` with TextEdit)
* **Implementation Files**: `desktop/editor.py`, `desktop/apps.py`, `intent/matcher.py`

### Critical Distinction: Explanation vs. Document Action
* If you say: *"Explain bubble sort"* $\rightarrow$ Treated as **informational query**; spoken AI explanation delivered.
* If you say: *"Write bubble sort in TextEdit"* $\rightarrow$ Treated as **computer action**; executes AI code generation, writes file to disk, and opens TextEdit.

### What it does internally:
1. Regex matches `write <topic> in textedit / notepad` or `open textedit and write <topic>`.
2. Generates formatted content via `ProviderManager` (or structured template fallback).
3. Chooses appropriate filename (e.g. `bubble_sort.cpp`, `reverse_string.py`, `leave_application.txt`).
4. Saves the file to `~/Desktop/NOVA Documents/<filename>`.
5. Launches macOS `TextEdit` displaying the saved document.

### Supported Commands:
* *"Open TextEdit"*
* *"Open Notepad"* (automatically maps to TextEdit)
* *"Write an application for college leave in TextEdit"*
* *"Write a bubble sort program in TextEdit"*
* *"Write a python program to reverse a string in TextEdit"*
* *"Open TextEdit and write notes on operating systems"*
* *"Write what is love in TextEdit"*

---

## 10. Files & Folders

* **Status**: ✅ WORKING
* **Mac Permissions**: None for standard user folders (`Desktop`, `Documents`, `Downloads`, `Projects`)
* **Implementation File**: `desktop/files.py`
* **Safety Policy**: Governed by `DesktopSafetyPolicy` (`desktop/safety.py`). Strictly blocks deletion or creation in system root directories (`/`, `/System`, `/Library`, `/usr`, `/bin`).

### 10.1 Create Folder
* *"Create a folder called DSA on Desktop"*
* *"Make a folder named College in Documents"*
* *"Create a folder called Trees inside my DSA folder"*
* *"Create a folder called Test"* (defaults to Desktop)

### 10.2 Open Folder in Finder
* *"Open my DSA folder"*
* *"Open the Downloads folder"*
* *"Open the Documents folder"*
* Contextual reference: *"Open it"* or *"Open that folder"* (resolves to the folder just created)

### 10.3 Create File
* *"Create a file called main.cpp on Desktop"*
* *"Create README.md"*
* *"Make a file named notes.txt in Documents"*

### 10.4 Safe Delete (Trash with Confirmation)
* **What it does internally**:
  NOVA will **never** immediately delete an item. It sets a pending confirmation state and asks: *"Do you want me to delete <item>?"*.
  Once confirmed, it moves the item safely to macOS Trash (`~/.Trash`) via AppleScript Finder rather than `rm -rf`.
* **Commands**:
  * *"Delete DSA folder"* $\rightarrow$ *"Do you want me to delete DSA? (Say Yes or No)"*
  * *"Delete this file"* / *"Remove it"*

---

## 11. Multitasking / Multi-Step Autonomous Commands

* **Status**: ✅ WORKING
* **Implementation Subsystem**: `core/task_agent/` (Task Agent V3: Planner, Replanner, Executor, Context, Verifier)
* **Capability Registry**: 22 registered, verified primitive capabilities (`core/task_agent/registry.py`)

### How Multitasking Works
1. **Plan Deconstruction**: Breaks user request into sequential `TaskStep` objects.
2. **Context Propagation**: Steps share a live `TaskContext`. If Step 1 creates a folder `"DSA"`, Step 2 creates subfolders inside it by resolving `ctx.last_created_folder`.
3. **Automated Verification**: Every step has a post-condition verifier (e.g. `dir_exists`, `file_exists`, `app_running`, `tab_loaded`).
4. **Deterministic Fast-Paths**: Handled in under $5\text{ms}$ without LLM latency for common developer patterns:
   * *Project with subfolders*
   * *Project with initial source files*
   * *Web research + save results to file*
5. **AI Synthesis**: For arbitrary compound goals, uses `ProviderManager` to generate JSON task plans.

### Verified Multi-Step Commands:
* *"Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders"*
* *"Create a C++ project with main.cpp and README.md"*
* *"Create a Python project called WebScraper with app.py and requirements.txt"*
* *"Search the web for DSA roadmap and save the link in a file on Desktop"*

---

## 12. Search

* **Status**: ✅ WORKING
* **Implementation Files**: `browser/sites/`, `browser/parser.py`, `intent/matcher.py`

### 12.1 Web Search Engines
* *"Search the web for machine learning basics"*
* *"Search Google for Python tutorials"*
* *"Google search best laptops 2026"*

### 12.2 E-Commerce Search
* *"Search Flipkart for mobile phones"*
* *"Search Amazon for noise cancelling headphones"*
* *"Go to Flipkart and search for running shoes"*

### 12.3 Code & Academic Search
* *"Search GitHub for fast whisper mac"*
* *"Search AKTU for exam schedule"*
* *"Search Wikipedia for Quantum Computing"*

---

## 13. Memory Subsystem

* **Status**: ⚠️ PARTIALLY WORKING (Durable JSON ✅ WORKING; ChromaDB Semantic Store ⚠️ Falls back to JSON if vector dependencies uninitialized)
* **Implementation Files**: `memory/memory_manager.py`, `memory/vector_store.py`

### Important Architectural Note on Memory Commands
> **NOVA does not have explicit command keywords like `ActionType.REMEMBER`**.
> Memory in NOVA is an **autonomous background persistence layer**:
> 1. Every conversational interaction is automatically categorized and stored in `data/memory_store.json`.
> 2. On every new user query, NOVA automatically calls `_build_memory_summary(query_text)` to retrieve top-5 relevant memories and injects them into the prompt.
> 3. If you say *"Remember that my favorite language is Python"*, conversational AI answers *"I will remember that"*, and `_write_memory()` commits it to long-term storage.

---

## 14. Voice System Architecture

* **Status**: ✅ WORKING
* **Implementation Package**: `voice/`

### Components & State Machine
1. **Microphone Capture**: `MicrophoneManager` (`voice/microphone.py`) streaming at 16,000 Hz 16-bit mono.
2. **VAD (Voice Activity Detection)**: `VoiceActivityDetector` (`voice/vad.py`) using Silero VAD. Detects speech onset and offsets automatically with 0.8s silence hang-time.
3. **STT (Speech-to-Text)**: `TranscriptionManager` (`voice/transcriber.py`) powered by `faster-whisper` (`base` or `small` model).
4. **TTS (Text-to-Speech)**: `SpeakerManager` (`voice/speaker.py`) using Kokoro TTS (`af_heart`), falling back to Edge-TTS or macOS native `say`.
5. **Quality Gate**: `TranscriptQualityGate` (`voice/quality.py`) filters low-confidence hallucinations and background noise artifacts.

### Voice States:
* `LISTENING`: Microphone is live; VAD scanning for speech energy.
* `PROCESSING`: Audio captured; Whisper transcribing and router matching intent.
* `SPEAKING`: TTS output streaming to speakers. (Microphone listening pauses during TTS playback to avoid audio echo loops).

---

## 15. AI Providers & Quota Handling

* **Status**: ✅ Multi-Provider Architecture Implemented
* **Implementation Package**: `providers/`

### Configured Providers:

| Provider | Default Model | Primary Task Optimization | Fallback Rank | Status |
|----------|---------------|---------------------------|---------------|--------|
| **Google Gemini** | `gemini-2.5-flash` | Reasoning, Multimodal, General | 1 | ✅ Working (with valid `GEMINI_API_KEY`) |
| **Groq** | `llama-3.3-70b-versatile` | Ultra-fast execution, Coding | 2 | ✅ Working (with valid `GROQ_API_KEY`) |
| **OpenRouter** | `meta-llama/llama-3.3-70b-instruct` | Redundant General Fallback | 3 | ✅ Working (with valid `OPENROUTER_API_KEY`) |
| **Cerebras** | `llama3.1-70b` | High throughput, Cheap | 4 | ✅ Working (with valid `CEREBRAS_API_KEY`) |

### Quota & Rate Limit Handling
* `ProviderManager` maintains provider health status.
* If a provider returns HTTP $429$ (Rate Limit / Quota Exceeded) or $503$, the manager marks it temporarily unhealthy and transparently cascades to the next provider in `_ROUTING_PRIORITIES`.
* No raw SDK exceptions leak to the user; if all providers fail, a clean spoken response is delivered.

---

## 16. Error Handling & Truthful Reporting

NOVA strictly enforces **truthful feedback** across all subsystems:
1. **No Fake Success**: If an action fails (e.g. app not found, permission denied, AppleScript error), NOVA reports the real error rather than falsely stating "Done Boss".
2. **Missing Permissions**: If Screen Recording or Accessibility is missing, NOVA specifically directs the user to the exact macOS Settings pane.
3. **Missing CLI Dependencies**: If a command requires an uninstalled tool (e.g. `blueutil`), NOVA specifies the Homebrew installation command.
4. **Safety Confirmations**: High-risk actions (File deletion, System shutdown) pause execution and require explicit user authorization.

---

## 17. Command Prefixes & Natural Language Variations

Below is the verified matrix showing how natural phrasing maps to base commands:

### Base: "Open Telegram"
* *"Open Telegram"*
* *"Open Telegram app"*
* *"Launch Telegram"*
* *"Start Telegram"*
* *"Nova, open Telegram"*
* *"Nova open Telegram"*
* *"Now open Telegram app"*
* *"Please open Telegram"*
* *"Boss, open Telegram"*
* *"Can you please open Telegram?"*
* *"Could you open Telegram for me?"*

### Base: "Increase Volume"
* *"Increase volume"*
* *"Turn up volume"*
* *"Make it louder"*
* *"Volume badhao"*
* *"Nova, increase the volume of my Mac"*
* *"Can you please turn up the volume?"*

### Base: "Take a Screenshot"
* *"Take a screenshot"*
* *"Capture screenshot"*
* *"Capture the screen"*
* *"Take a screenshot, Nova"*
* *"Screenshot lo"*
* *"Can you take a screenshot for me please?"*

*(Phrases that cause problems: Ambiguous bare words like "this" or "delete" without prior context prompt a clarification question from NOVA).*

---

## 18. Complete Command Cheat Sheet

| Category | Feature | Spoken Commands (What You Can Say) | Status | Permissions |
|:---------|:--------|:-----------------------------------|:------:|:-----------:|
| **System** | Volume Relative | *"Increase volume"*, *"Decrease volume"*, *"Turn up the volume"* | ✅ WORKING | None |
| **System** | Volume Absolute | *"Set volume to 70%"*, *"Set volume to 100%"*, *"Make volume 50%"* | ✅ WORKING | None |
| **System** | Volume Mute | *"Mute volume"*, *"Unmute volume"* | ✅ WORKING | None |
| **System** | Brightness Relative | *"Increase brightness"*, *"Decrease brightness"*, *"Make screen brighter"* | ✅ WORKING | 🔒 Accessibility (fallback) |
| **System** | Brightness Absolute | *"Set brightness to 80%"*, *"Make brightness 50%"* | ✅ WORKING | 🔒 Accessibility (fallback) |
| **System** | Wi-Fi Status | *"Is Wi-Fi on?"*, *"What Wi-Fi am I connected to?"* | ✅ WORKING | None |
| **System** | Wi-Fi Toggle | *"Turn Wi-Fi on"*, *"Turn Wi-Fi off"* | ✅ WORKING | None |
| **System** | Bluetooth Status | *"Is Bluetooth on?"*, *"Check Bluetooth status"* | ✅ WORKING | None |
| **System** | Bluetooth Toggle | *"Turn Bluetooth on"*, *"Turn Bluetooth off"* | ⚠️ PARTIAL | 🔒 Requires `blueutil` |
| **System** | Clipboard | *"What is in my clipboard?"*, *"Clear clipboard"* | ✅ WORKING | None |
| **System** | Lock Screen | *"Lock screen"*, *"Lock my Mac"* | ✅ WORKING | None |
| **System** | Shutdown | *"Shut down my Mac"*, *"Shutdown system"* | ✅ WORKING | 🔒 User Confirmation |
| **Apps** | Launch App | *"Open Telegram"*, *"Open VS Code"*, *"Launch Spotify"*, *"Open Chrome"* | ✅ WORKING | None |
| **Apps** | Quit App | *"Close Telegram"*, *"Quit VS Code"*, *"Close TextEdit"* | ✅ WORKING | None |
| **Browser** | Open Website | *"Open YouTube"*, *"Open Flipkart"*, *"Open GitHub"*, *"Open AKTU"* | ✅ WORKING | 🔒 Automation |
| **Browser** | Web Search | *"Search the web for..."*, *"Google search..."* | ✅ WORKING | 🔒 Automation |
| **Browser** | In-Site Search | *"Search YouTube for..."*, *"Search Flipkart for mobile phones"* | ✅ WORKING | 🔒 Automation |
| **Browser** | YouTube Shorts | *"Open YouTube Shorts"*, *"Start auto shorts"*, *"Stop auto shorts"* | ✅ WORKING | 🔒 Automation |
| **Browser** | Tabs | *"Next tab"*, *"Previous tab"*, *"Close tab"*, *"Close NOVA tabs"* | ✅ WORKING | 🔒 Automation |
| **Browser** | Page Navigation | *"Go back"*, *"Go forward"*, *"Scroll down"*, *"Scroll up"*, *"Scroll to bottom"* | ✅ WORKING | 🔒 Automation |
| **Browser** | Page Reading | *"Read what's on this page"*, *"Summarize this webpage"* | ✅ WORKING | 🔒 Automation |
| **Screen** | Screenshot | *"Take a screenshot"*, *"Capture the screen"* | ✅ WORKING | 🔒 Screen Recording |
| **Screen** | Screen Recording | *"Start screen recording"*, *"Stop screen recording"* | ✅ WORKING | 🔒 Screen Recording |
| **Screen** | Screen Awareness | *"What am I looking at?"*, *"What is on my screen?"*, *"Explain this error"* | ✅ WORKING | 🔒 Screen + Accessibility |
| **Mouse** | UI Clicking | *"Click Login"*, *"Click Submit"*, *"Click Search"* | ✅ WORKING | 🔒 Accessibility |
| **Mouse** | Popups | *"Close popup"*, *"Dismiss dialog"* | ✅ WORKING | 🔒 Accessibility |
| **Mouse** | Visual Scroll | *"Scroll down until you find Pricing"* | ✅ WORKING | 🔒 Accessibility |
| **Keyboard** | UI Typing | *"Type John Doe in Name"*, *"Enter admin@example.com in Email"* | ✅ WORKING | 🔒 Accessibility |
| **Editor** | Document Writer | *"Write a leave application in TextEdit"*, *"Write bubble sort in TextEdit"* | ✅ WORKING | None |
| **Files** | Create Folder | *"Create a folder called DSA on Desktop"*, *"Make a folder named Test"* | ✅ WORKING | None |
| **Files** | Open Folder | *"Open my DSA folder"*, *"Open Downloads folder"*, *"Open it"* | ✅ WORKING | None |
| **Files** | Create File | *"Create a file called main.cpp on Desktop"*, *"Create README.md"* | ✅ WORKING | None |
| **Files** | Trash Item | *"Delete DSA folder"* (Trashes to `~/.Trash` after user confirmation) | ✅ WORKING | 🔒 User Confirmation |
| **Multi-Step** | Autonomous Task | *"Create a folder called DSA Project on Desktop with Arrays and Trees"* | ✅ WORKING | None |
| **AI Chat** | Conversational | *"Explain Dijkstra's algorithm"*, *"What is dynamic programming?"* | ✅ WORKING | None |

---

## 19. Known Limitations

### Limitation 1: Bluetooth Hardware Toggling
* **Feature**: Bluetooth On / Off Toggle
* **Problem**: macOS does not provide a standard non-interactive command-line interface for toggling Bluetooth power without private Framework access.
* **Current Behavior**: NOVA checks and reports status accurately using `system_profiler`. Toggling returns an instructional message stating that `blueutil` is required.
* **Expected Behavior**: Direct toggling without external utilities.
* **Possible Cause**: macOS security architecture restrictions on Bluetooth daemon.
* **Relevant File**: `mac_control/actions/bluetooth.py`
* **Status**: ⚠️ PARTIALLY WORKING (Works if `brew install blueutil` is executed by user).

### Limitation 2: Visual Clicking in Non-Standard Web / Canvas Elements
* **Feature**: Visual UI target clicking (`click_ui_element`)
* **Problem**: Applications rendering with custom WebGL, Flutter, or HTML5 Canvas do not expose standard macOS Accessibility elements.
* **Current Behavior**: Target resolution score falls below threshold ($<0.70$); NOVA politely reports: *"I'm not sure which element to click. Could you please clarify?"*.
* **Expected Behavior**: Pure pixel-based fallback clicking.
* **Possible Cause**: Accessibility tree relies on native Cocoa / WebKit accessibility nodes.
* **Relevant File**: `core/visual/analysis.py`, `core/visual/resolver.py`
* **Status**: ⚠️ PARTIALLY WORKING (Native Cocoa / Standard Web UI works; Canvas elements require clarification).

### Limitation 3: Third-Party Browser Support
* **Feature**: Browser Tab & DOM Control
* **Problem**: Browser automation specifically targets Google Chrome and Safari via AppleScript.
* **Current Behavior**: If the user's primary browser is Firefox, Arc, or Brave, URL launches work via `open`, but deep DOM reading and tab management do not attach.
* **Expected Behavior**: Universal browser automation.
* **Possible Cause**: Firefox does not expose the AppleScript automation dictionary for tab/document query.
* **Relevant File**: `browser/engine.py`
* **Status**: ⚠️ PARTIALLY WORKING (Google Chrome and Safari fully supported; others limited to URL launching).

---

## 20. Commands to Test (Verification Checklist)

Use this checklist anytime to verify your live NOVA installation:

### System Controls
- [ ] `"Nova, increase volume"`
- [ ] `"Nova, set volume to 70%"`
- [ ] `"Nova, mute volume"`
- [ ] `"Nova, unmute volume"`
- [ ] `"Nova, increase brightness"`
- [ ] `"Nova, set brightness to 80%"`
- [ ] `"Nova, is Wi-Fi on?"`
- [ ] `"Nova, what Wi-Fi am I connected to?"`
- [ ] `"Nova, is Bluetooth on?"`
- [ ] `"Nova, what is in my clipboard?"`

### Applications
- [ ] `"Nova, open Telegram"`
- [ ] `"Nova, open VS Code"`
- [ ] `"Nova, open Google Chrome"`
- [ ] `"Nova, close Telegram"`

### Browser & Search
- [ ] `"Nova, open YouTube"`
- [ ] `"Nova, search Flipkart for mobile phones"`
- [ ] `"Nova, search YouTube for DSA tutorials"`
- [ ] `"Nova, scroll down"`
- [ ] `"Nova, scroll to bottom"`
- [ ] `"Nova, close tab"`

### Screen Actions
- [ ] `"Nova, take a screenshot"`
- [ ] `"Nova, start screen recording"`
- [ ] `"Nova, stop screen recording"`
- [ ] `"Nova, what am I looking at?"`

### Desktop Documents & Files
- [ ] `"Nova, write a leave application in TextEdit"`
- [ ] `"Nova, create a folder called DSA on Desktop"`
- [ ] `"Nova, open my DSA folder"`
- [ ] `"Nova, create a file called main.cpp on Desktop"`

### Multi-Step Autonomous Task
- [ ] `"Nova, create a folder called Project Alpha on Desktop with Frontend and Backend folders"`

---
*Document compiled and verified for NOVA on macOS.*
