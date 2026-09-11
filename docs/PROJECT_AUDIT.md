# NOVA System Architecture & Codebase Audit Report

## 1. System Overview & Core Identity
NOVA is designed as a modular, privacy-conscious, voice-first personal AI operating system on macOS. Its primary objectives include natural continuous voice and text interaction, multi-provider AI routing, persistent memory with semantic indexing, macOS local system automation, and companion lifecycle flows.

---

## 2. Complete Execution & Control Flow
1. **Bootstrap & Service Registry Wiring:** `main.py` initializes lifecycle tracking, constructs the central `EventBus`, and parallelly initializes `MemoryManager`, `VectorStore`, `ProviderManager`, `SystemPromptManager`, `EmotionEngine`, and `MacControlManager`.
2. **Voice V2 Subsystem Initialization:** Constructs and initializes `VoiceManager`, which orchestrates `MicrophoneManager`, `VoiceActivityDetector`, `TranscriptionManager`, `SpeakerManager`, and `VoiceListener`.
3. **Companion Startup Flow:** Synthesizes a greeting by querying memory for the previous session breadcrumb and active project, formatting a greeting prompt via `SystemPromptManager`, querying `ProviderManager`, and delivering the response via console and speech.
4. **Operations Dashboard & Event Loop:** Enters the main event loop reading `TurnRequest` objects from `_turn_queue`, populated by console inputs and Voice V2 callbacks.
5. **Turn Processing Pipeline:**
   - Evaluates input for local commands and macOS automation triggers.
   - Computes emotion, intent, and conversational mode.
   - Retrieves relevant memory and vector embeddings.
   - Builds structured prompt and routes to the best AI provider.
   - Generates response, decides whether to write durable memory, and delivers speech.
6. **Graceful Companion Shutdown:** Upon receiving shutdown commands or OS signals, summarizes the session, writes a breadcrumb to durable memory, says farewell, and tears down all subsystems.

---

## 3. Subsystem Architecture Map

| Subsystem | Core Modules | Responsibilities | Key Dependencies |
| :--- | :--- | :--- | :--- |
| **Orchestration & Core** | `main.py`, `core.lifecycle`, `core.registry`, `core.event_bus` | Application lifecycle, service registry, pub/sub event bus, turn processing queue. | Standard library |
| **Voice V2** | `voice.manager`, `voice.microphone`, `voice.vad`, `voice.transcriber`, `voice.speaker` | Low-latency audio streaming, adaptive VAD, Faster-Whisper transcription, Edge-TTS. | `pyaudio`, `faster-whisper`, `torch`, `edge-tts`, `pygame` |
| **AI Providers** | `providers.provider_manager`, `providers.gemini_provider`, `providers.groq_provider`, etc. | Provider routing, fallback hierarchies, rate limit management, LLM streaming. | `google-genai`, `groq`, `openai`, `cerebras-cloud-sdk` |
| **Memory** | `memory.memory_manager`, `memory.vector_store` | Key-value structured memory, persistence, TF-IDF / vector semantic indexing. | `scikit-learn` / `numpy` |
| **Personality** | `personality.system_prompt`, `personality.emotion_engine` | Dynamic system prompts, emotion classification, conversation mode detection. | `pydantic` |
| **Browser Actions V1** | `browser.manager`, `browser.parser`, `browser.router`, `browser.engine`, `browser.sites.*` | Natural language browser automation, YouTube playback, Google search, Shorts auto-scroll. | `osascript` / AppleScript |
| **macOS Control** | `mac_control.manager`, `mac_control.parser`, `mac_control.router`, `mac_control.actions.*` | Natural language macOS system automation (volume, apps, wifi, bluetooth, brightness). | `pyobjc`, `osascript` |
| **UI & Health** | `ui.terminal_dashboard`, `ui.health_checker`, `ui.doctor` | Terminal dashboard, health checks, environment & hardware self-diagnostics. | `rich`, `psutil` |

---

## 4. Virtual Environment & Environment Health
- **Active Interpreter:** Python 3.12 (`/Users/nikhilsingh/Desktop/NOVA_SETUP/.venv/bin/python`).
- **Dependencies:** Fully aligned between `requirements.txt` and `pyproject.toml`.
- **Test Suite:** 100% pass rate across unit and pipeline tests.
