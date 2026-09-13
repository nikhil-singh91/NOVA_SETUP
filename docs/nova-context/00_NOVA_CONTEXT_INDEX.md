# NOVA Context Index & Navigation Guide

This directory (`docs/nova-context/`) forms the complete technical master reference for the NOVA operating system, designed to provide exhaustive, verified architectural knowledge for future autonomous AI agent integration without breaking existing working systems or duplicating capabilities.

---

## 📑 Core Documentation Index

| File | Subsystem / Topic | Description |
| :--- | :--- | :--- |
| [**`NOVA_COMPLETE_CONTEXT.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/NOVA_COMPLETE_CONTEXT.md) | **Master Reference** | Comprehensive single-source technical reference of the entire NOVA codebase. |
| [**`NOVA_REUSE_MATRIX.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/NOVA_REUSE_MATRIX.md) | **Reuse Matrix** | Exhaustive classification of what to reuse directly, wrap/adapt, extend, or avoid duplicating. |
| [**`NOVA_API_CONTRACTS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/NOVA_API_CONTRACTS.md) | **API Contracts** | Concrete method signatures, parameters, return types, exceptions, and side effects. |
| [**`NOVA_CAPABILITY_REGISTRY.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/NOVA_CAPABILITY_REGISTRY.md) | **Capability Catalog** | End-to-end trace from Intent $\to$ Router $\to$ Handler $\to$ Executor $\to$ OS API $\to$ Verification. |
| [**`NOVA_NON_BREAKING_CONTRACT.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/NOVA_NON_BREAKING_CONTRACT.md) | **Invariants & Safety** | Critical stability invariants, configuration schema, and compatibility rules. |

---

## 🏛️ Topical Deep-Dives

1. [**`01_NOVA_ARCHITECTURE.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/01_NOVA_ARCHITECTURE.md) — Macro architecture, layers, core subsystems, lifecycle management.
2. [**`02_NOVA_CAPABILITIES.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/02_NOVA_CAPABILITIES.md) — Comprehensive inventory of all 35+ system, browser, desktop, visual, and task capabilities.
3. [**`03_NOVA_API_INTEGRATIONS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/03_NOVA_API_INTEGRATIONS.md) — External cloud APIs, SDK clients, auth methods, rate limiting, and fallbacks.
4. [**`04_NOVA_ENVIRONMENT_CONFIG.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/04_NOVA_ENVIRONMENT_CONFIG.md) — Central settings schema, environment variables, validation rules, secrets safety.
5. [**`05_NOVA_AI_PROVIDERS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/05_NOVA_AI_PROVIDERS.md) — AI routing engine, Gemini/Groq/OpenRouter/Cerebras clients, failover strategy.
6. [**`06_NOVA_MEMORY.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/06_NOVA_MEMORY.md) — Atomic JSON persistence, VectorStore semantic embeddings, breadcrumbs, search.
7. [**`07_NOVA_VOICE.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/07_NOVA_VOICE.md) — Voice V2 pipeline: PyAudio $\to$ Silero VAD $\to$ Faster-Whisper $\to$ Edge-TTS/Kokoro.
8. [**`08_NOVA_BROWSER.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/08_NOVA_BROWSER.md) — Native AppleScript & URL browser automation, site-specific skills, auto-scrolling.
9. [**`09_NOVA_COMPUTER_CONTROL.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/09_NOVA_COMPUTER_CONTROL.md) — Mouse, keyboard, Retina coordinates, accessibility hierarchy, popup closing.
10. [**`10_NOVA_ENVIRONMENT_AWARENESS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/10_NOVA_ENVIRONMENT_AWARENESS.md) — EYES perception, deictic pronoun resolution ("this", "that"), real-time state.
11. [**`11_NOVA_TASK_EXECUTION.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/11_NOVA_TASK_EXECUTION.md) — Autonomous Task Agent V3: Goal planning, step execution, observation, replanning.
12. [**`12_NOVA_AUTOMATION.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/12_NOVA_AUTOMATION.md) — Proactive perception triggers, background workers, multi-step routines.
13. [**`13_NOVA_SAFETY.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/13_NOVA_SAFETY.md) — Confirmation gates, destructive action guards, safe workspace sandboxes.
14. [**`14_NOVA_PERMISSIONS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/14_NOVA_PERMISSIONS.md) — macOS Accessibility, Screen Recording, Microphone, Automation/AppleEvents.
15. [**`15_NOVA_EVENTBUS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/15_NOVA_EVENTBUS.md) — Thread-safe publish-subscribe EventBus, event catalog, payloads, lifecycles.
16. [**`16_NOVA_UI.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/16_NOVA_UI.md) — React 18, TypeScript, Tailwind, Electron desktop wrapper, WebSocket gateway.
17. [**`17_NOVA_APPLICATIONS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/17_NOVA_APPLICATIONS.md) — Finder, Terminal, VS Code, Chrome, Safari, TextEdit, Photo Booth, System Settings.
18. [**`18_NOVA_FILESYSTEM.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/18_NOVA_FILESYSTEM.md) — Multi-root search, safe trash integration, overwrite protection, AI document generation.
19. [**`19_NOVA_DEPENDENCIES.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/19_NOVA_DEPENDENCIES.md) — Python packages, Node dependencies, system binaries (FFmpeg, osascript).
20. [**`20_NOVA_TESTING.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/20_NOVA_TESTING.md) — 881-test test suite catalog, test categories, mocks, running instructions.
21. [**`21_NOVA_STARTUP.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/21_NOVA_STARTUP.md) — Multithreaded bootstrap flow, signal handling, graceful shutdown, state serialization.
22. [**`22_NOVA_SECURITY.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/22_NOVA_SECURITY.md) — Secret masking, `.gitignore` defense, path containment, IPC authorization.
23. [**`23_NOVA_DATA_FLOW.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/23_NOVA_DATA_FLOW.md) — End-to-end data flow diagrams (Voice, Text, Vision, Browser, Computer, Tasks).
24. [**`24_NOVA_REUSE_GUIDE.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/24_NOVA_REUSE_GUIDE.md) — How the future autonomous agent must interface with NOVA's capability layer.
25. [**`25_NOVA_LIMITATIONS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/25_NOVA_LIMITATIONS.md) — Known hardware limitations, OS restrictions, external CLI dependencies.
26. [**`26_NOVA_EXTENSION_POINTS.md`**](file:///Users/nikhilsingh/Desktop/NOVA_SETUP/docs/nova-context/26_NOVA_EXTENSION_POINTS.md) — Preferred architecture-approved extension points for adding future features.
