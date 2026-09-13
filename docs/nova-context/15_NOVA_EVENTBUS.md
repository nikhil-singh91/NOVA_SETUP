# 15 — NOVA EventBus & Internal Event Stream

## Overview
NOVA uses a thread-safe publish/subscribe event bus (`core.event_bus.EventBus`) as its core internal messaging backbone.

---

## 📡 Event Catalog (`NovaEvent`)

```python
class NovaEvent(str, Enum):
    APPLICATION_STARTED = "application_started"
    APPLICATION_SHUTDOWN = "application_shutdown"
    WAKE_WORD_DETECTED = "wake_word_detected"
    LISTENING_STARTED = "listening_started"
    LISTENING_PARTIAL = "listening_partial"
    LISTENING_FINISHED = "listening_finished"
    THINKING_STARTED = "thinking_started"
    RESPONSE_GENERATED = "response_generated"
    SPEAKING_STARTED = "speaking_started"
    SPEAKING_FINISHED = "speaking_finished"
    SPEECH_INTERRUPTED = "speech_interrupted"
    STATE_CHANGED = "state_changed"
    HEALTH_UPDATE = "health_update"
    COMMAND_EXECUTED = "command_executed"
    BROWSER_ACTION_STARTED = "browser_action_started"
    BROWSER_ACTION_COMPLETED = "browser_action_completed"
    BROWSER_ACTION_FAILED = "browser_action_failed"
    BROWSER_ACTION_CANCELLED = "browser_action_cancelled"
    BROWSER_TASK_STARTED = "browser_task_started"
    BROWSER_TASK_STEP_COMPLETED = "browser_task_step_completed"
    BROWSER_TASK_COMPLETED = "browser_task_completed"
    BROWSER_TASK_CANCELLED = "browser_task_cancelled"
    BROWSER_PAGE_EXTRACTED = "browser_page_extracted"
    DESKTOP_ACTION_STARTED = "desktop_action_started"
    DESKTOP_ACTION_COMPLETED = "desktop_action_completed"
    DESKTOP_ACTION_FAILED = "desktop_action_failed"
    DESKTOP_ACTION_CANCELLED = "desktop_action_cancelled"
    CAMERA_CAPTURE_STARTED = "camera_capture_started"
    CAMERA_CAPTURE_COMPLETED = "camera_capture_completed"
    CAMERA_CAPTURE_FAILED = "camera_capture_failed"
```

---

## 🌉 EventBridge & UI Synchronization
- **Publishing:** Any subsystem publishes events via `event_bus.publish(NovaEvent.SOME_EVENT, key=val)`.
- **UI Forwarding:** `ui.backend.event_bridge.EventBridge` subscribes to these events and translates them into typed `UIEvent` objects broadcast over WebSockets to the React frontend.
