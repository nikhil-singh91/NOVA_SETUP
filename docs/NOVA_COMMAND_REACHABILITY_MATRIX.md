# NOVA Command Reachability Matrix

---

## Command Verification & Execution Pipeline Matrix

| Command Phrase | Voice | Text | Intent Found | Action Found | Verification | Test Evidence | Operational Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `"Open VS Code"` | YES | YES | YES (`LAUNCH_APP`) | YES (`AppLauncher`) | YES (`pgrep`) | UNIT (`test_desktop_actions`) | 🟢 CONFIRMED |
| `"Close VS Code"` | YES | YES | YES (`CLOSE_APP`) | YES (`AppLauncher`) | YES (`pgrep`) | UNIT (`test_desktop_actions`) | 🟢 CONFIRMED |
| `"Create a folder called DSA on Desktop"` | YES | YES | YES (`CREATE_DESKTOP_FOLDER`) | YES (`FileSystemManager`) | YES (`Path.is_dir`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"Open DSA folder"` | YES | YES | YES (`OPEN_FOLDER`) | YES (`FileSystemManager`) | YES (`Finder`) | UNIT (`test_desktop_actions`) | 🟢 CONFIRMED |
| `"Create main.cpp inside it"` | YES | YES | YES (`CREATE_DESKTOP_FILE`) | YES (`FileSystemManager`) | YES (`Path.is_file`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"Delete this folder"` | YES | YES | YES (`DELETE_ITEM`) | YES (Intercept $\rightarrow$ `safe_move_to_trash`) | YES (Trash verify) | UNIT (`test_environment_context`) | 🟢 CONFIRMED (Safety Prompt) |
| `"Write an application for college leave"` | YES | YES | YES (`GENERATE_AND_WRITE_DOCUMENT`) | YES (`DocumentEditor`) | YES (`Path.exists`) | UNIT (`test_natural_language_intents`) | 🟢 CONFIRMED |
| `"Go to AKTU website"` | YES | YES | YES (`OPEN_WEBSITE`) | YES (`BrowserEngine`) | YES (`URL check`) | UNIT (`test_browser_actions`) | 🟢 CONFIRMED |
| `"Open Flipkart"` | YES | YES | YES (`OPEN_WEBSITE`) | YES (`BrowserEngine`) | YES (`URL check`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"Search Google for Python tutorial"` | YES | YES | YES (`SEARCH_WEB`) | YES (`BrowserEngine`) | YES (`Google URL`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"In Flipkart search mobile phones"` | YES | YES | YES (`SEARCH_WEBSITE`) | YES (`FlipkartSkill`) | YES (`URL check`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"Open a new tab"` | YES | YES | YES (`OPEN_NEW_TAB`) | YES (`BrowserEngine`) | YES (`Tab count`) | UNIT (`test_browser_actions`) | 🟢 CONFIRMED |
| `"Close this tab"` | YES | YES | YES (`CLOSE_CURRENT_TAB`) | YES (`BrowserEngine`) | YES (`Tab count`) | UNIT (`test_browser_actions`) | 🟢 CONFIRMED |
| `"Next tab"` | YES | YES | YES (`NEXT_TAB`) | YES (`BrowserEngine`) | YES (`Tab index`) | UNIT (`test_browser_actions`) | 🟢 CONFIRMED |
| `"Previous tab"` | YES | YES | YES (`PREVIOUS_TAB`) | YES (`BrowserEngine`) | YES (`Tab index`) | UNIT (`test_browser_actions`) | 🟢 CONFIRMED |
| `"Read this webpage"` | YES | YES | YES (`READ_CURRENT_PAGE`) | YES (`BrowserExtractor`) | YES (`Text len`) | UNIT (`test_browser_actions_v2`) | 🟢 CONFIRMED |
| `"Play Kesariya"` | YES | YES | YES (`PLAY_MEDIA`) | YES (`YouTubeSkill`) | YES (`Video URL`) | UNIT (`test_media_matching`) | 🟢 CONFIRMED |
| `"Open YouTube Shorts"` | YES | YES | YES (`WATCH_SHORTS`) | YES (`YouTubeSkill`) | YES (`Shorts URL`) | UNIT (`test_browser_actions`) | 🟢 CONFIRMED |
| `"Next Short"` | YES | YES | YES (`WATCH_SHORTS`) | YES (`YouTubeSkill`) | YES (`Key press`) | UNIT (`test_browser_actions`) | 🟢 CONFIRMED |
| `"What am I looking at?"` | YES | YES | YES (`WHAT_AM_I_LOOKING_AT`) | YES (`EnvironmentObserver`) | YES (`Context`) | MATRIX (`test_environment_voice_matrix`) | 🟢 CONFIRMED |
| `"Explain this error"` | YES | YES | YES (`EXPLAIN_SCREEN_ERROR`) | YES (`ComputerAgent`) | YES (`OCR/AI`) | MATRIX (`test_computer_agent_matrix`) | 🟢 CONFIRMED |
| `"Click the search button"` | YES | YES | YES (`CLICK_UI_ELEMENT`) | YES (`ComputerAgent`) | YES (`Visual delta`) | MATRIX (`test_computer_agent_matrix`) | 🟢 CONFIRMED |
| `"Close this popup"` | YES | YES | YES (`CLOSE_POPUP`) | YES (`ComputerAgent`) | YES (`Visual delta`) | MATRIX (`test_computer_agent_matrix`) | 🟢 CONFIRMED |
| `"Scroll until you find pricing"` | YES | YES | YES (`SCROLL_UNTIL_VISIBLE`) | YES (`ComputerAgent`) | YES (`OCR match`) | MATRIX (`test_computer_agent_matrix`) | 🟢 CONFIRMED |
| `"Start recording screen"` | YES | YES | YES (`START_SCREEN_RECORDING`) | YES (`ScreenRecordingManager`) | YES (`PID check`) | UNIT (`test_screen_recording`) | 🟢 CONFIRMED |
| `"Stop recording"` | YES | YES | YES (`STOP_SCREEN_RECORDING`) | YES (`ScreenRecordingManager`) | YES (`File size`) | UNIT (`test_screen_recording`) | 🟢 CONFIRMED |
| `"Open camera"` | YES | YES | NO (Fallback) | YES (`CameraManager`) | YES (`Photo Booth`) | UNIT (`test_desktop_actions`) | 🟡 REACHABLE VIA FALLBACK |
| `"Take a photo"` | YES | YES | NO (Fallback) | YES (`CameraManager`) | YES (`File exists`) | UNIT (`test_desktop_actions`) | 🟡 REACHABLE VIA FALLBACK |
| `"Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders"` | YES | YES | YES (`AUTONOMOUS_TASK`) | YES (`TaskExecutor`) | YES (`Holistic dir`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"Create a C++ project with main.cpp and README.md"` | YES | YES | YES (`AUTONOMOUS_TASK`) | YES (`TaskExecutor`) | YES (`Holistic files`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"Find a Python tutorial and save the useful link in a text file"` | YES | YES | YES (`AUTONOMOUS_TASK`) | YES (`TaskExecutor`) | YES (`Holistic doc`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"Stop"` / `"Cancel"` | YES | YES | YES (`CANCEL_ACTION`) | YES (`TaskExecutor.cancel_task`) | YES (`Event clear`) | MATRIX (`test_task_agent_matrix`) | 🟢 CONFIRMED |
| `"Set volume to 50%"` | YES | YES | YES (`CONTROL_VOLUME`) | YES (`MacControlManager`) | YES (`AppleScript`) | UNIT (`test_end_to_end_voice_turn`) | 🟢 CONFIRMED |
| `"Set brightness to 80%"` | YES | YES | YES (`CONTROL_BRIGHTNESS`) | YES (`MacControlManager`) | YES (`AppleScript`) | UNIT (`test_end_to_end_voice_turn`) | 🟢 CONFIRMED |
| `"Lock screen"` | YES | YES | NO (Fallback) | YES (`MacControlManager`) | YES (`AppleScript`) | UNIT (`test_end_to_end_voice_turn`) | 🟡 REACHABLE VIA FALLBACK |
| `"Shutdown NOVA"` | YES | YES | YES (`SYSTEM_SHUTDOWN`) | YES (`VoiceCommandRouter`) | YES (`Lifecycle`) | UNIT (`test_voice_v2`) | 🟢 CONFIRMED |
