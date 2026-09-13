# NOVA Non-Breaking Architectural Contract

This document outlines the strict compatibility and safety invariants that all future autonomous agent development must preserve.

---

## 🔒 1. Secrets & Environment Configuration Invariants
- **Never Hardcode Secrets:** All external API keys (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `CEREBRAS_API_KEY`, `TAVILY_API_KEY`, `ELEVENLABS_API_KEY`, etc.) must be accessed exclusively through `config.settings.settings`.
- **Git Protection:** `.env` and `credentials.json` must remain ignored by `.gitignore`.
- **Masking:** Logs and UI telemetry must always mask sensitive credentials (`SecretStr.get_secret_value()` should never appear in plain log sinks).

---

## 🛡️ 2. Safety & Sandboxing Invariants
- **Destructive Operation Gates:**
  - File/folder deletion (`fs.safe_move_to_trash` / `DELETE_ITEM`) must always require explicit confirmation unless running in pre-authorized headless sandbox mode.
  - System shutdown (`system.shutdown`) must always require confirmation.
- **Filesystem Confinement:** File writing, project scaffolding, and folder creation must remain within approved user directories (`Desktop`, `Documents`, `Downloads`, `Projects`, `DESKTOP_WORKSPACE_DIR`). Never write arbitrary files outside these paths.
- **URL Filtering:** Malicious schemas (`javascript:`, `data:`, `file:`) must remain blocked by `BrowserSafetyPolicy`.

---

## ⚡ 3. Concurrency & EventBus Invariants
- **Thread Safety:** `EventBus`, `MemoryManager`, `RecentInteractionContext`, and `NovaEyesManager` must remain protected by thread-safe locks (`threading.RLock` / `threading.Lock`).
- **Non-Blocking Main Loop:** Turn processing in `NovaApplication` and UI server WebSocket broadcasting must never block the main event loop or audio ingestion thread.
- **Cancellation Propagation:** Calling `cancel_task()` or `stop_active_task()` must cleanly propagate cancellation flags to active `TaskExecutor`, `ComputerAgent`, `BrowserManager`, and `DesktopActionManager` instances.

---

## 🧩 4. IPC & Port Invariants
- **UI Gateway Port:** Local WebSocket and REST server must default to `127.0.0.1:8765`.
- **Payload Schema:** WebSocket event payloads must conform to `ui.backend.models.UIEvent` with `event_type`, `avatar_state`, and `data` fields to avoid breaking the React desktop interface.

---

## 🧪 5. Testing & Verification Invariants
- **Test Integrity:** Existing pytest test suite (881 passing tests) must remain 100% green.
- **No Direct Mock Pollution:** Tests must not modify global singletons (`registry`, `capability_registry`) permanently without restoring them in teardown fixtures.
