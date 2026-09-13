# 24 — Future Autonomous Agent Reuse Guide

## Architecture Blueprint for Future Autonomous Agents

When building a future autonomous AI agent, student companion, or specialized reasoning brain on top of NOVA, the future agent should act as a high-level **Orchestration Brain (WHAT to do)** while delegating all perception and action to NOVA's existing **Capability Layer (HOW to execute safely)**.

```
                    ┌──────────────────────────────────────┐
                    │      FUTURE AUTONOMOUS AI AGENT      │
                    │  (Autonomous Reasoning / Objectives) │
                    └──────────────────┬───────────────────┘
                                       │ Decides WHAT to do
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             NOVA CAPABILITY LAYER                                │
│                                                                                  │
│  ├── Multi-Provider AI Brain    : `providers.provider_manager.ProviderManager`   │
│  ├── Memory & Facts Store       : `memory.memory_manager.MemoryManager`          │
│  ├── Visual UI & Eyes           : `core.computer_agent.ComputerAgent`            │
│  ├── Autonomous Task Execution  : `core.task_agent.TaskExecutor`                 │
│  ├── Browser Automation         : `browser.manager.BrowserManager`               │
│  ├── Desktop & App Control      : `desktop.manager.DesktopActionManager`         │
│  ├── Filesystem Operations      : `desktop.files.FileSystemManager`              │
│  ├── Native System Control      : `mac_control.manager.MacControlManager`        │
│  ├── Voice Speech Pipeline      : `voice.manager.VoiceManager`                   │
│  └── Environment Observer       : `core.environment.EnvironmentObserver`        │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │ Executes safely with verification
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         macOS SYSTEM & USER INTERACTION                          │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚫 Systems the Future Agent Must NOT Duplicate
1. **Do NOT write new LLM API clients:** Route queries through `ProviderManager` to retain multi-provider failover and rate limit handling.
2. **Do NOT write new browser drivers:** Invoke `BrowserManager` or register browser task steps.
3. **Do NOT build a separate mouse/keyboard controller:** Use `ComputerAgent` and `NovaEyesManager`.
4. **Do NOT implement a separate audio capture loop:** Use `VoiceManager` and `EventBus`.
5. **Do NOT bypass safety policies:** Always respect `DesktopSafetyPolicy` and `BrowserSafetyPolicy`.
