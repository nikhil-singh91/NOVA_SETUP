# 20 — NOVA Automated Testing Suite & Test Verification

## Overview
NOVA contains an automated test suite of **881 tests** covering intent classification, provider routing, memory persistence, voice quality gating, browser automation, desktop execution, computer interaction, and task replanning.

---

## 🧪 Test Suite Execution
```bash
# Run full automated test suite with PYTHONPATH set to project root
PYTHONPATH=. .venv/bin/pytest --strict-markers -ra
```

**Result:** `881 passed, 3 warnings in 77s` (100% Pass Rate).

---

## 📂 Test Categories & Modules (`tests/`)

| Test Module | Coverage Domain | Primary Verification |
| :--- | :--- | :--- |
| `test_natural_intent_architecture.py` | Intent parsing & matching | Tests Regex + semantic parsing for 35+ intents |
| `test_task_agent_matrix.py` | Multi-step task planning | Tests step generation, dependencies, execution |
| `test_task_replanning.py` | Dynamic error recovery | Tests failure interception and alternative plan injection |
| `test_v3_5_capabilities.py` | Capability registry | Tests all 21 default capability handlers and verifiers |
| `test_browser_actions_v2.py` | Browser skills & auto-scroll | Tests YouTube, Google, Amazon, and Shorts scroller |
| `test_computer_agent_matrix.py` | Visual UI interaction | Tests `click_element`, `type_text`, `close_popup` |
| `test_environment_context.py` | Environment observer | Tests front app detection and deictic pronoun resolution |
| `test_voice_quality_gate.py` | Voice V2 quality & ASR | Tests hallucination rejection and confidence gates |
| `test_audio_events_and_multilingual_asr.py` | Acoustic non-speech detection| Tests cough, sneeze, laugh, sigh detection |
| `test_backend_ui_integration.py` | UI server & gateway | Tests WebSocket handshake and REST endpoints |
| `test_smart_files_step4.py` | Filesystem safety | Tests multi-root search, folder creation, trash |
