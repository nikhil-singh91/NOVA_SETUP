# 19 — NOVA Dependencies & Environment Manifest

## Overview
NOVA uses Python 3.12+ for backend execution and Node.js 18+ for desktop UI development.

---

## 🐍 Python Dependencies (`pyproject.toml` / `requirements.txt`)

| Package | Version Constraint | Purpose |
| :--- | :--- | :--- |
| `pydantic` | `>=2.9.0` | Data modeling & runtime validation |
| `pydantic-settings` | `>=2.7.1` | Central environment configuration management |
| `google-genai` | `>=1.2.0` | Official Google Gemini SDK |
| `groq` | `>=0.11.0` | Groq AI provider SDK |
| `openai` | `>=1.50.0` | OpenRouter / OpenAI SDK client |
| `cerebras-cloud-sdk` | `>=1.0.0` | Cerebras Cloud AI provider SDK |
| `faster-whisper` | `>=1.0.0` | Localized CTranslate2 speech recognition |
| `torch` | `>=2.0.0` | Deep learning backend for VAD / Whisper |
| `numpy` | `>=1.24.0,<3.0.0` | Audio buffer and coordinate math |
| `PyAudio` | `>=0.2.14` | PortAudio low-level microphone audio streams |
| `edge-tts` | `>=7.0.0` | Microsoft Edge TTS voice synthesis |
| `pygame` | `>=2.6.0` | Audio mixer playback |
| `pyobjc` | `>=10.0` | macOS Quartz, Cocoa, CoreGraphics, Vision bindings |
| `psutil` | `>=5.9.0` | Process and memory telemetry |
| `rich` | `>=13.0.0` | Terminal Operations Dashboard & Doctor formatting |
| `pytest` | `>=8.0.0` | Automated testing suite |
| `ruff` | `>=0.9.0` | Linting and code formatting |

---

## 📦 Node.js Dependencies (`ui/desktop/package.json`)
- `electron`: `^43.4.1` — Desktop window framework
- `react` / `react-dom`: `^18.3.1` — Component rendering
- `vite`: `^5.4.2` — Build tool & dev server
- `tailwindcss`: `^4.3.3` — Utility-first styling
- `lucide-react`: `^1.16.0` — UI icons
- `typescript`: `^5.5.3` — Static type checking

---

## 🛠️ System Binaries (macOS)
- `ffmpeg`: Required for audio format decoding during ASR.
- `osascript`: Built-in AppleScript automation runner.
- `screencapture`: Built-in macOS screenshot and recording utility.
- `blueutil`: Optional Homebrew utility for toggling Bluetooth power state.
