# NOVA User Manual
**Practical Owner Guide for Everyday Use & Natural Voice Control**

---

## 1. How to Talk to NOVA

NOVA understands natural language. You don't have to memorize rigid commands or robot phrases.

### Wake-Word & Conversational Prefixes
You can start your request with a wake word, a polite conversational opener, or jump straight into the command:
- **Direct**: `"Open VS Code"`
- **With Wake Word**: `"NOVA, open VS Code"`, `"Hey NOVA, launch Chrome"`
- **Polite & Conversational**: `"Can you please open VS Code?"`, `"Could you open TextEdit for me?"`, `"I want to open VS Code"`
- **Bilingual (Hindi/English)**: `"NOVA, camera kholo"`, `"Wi-Fi on karo"`, `"Stop research, रहने दो"`

### Pronouns & Context ("This", "That", "It")
NOVA remembers what happened in the previous turn and what is currently on your screen:
- Say `"Create a folder called DSA on Desktop"`, then say `"Open it"`. NOVA knows *"it"* refers to `~/Desktop/DSA`.
- If you're reading a webpage in Chrome, say `"Summarize this page"`.
- If you see an error on your screen, say `"Explain this error"`.

---

## 2. Top 20 Most Useful Commands

1. `"Open VS Code"` — Launches Visual Studio Code.
2. `"Create a folder called DSA on Desktop"` — Creates a new folder on your Desktop.
3. `"Now create main.cpp inside it"` — Creates `main.cpp` inside your active folder with starter boilerplate.
4. `"Open DSA folder"` — Reveals the folder in Finder.
5. `"Write an application for college leave"` — Generates a leave application and opens it in TextEdit.
6. `"Go to AKTU website"` — Opens Chrome and navigates to the university portal.
7. `"In Flipkart search mobile phones"` — Navigates directly to Flipkart search results.
8. `"Play Kesariya"` — Scores official music uploads on YouTube and plays the track.
9. `"Open YouTube Shorts"` — Opens Shorts in Chrome and prepares arrow-key scrolling.
10. `"Next Short"` — Scrolls to the next Short.
11. `"What am I looking at?"` — Tells you the active window, open website, or current folder.
12. `"Explain this error"` — Captures the screen, uses OCR, and explains the error message.
13. `"Close this popup"` — Clicks the close `✕` button or dismisses modal dialogs.
14. `"Open camera"` — Opens Photo Booth as a live viewfinder.
15. `"What is in my clipboard?"` — Reads your copied text out loud.
16. `"Clear my clipboard"` — Empties your system clipboard buffer.
17. `"Start recording screen"` — Records your display and saves to `~/Movies/NOVA_Recordings/`.
18. `"Stop recording"` — Stops and saves the video file.
19. `"Turn off Wi-Fi"` — Disables macOS Wi-Fi.
20. `"Stop"` / `"Cancel"` — Immediately halts any active multi-step autonomous task or scrolling loop.

---

## 3. Applications

- `"Open VS Code"`, `"Launch VS Code"`, `"Start VS Code"`
- `"Open Google Chrome"`, `"Launch Chrome"`
- `"Open TextEdit"`, `"Open Notepad"`
- `"Open Spotify"`
- `"Open Terminal"`, `"Launch Terminal"`
- `"Close VS Code"`, `"Quit Chrome"`

---

## 4. Browser & Web Navigation

- `"Go to AKTU website"`, `"Open Flipkart"`, `"Open GitHub"`
- `"Search Google for Python tutorials"`
- `"In Flipkart search mobile phones"`, `"On YouTube search lofi music"`
- `"Open a new tab"`, `"Close this tab"`
- `"Next tab"`, `"Previous tab"`, `"Switch to Flipkart tab"`
- `"Scroll down"`, `"Scroll up"`, `"Scroll to top"`, `"Scroll to bottom"`
- `"Read this webpage"`, `"Summarize this article"`

---

## 5. Files & Folders

- `"Create a folder called DSA on Desktop"`
- `"Make a folder named Projects on Desktop"`
- `"Open DSA folder"`, `"Open it"`
- `"Create main.cpp inside it"`
- `"Delete this folder"` *(NOVA will ask for verbal confirmation first)*

---

## 6. VS Code & Coding

- `"Create a Python file and write a calculator program"`
- `"Create a C++ file and write binary search"`
- `"Create a C++ project with main.cpp and README.md"`
- `"Open this project in VS Code"`

---

## 7. Writing & Documents

- `"Write an application for college leave"`
- `"Write an apology email for delay"`
- `"Open Notepad and write a project report"`

---

## 8. Music & YouTube

- `"Play Kesariya"`, `"Play Believer"`, `"Play Shape of You"`
- `"Open YouTube Shorts"`
- `"Next Short"`, `"Previous Short"`
- `"Stop Shorts"`

---

## 9. Screen & Visual Actions (Computer Agent V2)

- `"What am I looking at?"`
- `"Explain this error"`
- `"Click the blue submit button"`, `"Click login"`
- `"Type hello into search"`
- `"Close this popup"`
- `"Scroll until you find pricing"`

---

## 10. Screen Recording

- `"Start recording screen"`, `"Record my screen"`
- `"Stop recording"`, `"Stop screen recording"`
- *Saved at*: `~/Movies/NOVA_Recordings/recording_<timestamp>.mov`

---

## 11. Camera

- 🟢 `"Open camera"`, `"Launch camera"`, `"Open Photo Booth"` — Opens live viewfinder.
- 🟡 `"Take a picture"`, `"Take my photo"`, `"Click a photo"` — Captures photo to `~/Pictures/NOVA/` *(Requires webcam + FFmpeg)*.

---

## 12. System Clipboard

- 🟢 `"What is in my clipboard?"`, `"Show my clipboard"`, `"What did I copy?"` — Reads clipboard.
- 🟢 `"Clear my clipboard"`, `"Empty the clipboard"` — Clears clipboard buffer.
- 🟢 `"Copy this to clipboard"` — Copies active URL or created file path.

---

## 13. Mac Controls & System

- 🟢 `"Set volume to 50%"`, `"Volume up"`, `"Volume down"`, `"Mute"`, `"Unmute"`
- 🟢 `"Set brightness to 80%"`, `"Brightness up"`, `"Dim screen"` *(MacBook built-in display)*
- 🟢 `"Lock screen"`, `"Lock my mac"` — Locks macOS session.
- 🟢 `"Shutdown NOVA"`, `"Bye NOVA"`, `"Exit"` — Gracefully closes NOVA.

---

## 14. Wi-Fi & Bluetooth

- 🟢 `"Turn on Wi-Fi"`, `"Enable Wi-Fi"`, `"Wi-Fi on karo"`
- 🟢 `"Turn off Wi-Fi"`, `"Disable Wi-Fi"`, `"Wi-Fi off karo"`
- 🟢 `"Is Wi-Fi on?"`, `"Check Wi-Fi status"`
- 🟡 `"Turn on Bluetooth"`, `"Turn off Bluetooth"`, `"Is Bluetooth on?"` *(Requires `blueutil` CLI)*

---

## 15. Autonomous Tasks (Multi-Step V3)

Compound tasks that NOVA breaks down into multiple steps:
- `"Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders"`
- `"Create a C++ project with main.cpp and README.md"`
- `"Find a Python tutorial and save the useful link in a text file"`

---

## 16. Stop / Cancel / Interruption

Say any of the following to immediately stop any active task, script, or scrolling loop:
- `"Stop"`
- `"Cancel"`
- `"Never mind"`
- `"Abort"`
- `"Stop doing that"`
- `"रहने दो"` / `"रुको"`
