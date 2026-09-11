# NOVA UI V1 Architecture Audit

---

## 1. Current NOVA Backend Flow

```text
User Speech / Text Input
        │
        ▼
[TurnRequest] -> Enqueued in NovaApplication._turn_queue
        │
        ▼
NovaApplication._process_turn()
        ├── 0. Real-time Environment Observation (EnvironmentObserver.refresh())
        ├── 1. Pending Confirmation Handling (ContextResolver / Safe Trash / Reminders)
        ├── 2. Local Voice Command Router (VoiceCommandRouter -> "shutdown" / "cancel")
        ├── 3. Natural Language Intent Engine (TextNormalizer -> LinguisticMatcher -> Fallback)
        ├── 4. Routing Domain Dispatcher:
        │       ├── TASK_AGENT -> TaskPlanner -> TaskExecutor -> Replanner -> Verification
        │       ├── VISUAL -> ComputerAgent (ScreenObserver, OCR, UIResolver, Verifier)
        │       ├── BROWSER -> BrowserManager (Chrome/Safari sessions, platform skills)
        │       ├── DESKTOP_APP / FILESYSTEM / DOCUMENT -> DesktopActionManager
        │       └── SYSTEM -> MacControlManager / Hardware & Clipboard actions
        ├── 5. Response Delivery (_deliver_response -> VoiceManager.speak() + Console)
        └── 6. Event Notification (EventBus.publish(NovaEvent.*))
```

---

## 2. Voice Input Flow

- **Audio Capture**: `voice/listener.py` (`AudioListener`) reads raw PCM audio streams from PyAudio/sounddevice.
- **Voice Activity Detection**: `voice/vad.py` (`SileroVAD`) detects speech start/end boundaries and filters background noise.
- **Transcription**: `voice/transcriber.py` (`FasterWhisperTranscriber`) converts audio frames into transcription text and emits `TranscriptionResult`.
- **Turn Hook**: `VoiceManager` passes transcribed text to `NovaApplication._on_voice_turn()`, which enqueues a `TurnRequest(source="voice", text=...)`.

---

## 3. Speech Output Flow

- **Response Formulation**: Subsystems generate a structured `spoken_response` string.
- **Delivery Hook**: `NovaApplication._deliver_response(text, turn_id)` is invoked.
- **TTS Synthesis**: `voice/speaker.py` (`KokoroSpeaker` / `PiperSpeaker` / `EdgeTTSSpeaker` / `Pyttsx3Speaker`) synthesizes and plays audio through `pygame.mixer` or native audio output.
- **Event Bus Notification**: `NovaEvent.SPEAKING_STARTED` is emitted before playback, and `NovaEvent.SPEAKING_FINISHED` is emitted upon completion.

---

## 4. Command Execution Flow

- **Single Entry Point**: `NovaApplication._process_turn(request)` coordinates all intent matching, execution, and response synthesis.
- **Subsystem Isolation**: Subsystems (`TaskExecutor`, `ComputerAgent`, `BrowserManager`, `DesktopActionManager`, `MacControlManager`) do not directly depend on each other; they are coordinated via `EnvironmentContext`, `TaskContext`, and `NovaApplication`.

---

## 5. Autonomous Task Agent Flow

- **Planning**: `TaskPlanner.plan_goal(goal_prompt)` decomposes compound requests into a directed graph of `TaskStep` objects with registered capability names (`fs.create_folder`, `code.create_project`, `browser.search_web`, `visual.click_element`, `camera.take_photo`, etc.).
- **Execution**: `TaskExecutor.execute_plan(plan, context)` executes steps sequentially or in dependency order, validating outputs via step verifiers.
- **Replanning**: If a step fails, `DynamicReplanner` generates localized recovery steps without restarting the entire task.
- **Goal Verification**: Post-task holistic checks confirm that target directories, files, or documents exist on disk.

---

## 6. Safe UI Integration Points

1. **Input Gateway**: Instead of modifying `main.py`, the UI will submit commands through a dedicated `CommandGateway` (`backend_ui/command_gateway.py`), which pushes a `TurnRequest(source="ui", text=...)` into `NovaApplication._turn_queue`.
2. **Event Bridge**: An `EventBridge` (`backend_ui/event_bridge.py`) subscribes to NOVA's `EventBus` (`core/event_bus.py`) and broadcasts structured, sanitized JSON event streams over a local WebSocket (`ws://127.0.0.1:8765/events`).
3. **State Observability**:
   - `LISTENING_STARTED` / `LISTENING_FINISHED` $\rightarrow$ Avatar state: `LISTENING`
   - `THINKING_STARTED` $\rightarrow$ Avatar state: `THINKING`
   - `TASK_STARTED` $\rightarrow$ Avatar state: `PLANNING` / `EXECUTING`
   - `VERIFICATION_STARTED` $\rightarrow$ Avatar state: `VERIFYING`
   - `SPEAKING_STARTED` / `SPEAKING_FINISHED` $\rightarrow$ Avatar state: `SPEAKING` $\rightarrow$ `IDLE`
   - `CANCEL_ACTION` $\rightarrow$ Avatar state: `IDLE` / `CONFUSED`
   - Errors $\rightarrow$ Avatar state: `ERROR`

---

## 7. Files That Must NOT Be Modified

- `voice/` (Whisper transcriber, Silero VAD, Kokoro/Piper TTS)
- `browser/` (Browser sessions, engine, site skills)
- `desktop/` (Filesystem, safety policy, apps, camera, editor)
- `core/computer_agent.py` & `core/visual/` (Visual UI automation)
- `core/task_agent/` (Autonomous Task Agent planning & execution)
- `mac_control/` (macOS hardware actions)
- `intent/` (Natural language intent engine & models)

---

## 8. Files Requiring Small Adapters or New Creation

- **`backend_ui/` (NEW)**:
  - `backend_ui/models.py`: UI event models and avatar states.
  - `backend_ui/event_bridge.py`: Event bus bridge to WebSocket subscribers.
  - `backend_ui/command_gateway.py`: Safe command submission and task cancellation endpoint.
  - `backend_ui/server.py`: Local WebSocket & HTTP server.
  - `backend_ui/launcher.py`: Desktop application startup orchestrator.
- **`ui/` (NEW)**:
  - Complete modern React + TypeScript + Vite + Electron desktop application.
