# 17 — macOS Application Integrations

## Overview
NOVA interfaces with macOS desktop applications using native process management, AppleScript, Accessibility APIs, and CLI utilities.

---

## 📱 Controlled Applications

| Application | Launch / Open | Close / Quit | State Inspection | Interaction Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **Google Chrome** | `open -a "Google Chrome"` | `osascript quit` / `pkill` | Active tab URL, title, tab count | AppleScript + Quartz |
| **Safari** | `open -a Safari` | `osascript quit` / `pkill` | Active tab URL, title | AppleScript + Quartz |
| **VS Code** | `code <path>` / `open -a "Visual Studio Code"` | `pkill "Visual Studio Code"` | Active window title | CLI + AXUIElement |
| **Finder** | `open <path>` | — | Selected files/folders, open path | AppleScript Finder Suite |
| **Terminal / iTerm** | `open -a Terminal` | `osascript quit` | Front window title | AppleScript + CLI |
| **TextEdit** | `open -a TextEdit <file>`| `osascript quit` | Active document | AppleScript + FS |
| **Photo Booth / Camera**| `open -a "Photo Booth"` | `pkill "Photo Booth"` | Window active state | `CameraManager` / AVFoundation |
| **Spotify** | `open -a Spotify` | `osascript quit` | Active track & artist | AppleScript Spotify Suite |
| **System Settings** | `open -a "System Settings"` | `osascript quit` | Front window title | AppleScript |
