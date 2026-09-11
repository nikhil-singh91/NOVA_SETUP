# NOVA UI V1 Real-Time Event System

---

## 1. Event Model & Payload Structure

Every event streamed over `ws://127.0.0.1:8765/events` follows a standardized schema:

```json
{
  "event_id": "a8f3b20c91",
  "event_type": "task_step_started",
  "timestamp": 1724520120.45,
  "avatar_state": "executing",
  "message": "Creating directory ~/Desktop/DSA",
  "task_id": "task_9281a",
  "data": {
    "step_index": 1,
    "capability_name": "fs.create_folder",
    "target_path": "~/Desktop/DSA"
  },
  "privacy": {
    "microphone_active": false,
    "screen_observation_active": false,
    "screen_recording_active": false,
    "camera_active": false,
    "task_executing": true
  }
}
```

---

## 2. Event Types & Mappings

| Backend `NovaEvent` | UI Event Type | Default Avatar State | UI Action / Display |
| :--- | :--- | :--- | :--- |
| `APPLICATION_STARTED` | `nova_started` | `idle` | Shows online connection status |
| `LISTENING_STARTED` | `voice_listening_started` | `listening` | Pulses waveform & turns on MIC privacy badge |
| `LISTENING_FINISHED` | `voice_listening_stopped` | `thinking` | Freezes waveform, turns off MIC privacy badge |
| `THINKING_STARTED` | `command_understood` | `thinking` | Shows intent understanding pill in Chat/Voice |
| `SPEAKING_STARTED` | `speaking_started` | `speaking` | Triggers animated lip-sync and audio visualizer |
| `SPEAKING_FINISHED` | `speaking_finished` | `idle` | Stops lip-sync, returns avatar to idle breathing |
| `COMMAND_EXECUTED` | `command_completed` | `success` | Displays completed turn card in Chat |
| `TASK_STARTED` | `task_started` | `planning` | Initializes Task Agent progress card |
| `TASK_STEP_STARTED` | `task_step_started` | `executing` | Marks active step as `running` with spinner |
| `TASK_STEP_COMPLETED` | `task_step_completed` | `success` | Advances progress bar, marks step green |
| `TASK_CANCELLED` | `task_cancelled` | `idle` | Displays cancellation banner |
| `NOVA_ERROR` | `nova_error` | `error` | Shows amber/crimson alert toast |

---

## 3. Privacy & Sanitization Pipeline

Before any event is serialized:
1. `EventBridge._sanitize_dict()` intercepts all fields containing `api_key`, `secret`, `token`, `password`, `auth`, or `credential` and replaces values with `******`.
2. String payloads longer than 2000 characters (e.g. raw HTML or memory dumps) are truncated.
3. Binary data (e.g. raw screen buffers) are filtered; only structured coordinate/metadata representations are sent.
