# NOVA 4.0 — Phase 1: Unified Autonomous Agent Runtime Architecture

> **Document Version:** 4.0.0-phase1-draft  
> **Target System:** NOVA (NOVA_SETUP)  
> **Status:** Architectural Design & Contract Specification (Phase 1 — No Code Implementation)  
> **Source of Truth:** Current NOVA Codebase (`core/`, `desktop/`, `browser/`, `intent/`, `providers/`, `memory/`, `ui/`, `main.py`)  
> **Author:** Antigravity / NOVA Core Architecture  

---

## 1. Executive Summary

NOVA currently operates primarily as an advanced, reactive assistant: it listens for user commands (voice or text), resolves intent through regex and neural semantic extractors, executes bounded commands across macOS desktop, browser, and hardware surfaces, and reports outcomes. With **Autonomous Task Agent V3** (`core.task_agent`), NOVA introduced structured multi-step task decomposition, sequential capability execution, and localized recovery.

**NOVA 4.0** establishes a **Unified Autonomous Agent Runtime**. Rather than operating merely as a command-response pipeline, NOVA evolves toward a **general-purpose autonomous computer agent** capable of pursuing complex, multi-modal, durable goals across the operating system and the web.

### Core Architectural Invariants Preserved
1. **Source of Truth Rule:** The actual existing codebase is the definitive implementation truth. Existing working subsystems (`NovaApplication`, `CapabilityRegistry`, `TaskPlanner`, `TaskExecutor`, `DynamicReplanner`, `ProviderManager`, `NovaEyesManager`, `BrowserManager`, `ComputerAgent`, `MemoryManager`, `EventBus`, `EventBridge`) are preserved.
2. **Zero Parallel Duplication:** NOVA 4.0 will **not** introduce a parallel agent framework, duplicate AI provider clients, second event buses, or competing browser/computer controllers.
3. **Continuous Perception Without Cloud Leakage:** NOVA's local-first Quartz and Apple Vision perception architecture is preserved. There is zero cloud video streaming and zero disk persistence of user screens.
4. **Safety and Verification First:** The runtime will never convert an unverified action into a false success response. Every autonomous step passes through explicit policy checks, post-action observation, and deterministic verification.
5. **Architectural Transition:**
   $$\text{CURRENT IMPLEMENTATION} \longrightarrow \text{CURRENT CONTRACT} \longrightarrow \text{SAFE EXTENSION POINT} \longrightarrow \text{NOVA 4.0 DESIGN}$$

---

## 2. Current NOVA Architecture Baseline

### 2.1 Macro Architecture Layers
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE & GATEWAYS                              │
│       Electron Desktop App / React 18 / WebSocket / Terminal Dashboard          │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ JSON IPC / WebSocket (127.0.0.1:8765)
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       NOVA APPLICATION ORCHESTRATOR                             │
│  • Turn Queue Loop (`main.py:NovaApplication`)                                  │
│  • Service Lifecycle (`core.lifecycle:ServiceLifecycle`)                        │
│  • Thread-Safe EventBus (`core.event_bus:EventBus`)                             │
│  • Recent Interaction Context (`core.context:RecentInteractionContext`)          │
└──────────────────┬───────────────────────────────┬──────────────────────────────┘
                   │                               │
                   ▼                               ▼
┌────────────────────────────────────┐ ┌──────────────────────────────────────────┐
│    EYES & PERCEPTION ENGINE        │ │        INTENT & ROUTING ENGINE           │
│ • `EnvironmentObserver` (macOS OS) │ │ • `NaturalLanguageIntentEngine`          │
│ • `NovaEyesManager` (Retina SCK)   │ │ • `CanonicalIntent` & `StructuredAction` │
│ • `ContextResolver` (Pronouns)     │ │ • `RoutingDomain` Dispatcher             │
│ • `VisionOCR` & `ScreenState`      │ │ • Regex + Fast AI Fallback Routing       │
└──────────────────┬─────────────────┘ └───────────────────┬──────────────────────┘
                   │                                       │
                   └───────────────────┬───────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CAPABILITY & EXECUTION LAYER (HANDS)                         │
│  ┌───────────────────────────┐ ┌───────────────────────────┐                    │
│  │ CapabilityRegistry (26+)  │ │ Autonomous Task Agent V3  │                    │
│  │ Handler + Verifier Tuple  │ │ (Planner, Replanner, Ex)  │                    │
│  └─────────────┬─────────────┘ └─────────────┬─────────────┘                    │
│                │                             │                                  │
│  ┌─────────────▼─────────────┐ ┌─────────────▼─────────────┐                    │
│  │ BrowserManager            │ │ ComputerAgent             │                    │
│  │ (Chrome/Safari via AS/URL)│ │ (Retina Quartz Pointer/AX)│                    │
│  └───────────────────────────┘ └───────────────────────────┘                    │
│  ┌───────────────────────────┐ ┌───────────────────────────┐                    │
│  │ DesktopActionManager      │ │ MacControlManager         │                    │
│  │ (Files, Code, Docs, Apps) │ │ (Audio, Bright, WiFi, BT) │                    │
│  └───────────────────────────┘ └───────────────────────────┘                    │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-PROVIDER REASONING ENGINE                            │
│  • `ProviderManager`: Gemini, Groq, OpenRouter, Cerebras                        │
│  • TaskType Routing: CODING, REASONING, FAST, CHEAP, GENERAL                    │
│  • Automatic Health Tracking, Rate-Limit Isolation & Instant Failover           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Deep Audit of 17 Core Execution Paths

| # | Workflow / Code Path | Primary File | Class | Function | Input | Output | Events Emitted | Key Dependencies | Current Limitations |
|---|---|---|---|---|---|---|---|---|---|
| **1** | User Voice/Text Input | `main.py`, `voice/manager.py` | `NovaApplication`, `VoiceManager` | `_start_background_services`, `_run_event_loop` | Mic audio buffer or Terminal stdin | `TurnRequest` | `LISTENING_STARTED`, `LISTENING_FINISHED` | PyAudio, Silero VAD, Faster-Whisper | Queue is FIFO; only processes one turn synchronously per turn cycle. |
| **2** | Turn Creation | `main.py` | `NovaApplication` | `_process_turn` | `TurnRequest` (source, text) | None (drives turn pipeline) | `COMMAND_UNDERSTOOD` | `uuid`, `queue.Queue` | Turns are ephemeral; turn ID not propagated to all subsystem loggers. |
| **3** | Intent Classification | `intent/engine.py` | `NaturalLanguageIntentEngine` | `parse` | `text: str`, `allow_ai_fallback: bool` | `StructuredAction` | None directly | Regex rules, `ProviderManager` | Fallback AI call adds 300-800ms latency if regex fails. |
| **4** | Context Resolution | `core/environment.py`, `core/context.py` | `ContextResolver`, `RecentInteractionContext` | `resolve_target`, `resolve_reference` | `reference: str`, `EnvironmentContext` | `ResolvedEntity` | None | macOS `osascript`, Finder AppleScript | Cannot resolve ambiguous visual objects without running full OCR pass. |
| **5** | Capability Selection | `core/task_agent/registry.py` | `CapabilityRegistry` | `get`, `has`, `list_capabilities` | `capability_name: str` | `CapabilityDefinition` | None | In-memory registry dict | Static registration; dynamic plugin capability injection not fully formalized. |
| **6** | Task Planning | `core/task_agent/planner.py` | `TaskPlanner` | `plan_goal` | `user_request: str` | `TaskPlan` | None directly | `ProviderManager`, Regex pattern table | Deterministic regex only matches 4 specific templates; fallback AI schema strict. |
| **7** | Task Execution | `core/task_agent/executor.py` | `TaskExecutor` | `execute_plan` | `plan: TaskPlan`, `context: TaskContext` | `TaskResult` | Emits telemetry via logger, no EventBus publish | `threading.Event`, `CapabilityRegistry` | Synchronous execution block; cannot pause mid-step; lacks granular EventBus emission. |
| **8** | Browser Execution | `browser/manager.py`, `browser/engine.py` | `BrowserManager`, `MacOSNativeBrowserEngine` | `execute_plan`, `execute_command` | `BrowserActionPlan` | `BrowserResult` | `BROWSER_ACTION_STARTED`, `_COMPLETED`, `_FAILED` | AppleScript, Google Chrome / Safari | Heavy reliance on AppleScript dictionary; DOM interaction via URL JavaScript injection. |
| **9** | Computer Execution | `core/computer_agent.py` | `ComputerAgent` | `execute_visual_goal` | `goal_text: str`, `action_hint: str` | `VisualResult` | None directly | Quartz, ScreenCaptureKit, Accessibility | Single-action visual loop; does not chain multiple coordinate-free visual actions natively. |
| **10** | Eyes Observation | `core/eyes/manager.py`, `core/eyes/state.py` | `NovaEyesManager` | `observe_now`, `_perception_loop` | `force_ocr: bool` | `ScreenState` | None | Apple Vision, Quartz, Accessibility API | In-memory latest snapshot only; no temporal window delta diffing across steps. |
| **11** | Verification | `core/eyes/verifier.py`, `core/task_agent/executor.py` | `EyesStateVerifier`, `TaskExecutor` | `verify`, `_verify_final_goal` | `ActionType`, `before: ScreenState`, `after: ScreenState` | `VerificationOutcome`, `bool` | None | Visual hash, OS State, Path check | UI verifiers check visual hash/window title; semantic confirmation is binary. |
| **12** | Dynamic Replanning | `core/task_agent/replanner.py` | `DynamicReplanner` | `replan_failed_step` | `plan: TaskPlan`, `failed_step: TaskStep`, `ctx: TaskContext` | `list[TaskStep] \| None` | None | `FailureType` classification | Replanner rules currently hardcoded for visual click fallback and folder creation. |
| **13** | Response Generation | `main.py`, `personality/system_prompt.py` | `NovaApplication`, `SystemPromptManager` | `_generate_response` | `user_text: str`, `PromptBuildContext` | `str \| None` | `THINKING_STARTED`, `RESPONSE_GENERATED` | `ProviderManager`, System prompts | Blocks turn thread while awaiting LLM completion. |
| **14** | TTS Delivery | `voice/manager.py` | `VoiceManager` | `speak` | `text: str`, `turn_id: str` | `bool` | `SPEAKING_STARTED`, `SPEAKING_FINISHED` | Edge-TTS, Kokoro, PyAudio | Speaking blocks voice listener unless speech interruption triggers. |
| **15** | UI Events | `ui/backend/event_bridge.py` | `EventBridge` | `emit_event`, `_wire_event_bus` | `NovaEvent`, payload | Broadcasts WebSocket JSON | Bridges internal `NovaEvent` to `UIEvent` | `asyncio.Queue`, WebSocket | Task agent steps currently logged to console, not bridged to UI event stream. |
| **16** | Cancellation | `main.py`, `core/task_agent/executor.py` | `NovaApplication`, `TaskExecutor`, `ComputerAgent` | `_execute_local_cancel`, `cancel_task` | "Stop" command / SIGINT | Sets `threading.Event` | Emits response via voice/text | `threading.Event` across subsystems | Must wait for current blocking synchronous I/O or sleep to yield. |
| **17** | Shutdown | `main.py`, `core/lifecycle.py` | `NovaApplication`, `ServiceLifecycle` | `_shutdown`, `shutdown` | SIGINT / `exit` command | Process termination code (0/1) | `APPLICATION_SHUTDOWN` | Registered services | Threads are daemonized; uncommitted state in memory manager saved synchronously. |

---

## 3. Current Task Agent Analysis

A rigorous inspection of `core/task_agent/` reveals the exact operational mechanics of the current Autonomous Task Agent V3:

### 3.1 TaskPlanner
* **Receives:** `user_request: str`.
* **Returns:** `TaskPlan` (containing `plan_id`, `task_id`, `goal: TaskGoal`, and `steps: list[TaskStep]`).
* **Mechanism:**
  1. Checks 4 deterministic regex patterns:
     - Root project folder with subfolders on Desktop.
     - C++/Python project with boilerplate files.
     - Find tutorial on Google and save link in text file.
     - Cross-turn context-bound file creation (`"create main.cpp inside it"`).
  2. If deterministic patterns miss and `ProviderManager` is present, it constructs a prompt with all capabilities listed from `CapabilityRegistry` and requests a structured JSON plan via `TaskType.REASONING`.
  3. Fallback: If AI synthesis fails, creates a single empty plan.

### 3.2 TaskExecutor
* **Receives:** `plan: TaskPlan`, optional `context: TaskContext`, optional `progress_callback: Callable[[str], None]`.
* **Executes:** Iterates through `step_queue = list(plan.steps)`.
* **Step Representation:** `TaskStep` dataclass containing `step_id`, `description`, `capability_name`, `parameters: dict[str, Any]`, `depends_on: list[str]`, `verification_type: str`, `verification_params: dict`, `status: StepStatus`, `retry_count: int`, `max_retries: int`, `result_data: dict`.
* **Dependencies:** Step dependency check via `plan.are_dependencies_met(current_step)` which verifies every prerequisite step ID has `status == StepStatus.COMPLETED`.
* **Failures:** Captured via `try...except` and `result.get("success", False)`. Classified via `DynamicReplanner.classify_failure(err_msg)`.

### 3.3 DynamicReplanner
* **Mechanism:** Categorizes errors into `FailureType` (`TRANSIENT`, `NOT_FOUND`, `PERMISSION`, `AMBIGUOUS`, `UNSUPPORTED`, `CANCELLED`).
* **Recovery:** If `can_retry_step` returns true, re-enqueues step with backoff. If max step retries exhausted, calls `replan_failed_step`.
* **Replanning Budget:** Max 3 replan cycles per task (`max_replan_cycles = 3`).
* **Current Replanning Logic:** Provides 2 deterministic substitutions:
  - If `visual.click_element` fails on a search input, substitutes `browser.search_web`.
  - If `fs.create_folder` fails on a non-existent path, substitutes creation on Desktop.

### 3.4 Verification System
* **Step Verification:** Handled via `CapabilityDefinition.verifier(bound_params, exec_result, ctx)`. For filesystem, checks `Path.is_file()` or `Path.is_dir()`. For browser, checks URL matches.
* **Goal Verification:** `_verify_final_goal(plan, ctx)` checks that every file or folder created across all completed steps physically exists on disk.

### 3.5 Answers to Key Analysis Questions
1. **Environment State Passing:** Currently passed via parameter binding (`_bind_parameters`) using `TaskContext` (resolves `"it"` to `last_created_folder` or `last_created_file`). Real-time `ScreenState` is **not** continuously fed into the executor loop.
2. **Cancellation Handling:** Checked at the beginning of each step via `self._stop_event.is_set()`. Sets `plan.status = TaskStatus.CANCELLED` and returns immediately.
3. **Provider Outage Behavior:** If `ProviderManager` fails during AI plan synthesis, planner falls back to an empty plan; it does not crash, but cannot synthesize dynamic steps.
4. **Capability Unavailable:** If `capability_name` is missing from `CapabilityRegistry`, executor marks step as `FAILED` with `"Capability not registered"` and halts.
5. **Action Succeeds but Verification Fails:** If the capability handler returns `success=True` but the verifier returns `False`, executor treats the step as `FAILED`, increments `retry_count`, and triggers dynamic recovery. Success is never faked.
6. **Current Limitations for General Agent Runtime:**
   - Synchronous, blocking execution on the main/turn thread.
   - Fixed step list; lacks dynamic loop where observation creates actions on the fly.
   - Step verifiers are capability-specific heuristics rather than unified before/after world state diffs.
   - No task budget for wall-clock execution or multi-turn persistent tracking.
   - Task execution events are logged to console but not streamed through `EventBus` to UI.

---

## 4. NOVA 4.0 Agent Runtime Goals

The unified runtime upgrades the system from executing pre-compiled batch plans to a continuous, closed-loop **autonomous computer agent loop**:

```
                              ┌────────────────────────┐
                              │       USER GOAL        │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │       UNDERSTAND       │
                              │ (Decompose & Criteria) │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │    RESOLVE CONTEXT     │
                              │ (OS, Eyes, Memory)     │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │   CHECK CAPABILITIES   │
                              │ (Registry & Perms)     │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │  OBSERVE CURRENT STATE │
                              │ (Selective Observation)│
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │          PLAN          │
                              │ (Synthesize Next Steps)│
                              └───────────┬────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │                                             │
                   ▼                                             ▼
       ┌────────────────────────┐                   ┌────────────────────────┐
       │     POLICY CHECK       │                   │    BUDGET CHECK        │
       │ (Sandboxes & Gates)    │                   │ (Time, Steps, Retries) │
       └───────────┬────────────┘                   └────────────┬───────────┘
                   │                                             │
                   └──────────────────────┬──────────────────────┘
                                          │ Approved
                                          ▼
                              ┌────────────────────────┐
                              │          ACT           │
                              │ (Dispatch Capability)  │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │     OBSERVE AGAIN      │
                              │ (Capture Delta State)  │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │         VERIFY         │
                              │ (Evidence vs Expected) │
                              └───────────┬────────────┘
                                          │
                                          ▼
                                     SUCCESS?
                                    /        \
                                  YES         NO
                                  /            \
                                 ▼              ▼
                     [More Steps Needed?]   [RECOVER]
                         /          \           │
                       YES          NO      [REPLAN]
                       /             \          │
        (Loop back to OBSERVE)       [DONE]     ▼
                                          (Check budget &
                                           loop to OBSERVE)
```

---

## 5. Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 NOVA 4.0 AGENT RUNTIME                                 │
│                                                                                        │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                    AgentRuntimeEngine (`core.task_agent.runtime`)                 │  │
│  │  • Owns the Goal Lifecycle & Autonomous Loop                                      │  │
│  │  • Enforces ExecutionBudget (timeouts, max steps, replan thresholds)              │  │
│  │  • Thread-safe control: pause, resume, cancel, confirm                            │  │
│  └─────────────┬──────────────────────────────────────────────────────┬─────────────┘  │
│                │                                                      │                │
│                ▼                                                      ▼                │
│  ┌───────────────────────────┐                          ┌───────────────────────────┐  │
│  │ TaskPlanner (Extended)    │                          │ TaskExecutor (Extended)   │  │
│  │ • Deterministic synthesis │                          │ • Step dependency checker │  │
│  │ • ProviderManager prompt  │                          │ • Context binder          │  │
│  │ • Goal criteria generator │                          │ • Capability dispatcher   │  │
│  └─────────────┬─────────────┘                          └─────────────┬─────────────┘  │
│                │                                                      │                │
│                └──────────────────────┬───────────────────────────────┘                │
│                                       ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                       UNIFIED PERCEPTION & VERIFICATION                          │  │
│  │  ┌─────────────────────────────────────┐  ┌───────────────────────────────────┐  │  │
│  │  │ ObservationProvider                 │  │ GoalVerifier                      │  │  │
│  │  │ • Selective State Capture           │  │ • Evidence-based validation       │  │  │
│  │  │ • EnvironmentContext + ScreenState  │  │ • EyesStateVerifier + Path verify │  │  │
│  │  └─────────────────────────────────────┘  └───────────────────────────────────┘  │  │
│  │  ┌────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ DynamicReplanner (Extended): Diagnostician & Failure Recovery             │  │  │
│  │  └────────────────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                       │                                                │
│  ┌────────────────────────────────────▼─────────────────────────────────────────────┐  │
│  │                           POLICY & GOVERNANCE GATEWAY                            │  │
│  │  • DesktopSafetyPolicy (Path sandbox, deletion confirmation)                     │  │
│  │  • BrowserSafetyPolicy (Sensitive keyword gates, URL guards)                    │  │
│  │  • ConfirmationManager (User approval prompt routing)                            │  │
│  └────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                       │                                                │
│  ┌────────────────────────────────────▼─────────────────────────────────────────────┐  │
│  │                     EXISTING SUBSYSTEM DISPATCH HARNESS                          │  │
│  │  • CapabilityRegistry (Handlers & registered actions)                            │  │
│  │  • BrowserManager (Native AppleScript & session manager)                         │  │
│  │  • ComputerAgent & NovaEyesManager (Retina pointer, Vision OCR, AX)              │  │
│  │  • DesktopActionManager (Files, apps, code editor)                               │  │
│  │  • ProviderManager (Gemini, Groq, OpenRouter, Cerebras)                          │  │
│  │  • EventBus (Thread-safe publish/subscribe to UI EventBridge)                    │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Runtime Lifecycle

The runtime executes according to a strict, predictable lifecycle:
1. **Intake & Initialization:** A goal is submitted via user turn or background worker. An `ExecutionBudget` is allocated.
2. **Context Resolution:** The runtime queries `EnvironmentObserver`, `RecentInteractionContext`, and active window state.
3. **Capability & Policy Pre-Check:** Required capabilities are matched against `CapabilityRegistry`. If permissions or confirmations are needed, execution pauses in `WAITING_USER` state.
4. **Selective Observation (Before):** Runtime captures only the observation dimensions needed for the step.
5. **Execution:** Capability handler executes with bound parameters.
6. **Selective Observation (After):** Immediate post-action observation is taken.
7. **Verification:** `GoalVerifier` compares before/after states against explicit expected criteria.
8. **Recovery Loop:** If verification fails, `DynamicReplanner` classifies failure, applies retry or substitutes sub-plan if budget permits.
9. **Goal Completion:** Holistic criteria verified, resources freed, final summary emitted to UI and speech orchestrator.

---

## 7. Goal Contract

The **Goal** represents the high-level intent, desired outcome, constraints, and objective proof of completion.

* **Extension Point:** Extends `core.task_agent.models.TaskGoal`.
* **Producer:** `TaskPlanner` or direct API / user turn.
* **Consumer:** `AgentRuntimeEngine`, `TaskExecutor`, `GoalVerifier`.
* **Thread Safety:** Immutable once initialized, or protected by runtime lock.
* **Serialization:** Full JSON serialization via Pydantic/dataclass for UI inspection.

```python
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from core.task_agent.models import RiskLevel, TaskStatus

@dataclass
class GoalCriteria:
    """An objective, testable assertion required for goal success."""
    criteria_id: str
    description: str
    verifier_type: str       # "file_exists", "url_match", "process_running", "text_visible", "custom"
    params: dict[str, Any]
    required: bool = True
    passed: bool = False

@dataclass
class Goal:
    """Canonical representation of an autonomous user goal in NOVA 4.0."""
    goal_id: str
    user_request: str
    normalized_goal: str
    success_criteria: list[GoalCriteria] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    deadline: datetime | None = None
    origin: str = "voice"   # "voice", "text", "ui", "proactive"
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

---

## 8. Task Contract

The **Task** represents an instance of an execution attempt designed to satisfy a Goal.

* **Extension Point:** Evolves `core.task_agent.models.TaskPlan`.
* **Producer:** `TaskPlanner`.
* **Consumer:** `AgentRuntimeEngine`.

```python
@dataclass
class Task:
    """An ordered, dependency-tracked execution graph achieving a Goal."""
    task_id: str
    goal: Goal
    steps: list[TaskStep] = field(default_factory=list)
    budget: ExecutionBudget = field(default_factory=lambda: ExecutionBudget())
    status: TaskStatus = TaskStatus.PENDING
    current_step_index: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    replan_cycles: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
```

---

## 9. TaskStep Contract

The **TaskStep** represents an individual operational unit in the task graph.

* **Source of Truth:** Preserves existing `core.task_agent.models.TaskStep` fields while adding action link, timeouts, and verification references.

```python
@dataclass
class TaskStep:
    step_id: str
    description: str
    capability_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    verification_type: str = "custom"
    verification_params: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    status: StepStatus = StepStatus.PENDING
    retry_count: int = 0
    max_retries: int = 2
    timeout_seconds: float = 30.0
    result_data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

---

## 10. Action Contract

A universal specification of an operational command executed against a subsystem.

* **Design Invariant:** The agent selects registered capabilities; it never calls arbitrary OS commands directly.

```python
@dataclass
class Action:
    action_id: str
    capability_name: str
    parameters: dict[str, Any]
    target_description: str
    expected_effect: str
    risk_level: RiskLevel = RiskLevel.LOW
    timeout_seconds: float = 30.0
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
```

---

## 11. ActionResult Contract

Captures the immediate execution output returned by a capability handler before verification.

```python
@dataclass
class ActionResult:
    action_id: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    execution_time_seconds: float = 0.0
    raw_response: Any = None
```

---

## 12. Observation Contract

Represents an instantaneous snapshot of relevant world state. Selective and task-aware.

* **Design Invariant:** Preserves NOVA's local-first Quartz and Apple Vision perception architecture. No continuous cloud screen streaming.

```python
from enum import Enum

class ObservationScope(str, Enum):
    ENVIRONMENT_ONLY = "environment_only"  # Active app, window, URL, Finder selection
    FILESYSTEM_ONLY = "filesystem_only"    # File exists, content hash
    BROWSER_STATE = "browser_state"        # Active tab, URL, page title, DOM extract
    VISUAL_ELEMENTS = "visual_elements"    # Accessibility tree + Vision OCR in-memory
    FULL = "full"                          # Multi-modal complete snapshot

@dataclass
class Observation:
    observation_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    scope: ObservationScope = ObservationScope.ENVIRONMENT_ONLY
    active_application: str | None = None
    active_window: str | None = None
    current_url: str | None = None
    filesystem_matches: dict[str, bool] = field(default_factory=dict)
    screen_elements_count: int = 0
    detected_errors: list[str] = field(default_factory=list)
    raw_environment: dict[str, Any] = field(default_factory=dict)
    # Never serialize full image buffers to logs or UI
    visual_hash: str | None = None
```

---

## 13. Verification Contract

First-class validation answering: **Expected**, **Actual**, **Evidence**, **Result**, **Recoverable**.

```python
class VerificationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNCERTAIN = "uncertain"

@dataclass
class VerificationResult:
    verification_id: str
    step_id: str
    status: VerificationStatus
    expected_state: str
    actual_state: str
    evidence: str
    recoverable: bool = True
    suggested_recovery: str | None = None
    confidence: float = 1.0
```

---

## 14. Recovery Contract

Defines recovery policies and diagnostics when actions fail or verification fails.

```python
class RecoveryAction(str, Enum):
    RETRY_IMMEDIATE = "retry_immediate"
    WAIT_AND_RETRY = "wait_and_retry"
    SUBSTITUTE_CAPABILITY = "substitute_capability"
    REPLAN_SUBGRAPH = "replan_subgraph"
    PROMPT_USER = "prompt_user"
    ABORT = "abort"

@dataclass
class RecoveryDecision:
    decision_id: str
    failed_step_id: str
    failure_type: FailureType
    action: RecoveryAction
    reason: str
    replacement_steps: list[TaskStep] = field(default_factory=list)
    retry_count: int = 0
    remaining_recovery_budget: int = 3
```

---

## 15. PolicyDecision Contract

Every autonomous action must pass through safety policies before invocation.

```python
@dataclass
class PolicyDecision:
    allowed: bool
    policy_name: str         # "DesktopSafetyPolicy", "BrowserSafetyPolicy", "SecretMasking"
    requires_user_confirmation: bool = False
    confirmation_prompt: str = ""
    rejection_reason: str | None = None
    sandbox_path_override: Path | None = None
```

---

## 16. CapabilityRequirement Contract

Defines operational dependencies and permissions required prior to task scheduling.

```python
@dataclass
class CapabilityRequirement:
    capability_name: str
    required_permissions: list[str] = field(default_factory=list) # "accessibility", "screen_recording"
    required_services: list[str] = field(default_factory=list)    # "browser", "desktop", "ocr"
    required_ai_provider: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
```

---

## 17. ExecutionBudget Contract

Prevents infinite loops, unbounded retries, or hanging cloud provider requests.

```python
@dataclass
class ExecutionBudget:
    max_task_duration_seconds: float = 300.0   # 5 minutes default
    max_step_duration_seconds: float = 45.0
    max_total_steps: int = 20
    max_retries_per_step: int = 2
    max_replan_cycles: int = 3
    max_provider_latency_seconds: float = 20.0
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.max_task_duration_seconds
```

---

## 18. AgentState Machine

NOVA 4.0 establishes a clean, bounded state machine mapped directly to existing UI `AvatarState` values:

```
               ┌──────────┐
               │   IDLE   │
               └────┬─────┘
                    │ User turn / Goal received
                    ▼
          ┌───────────────────┐
          │   UNDERSTANDING   │  (Avatar: THINKING)
          └─────────┬─────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ CHECKING_CAPABILITIES │  (Avatar: THINKING)
        └───────────┬───────────┘
                    │
                    ▼
          ┌───────────────────┐
          │     OBSERVING     │  (Avatar: THINKING)
          └─────────┬─────────┘
                    │
                    ▼
          ┌───────────────────┐
          │     PLANNING      │  (Avatar: PLANNING)
          └─────────┬─────────┘
                    │
                    ▼
          ┌───────────────────┐  Requires confirmation
          │  WAITING_POLICY   │ ───────────────────────► ┌──────────────┐
          └─────────┬─────────┘                          │ WAITING_USER │
                    │ Approved                           └──────┬───────┘
                    ▼                                           │ Approved
          ┌───────────────────┐                                 │
          │     EXECUTING     │ ◄───────────────────────────────┘
          └─────────┬─────────┘
                    │
                    ▼
          ┌───────────────────┐
          │     VERIFYING     │  (Avatar: VERIFYING)
          └─────────┬─────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
     Pass                       Fail
        │                       │
        ▼                       ▼
  [More steps?]            ┌────────────┐
   /         \             │ RECOVERING │
 YES          NO           └─────┬──────┘
  │            │                 │
  │            ▼                 ▼
  │      ┌───────────┐     ┌────────────┐
  │      │ COMPLETED │     │ REPLANNING │ (Avatar: PLANNING)
  │      └───────────┘     └─────┬──────┘
  │                              │
  └──────────────────────────────┘
```

### Avatar State Mapping
| AgentState | UI AvatarState | UI Feedback Message |
|---|---|---|
| `IDLE` | `AvatarState.IDLE` | "NOVA ready." |
| `UNDERSTANDING` | `AvatarState.THINKING` | "Analyzing goal..." |
| `CHECKING_CAPABILITIES`| `AvatarState.THINKING` | "Checking system capabilities..." |
| `OBSERVING` | `AvatarState.THINKING` | "Observing active screen state..." |
| `PLANNING` | `AvatarState.PLANNING` | "Synthesizing execution plan..." |
| `WAITING_POLICY` | `AvatarState.THINKING` | "Verifying safety policies..." |
| `WAITING_USER` | `AvatarState.CONFUSED` | "Awaiting user confirmation..." |
| `EXECUTING` | `AvatarState.EXECUTING`| "Executing step {i} of {n}..." |
| `VERIFYING` | `AvatarState.VERIFYING`| "Verifying step outcome..." |
| `RECOVERING` | `AvatarState.EXECUTING`| "Attempting step recovery..." |
| `REPLANNING` | `AvatarState.PLANNING` | "Dynamically replanning approach..." |
| `PAUSED` | `AvatarState.IDLE` | "Task paused." |
| `COMPLETED` | `AvatarState.SUCCESS` | "Task completed successfully." |
| `FAILED` | `AvatarState.ERROR` | "Task failed: {reason}" |
| `CANCELLED` | `AvatarState.IDLE` | "Task cancelled." |

---

## 19. AgentEvent Model

All agent runtime events integrate natively into `core.event_bus.NovaEvent`.

### Event Catalog Extensions
```python
# Extending core.event_bus.NovaEvent
class NovaEvent(str, Enum):
    # Existing core events preserved...
    
    # NOVA 4.0 Agent Runtime Extensions:
    TASK_CREATED = "task_created"
    TASK_UNDERSTANDING = "task_understanding"
    TASK_PLANNING = "task_planning"
    TASK_OBSERVING = "task_observing"
    TASK_STEP_STARTED = "task_step_started"
    TASK_ACTION_STARTED = "task_action_started"
    TASK_ACTION_COMPLETED = "task_action_completed"
    TASK_VERIFICATION_STARTED = "task_verification_started"
    TASK_VERIFICATION_COMPLETED = "task_verification_completed"
    TASK_RECOVERY_STARTED = "task_recovery_started"
    TASK_REPLANNING = "task_replanning"
    TASK_WAITING_USER = "task_waiting_user"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
```

* **Producer:** `AgentRuntimeEngine`, `TaskExecutor`.
* **Consumers:** `ui.backend.event_bridge.EventBridge`, `TerminalDashboard`.
* **Privacy Controls:** Payloads sanitized via `EventBridge._sanitize_dict` to prevent leaking API keys, passwords, or raw visual buffers.

---

## 20. TaskContext Integration

NOVA has three distinct context layers that must not collide:
1. **User Interaction Context (`core.context.RecentInteractionContext`):** Tracks last 10 turns, spoken references, recent active tabs.
2. **Environment Context (`core.environment.EnvironmentContext`):** Real-time OS state: active window, active app, URL, Finder selection.
3. **Task Context (`core.task_agent.models.TaskContext`):** Durable variables produced during the task (`created_folders`, `created_files`, `opened_apps`, `active_urls`).

### Resolution Rule
When resolving a parameter (e.g. `"parent_path": "it"`):
1. Check `TaskContext.variables["it"]` (explicitly produced by a previous step in this task).
2. If absent, check `EnvironmentContext.selected_file_or_folder` (current real OS state).
3. If absent, check `RecentInteractionContext` (conversational history).
4. Real-time observed state **always overrides** stale assumptions.

---

## 21. CapabilityRegistry Integration

The canonical `core.task_agent.registry.CapabilityRegistry` is retained as the single source of truth for actions.

### Schema Preservation
```python
@dataclass
class CapabilityDefinition:
    name: str
    subsystem: str
    description: str
    risk_level: RiskLevel
    handler: Callable[[dict[str, Any], TaskContext], dict[str, Any]]
    verifier: Callable[[dict[str, Any], dict[str, Any], TaskContext], bool] | None = None
    requires_confirmation: bool = False
```

### Safe Extension Point
Add declarative metadata fields without breaking existing handler signatures:
* `timeout_seconds: float = 30.0`
* `required_permissions: tuple[str, ...] = ()`
* `is_idempotent: bool = True`

---

## 22. ProviderManager Integration

The runtime interacts with LLMs **exclusively** through `providers.provider_manager.ProviderManager`.

### Invariants
* **Zero Custom SDK Clients:** Never call `google.genai`, `groq`, or `openai` directly.
* **Deterministic Fallback:** If `ProviderManager` is unavailable or rate-limited:
  - Common tasks use deterministic regex planning (`_try_deterministic_planning`).
  - Pre-registered capabilities execute deterministically without requiring an LLM.
  - NOVA will **never** claim "I cannot control the computer" during an AI outage if the capability itself is local.

---

## 23. Memory Integration

* **Short-Term Context:** Managed via `RecentInteractionContext` and `TaskContext`.
* **Long-Term Memory:** Managed via `memory.memory_manager.MemoryManager` (atomic JSON) and `memory.vector_store.VectorStore` (ChromaDB semantic indexing).
* **Agent Integration:** When a goal completes, high-value learned artifacts (e.g. user project paths, preferred browsers) are persisted under `MemoryCategory.PROJECTS` or `MemoryCategory.TASKS`. Ephemeral screen states are **never** persisted to durable memory.

---

## 24. Eyes & Observation Integration

The runtime consumes perception from `core.eyes.manager.NovaEyesManager` and `core.environment.EnvironmentObserver`.

### Invariants
* In-memory Retina Quartz capture only (`ScreenCaptureKit`).
* Zero disk writes of raw screenshots.
* Selective capture: only invoke heavy `Apple Vision OCR` when visual UI element coordinates or error texts are required.

---

## 25. Browser Integration

* **Subsystem:** `browser.manager.BrowserManager`.
* **Execution:** Communicates with Chrome/Safari via `MacOSNativeBrowserEngine` (AppleScript and URL navigation).
* **Safety:** Evaluated through `browser.safety.BrowserSafetyPolicy` (blocks irreversible financial keywords like `buy`, `transfer money`, `delete account` without explicit user confirmation).

---

## 26. ComputerAgent Integration

* **Subsystem:** `core.computer_agent.ComputerAgent`.
* **Execution:** Retina-aware coordinate clicks and keyboard typing via Quartz.
* **Coordinate Invariant:** Absolute pixel coordinates are **never** hardcoded into the planner. Target coordinates are dynamically resolved at runtime from accessibility labels or OCR entity cards via `EyesTargetResolver`.

---

## 27. Safety & Policy Integration

Autonomous actions pass through a two-tier safety gateway:
1. **Desktop Safety (`desktop.safety.DesktopSafetyPolicy`):**
   - Enforces workspace sandbox (`~/Desktop/NOVA_WORKSPACE` or approved project root).
   - Blocks restricted system roots (`/System`, `/Library`, `/usr`, `/bin`).
2. **Browser Safety (`browser.safety.BrowserSafetyPolicy`):**
   - Checks against `SENSITIVE_KEYWORDS`.
   - Requires user confirmation before proceeding with destructive or financial web actions.

---

## 28. EventBus Integration

All runtime lifecycle transitions publish to `core.event_bus.EventBus`.
* Thread-safe publish/subscribe mechanism utilizing `threading.RLock`.
* Handlers execute synchronously or dispatch to background async queues.

---

## 29. UI Integration Design

* **Gateway:** `ui.backend.event_bridge.EventBridge` translates internal `NovaEvent` instances to `UIEvent` objects broadcast over WebSocket port `8765`.
* **Information Exposure Policy:**
  - **Expose:** Goal description, active step index, step description, verification status, progress percentage, confirmation prompts.
  - **Never Expose:** Internal chain-of-thought, system prompts, API keys, raw base64 frame buffers.

---

## 30. Cancellation

Immediate, hierarchical propagation:
```
User "Stop" / Voice / UI Cancel
       │
       ▼
NovaApplication._execute_local_cancel()
       │
       ├─► AgentRuntimeEngine.cancel_task()
       ├─► TaskExecutor.cancel_task() [Sets _stop_event]
       ├─► ComputerAgent.stop_active_task()
       ├─► DesktopActionManager.stop_active_task()
       └─► BrowserManager.stop_active_task()
```
Every execution loop inspects `self._stop_event.is_set()` before and after every action.

---

## 31. Pause and Resume

* **Pause:** `runtime.pause()` sets `_pause_event`. Any running capability completes its atomic step, but the executor halts before starting the next step.
* **Resume:** `runtime.resume()` clears `_pause_event`.
* **Reconciliation Rule:** Upon resume, the agent **never** assumes the screen or filesystem is unchanged. It takes a fresh `Observation`, compares it with the pre-pause state, and replans if external changes occurred.

---

## 32. Concurrency & Thread Safety

* **Main Thread:** Handles terminal dashboard / UI event pump.
* **Turn Queue Thread:** Executes `NovaApplication._process_turn()`.
* **Agent Runtime Thread:** Multi-step autonomous goals run on a dedicated worker thread `nova-agent-runtime`, freeing the turn queue to accept status queries or "Stop" commands.
* **Locking Hierarchy:** Subsystems utilize dedicated `threading.RLock` instances. Resource acquisition order:
  $$\text{Runtime Lock} \longrightarrow \text{Context Lock} \longrightarrow \text{Subsystem Lock}$$

---

## 33. Error Model & Taxonomy

All runtime errors inherit from `core.exceptions.NovaError`:

```
NovaError (core.exceptions)
   │
   └── AgentRuntimeError
         ├── CapabilityUnavailableError
         ├── PermissionRequiredError
         ├── DependencyMissingError
         ├── ActionExecutionError
         ├── VerificationFailedError
         ├── ObservationTimeoutError
         ├── PolicyViolationError
         ├── TaskBudgetExceededError
         └── AmbiguousGoalError
```

---

## 34. Failure Scenarios Matrix (20 Scenarios)

| # | Failure Scenario | Expected Behavior | Recovery Action | User Communication | Final State |
|---|---|---|---|---|---|
| **1** | Browser closes unexpectedly | Detect missing browser window in post-action observation | Re-launch browser, restore session tab | "Browser closed unexpectedly; restoring session." | Recovered / Re-executed |
| **2** | Website changes layout | Element resolution score drops below threshold | Fallback from visual click to DOM site search | "Website layout changed; attempting direct search." | Recovered |
| **3** | UI element disappears | `EyesTargetResolver` returns `LOW` confidence | Wait 1.0s, re-observe, try alternative element | "Target element disappeared; checking updated screen." | Retried or Replanned |
| **4** | Computer action fails | Quartz click / keypress fails | Check accessibility permission; retry once | "Could not interact with window; retrying." | Failed or Retried |
| **5** | OCR fails | Apple Vision returns empty text | Fallback to macOS Accessibility (`AXUIElement`) | None (silent graceful fallback) | Recovered |
| **6** | Accessibility unavailable | AX API returns permission error | Prompt user to grant macOS Accessibility | "NOVA requires Accessibility permissions in System Settings." | Blocked (`WAITING_USER`) |
| **7** | Nova Eyes unavailable | Screen capture initialization fails | Fallback to pure OS/filesystem/browser automation | "Visual perception unavailable; using system APIs." | Degraded Mode |
| **8** | Permission revoked mid-task | Subsystem catches `PermissionDeniedError` | Halt task immediately without retry | "Permission denied by macOS for this action." | Failed (`PERMISSION`) |
| **9** | Network disconnects | Web request or AI call drops | Classify as `TRANSIENT`; retry with exponential backoff | "Internet connection lost; pausing task." | Paused / Retrying |
| **10** | AI provider quota exhausted | `ProviderManager` catches rate limit | Failover to next provider (Groq $\to$ Cerebras $\to$ Gemini) | None if failover succeeds | Transparent Failover |
| **11** | User changes screen manually | Observation hash mismatch post-pause | Re-observe full state and reconcile with goal | "I noticed the screen changed; adjusting steps." | Replanned |
| **12** | New user voice command during task | Input thread receives new turn | If related: modify context. If "status": report progress | Speaks current step progress | Executing |
| **13** | User says "Stop" | Cancellation signal triggered | Set `_stop_event`, abort active step, release locks | "Task cancelled, Boss." | Cancelled |
| **14** | Verification fails | Verifier returns `False` | Increment step retry; invoke `DynamicReplanner` | "Action did not take effect; trying alternative." | Recovering |
| **15** | Recovery exhausted | Retries exceed `max_replan_cycles` | Terminate task cleanly, preserve created artifacts | "Task could not be completed after 3 attempts." | Failed |
| **16** | Task goal ambiguous | Multiple candidates found | Transition to `WAITING_USER` with specific options | "Did you mean folder A or folder B?" | `WAITING_USER` |
| **17** | Dangerous action requested | Policy flags destructive action | Require explicit spoken/typed confirmation | "Are you sure you want to permanently delete this?" | `WAITING_POLICY` |
| **18** | Capability unavailable | Action not in `CapabilityRegistry` | Report unsupported capability immediately | "I don't have a capability to perform that operation." | Failed (`UNSUPPORTED`) |
| **19** | Dependency missing | External CLI (e.g. ffmpeg) not found | Report prerequisite installation command | "This operation requires ffmpeg, which is not installed."| Failed (`DEPENDENCY`) |
| **20** | Task timeout | `ExecutionBudget.is_expired()` is True | Terminate execution loop cleanly | "Task timed out after reaching maximum duration." | Failed (`TIMEOUT`) |

---

## 35. Security Review

The proposed runtime strictly upholds NOVA's existing security invariants:
1. **Zero Secret Leakage:** All payloads dispatched through `EventBus` pass through `EventBridge._sanitize_dict`, masking API keys and passwords.
2. **Prompt Injection Defense:** External web content extracted by browser tools is marked as untrusted and never fed directly into executive prompt instructions without sandboxing.
3. **Filesystem Sandbox:** `DesktopSafetyPolicy` strictly prohibits write/delete operations in system roots (`/System`, `/Library`, `/usr`, `/bin`).
4. **Browser Safety:** Irreversible operations (payments, account deletions) are blocked by `BrowserSafetyPolicy`.
5. **No Screen Streaming:** Raw visual buffers stay exclusively in RAM; no continuous cloud screen streaming is introduced.

---

## 36. Current $\longrightarrow$ Future Architecture Mapping

| Component | Existing NOVA Implementation | Existing Contract | Safe Extension Point | NOVA 4.0 Design |
|---|---|---|---|---|
| **Goal** | `core.task_agent.models:TaskGoal` | Dataclass (`task_id`, `original_request`, `goal_description`, `success_criteria`) | Add `GoalCriteria` list and deadline | `Goal` (First-class goal model with testable criteria) |
| **Task Planning** | `core.task_agent.planner:TaskPlanner` | `plan_goal(user_request: str) -> TaskPlan` | Keep method signature, extend internal synthesis | `TaskPlanner` with multi-modal criteria synthesis |
| **Task Execution** | `core.task_agent.executor:TaskExecutor` | `execute_plan(plan, context) -> TaskResult` | Add budget check, pause flag, event emission | `TaskExecutor` running as inner step engine |
| **Runtime Engine** | Inlined in `main.py:_handle_task_agent_and_safety_intents` | Ad-hoc turn call | Wrap into dedicated runtime orchestrator | `AgentRuntimeEngine` managing outer autonomous loop |
| **Capabilities** | `core.task_agent.registry:CapabilityRegistry` | Catalog of 26 `CapabilityDefinition` instances | Add metadata (timeouts, permissions) | Preserved single source of truth |
| **Observation** | `core.eyes.manager:NovaEyesManager` | `observe_now(force_ocr) -> ScreenState` | Add selective observation adapter | `ObservationProvider` matching observation to task scope |
| **Verification** | `core.eyes.verifier:EyesStateVerifier` | `verify(action, before, after) -> VerificationOutcome` | Unify with filesystem and browser verifiers | `GoalVerifier` combining visual + OS state proof |
| **Recovery** | `core.task_agent.replanner:DynamicReplanner` | `replan_failed_step(plan, step, fail_type, ctx)` | Add LLM-guided dynamic replanning | `DynamicReplanner` with budget-enforced recovery |
| **AI Brain** | `providers.provider_manager:ProviderManager` | `generate_response(prompt, task_type)` | Preserve routing and failover tables | Unchanged; consumed via standard interface |
| **Events** | `core.event_bus:EventBus` | `publish(event: NovaEvent, **payload)` | Add task lifecycle events to `NovaEvent` enum | Single unified EventBus |
| **Safety** | `desktop.safety:DesktopSafetyPolicy`, `browser.safety` | `evaluate(plan) -> plan` | Pre-execution gate checking action risk | `PolicyDecision` gatekeeper |
| **UI Stream** | `ui.backend.event_bridge:EventBridge` | Translates `NovaEvent` to `UIEvent` | Wire new task events to UI event mappings | Stream live step progress and avatar states |

---

## 37. Duplication Avoidance Analysis

To protect codebase integrity, the following directives are strictly mandated:

| Subsystem Component | Status | Architectural Mandate |
|---|---|---|
| **Agent Manager / Orchestrator** | **EXTEND EXISTING** | Extend `core.task_agent`. Do **NOT** create a parallel `agent_manager/` package. |
| **Planner** | **EXTEND EXISTING** | Extend `core.task_agent.planner:TaskPlanner`. Do **NOT** create a second planner. |
| **Executor** | **EXTEND EXISTING** | Extend `core.task_agent.executor:TaskExecutor`. Do **NOT** create a parallel executor. |
| **Capability Registry** | **KEEP EXISTING** | Retain `core.task_agent.registry:CapabilityRegistry`. Do **NOT** create a second registry. |
| **Browser Controller** | **KEEP / WRAP** | Retain `browser.manager:BrowserManager`. Do **NOT** write a separate browser controller. |
| **Computer / Mouse / Keyboard**| **KEEP / WRAP** | Retain `core.computer_agent:ComputerAgent` and `core.eyes.interaction`. Do **NOT** duplicate Quartz bindings. |
| **Screen Perception (Eyes)** | **KEEP EXISTING** | Retain `core.eyes.manager:NovaEyesManager`. Do **NOT** create a second screenshot/vision engine. |
| **AI Provider Client** | **KEEP EXISTING** | Retain `providers.provider_manager:ProviderManager`. Do **NOT** introduce direct cloud SDK calls. |
| **Event Bus** | **KEEP EXISTING** | Retain `core.event_bus:EventBus`. Do **NOT** create a second event bus. |
| **Memory Manager** | **KEEP EXISTING** | Retain `memory.memory_manager:MemoryManager`. Do **NOT** create parallel storage files. |
| **Safety Policies** | **KEEP / WRAP** | Retain `DesktopSafetyPolicy` and `BrowserSafetyPolicy`. Do **NOT** bypass them. |
| **UI Event Bridge** | **EXTEND EXISTING** | Extend `ui.backend.event_bridge:EventBridge`. Do **NOT** create a competing WebSocket server. |

---

## 38. Extension Points

1. **`core.task_agent.models`:** Add `GoalCriteria`, `Observation`, `VerificationResult`, `ExecutionBudget`, and `RecoveryDecision` dataclasses.
2. **`core.task_agent.registry`:** Add optional metadata fields (`timeout_seconds`, `required_permissions`) to `CapabilityDefinition`.
3. **`core.event_bus.NovaEvent`:** Add `TASK_*` lifecycle events.
4. **`core.task_agent.executor`:** Inject `EventBus` reference into `TaskExecutor` to publish real-time step events during execution.
5. **`ui.backend.event_bridge`:** Map new `NovaEvent.TASK_*` events to existing `UIEventType` and `AvatarState` values.
6. **`core.exceptions`:** Add `AgentRuntimeError` hierarchy.

---

## 39. Implementation Phases

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE A: Contract & Model Foundation                                    │
│ • Define GoalCriteria, ExecutionBudget, VerificationResult in models.py │
│ • Add AgentRuntimeError hierarchy in exceptions.py                      │
│ • Add TASK_* events to NovaEvent enum in event_bus.py                   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE B: EventBus & UI Telemetry Integration                            │
│ • Wire TaskExecutor to publish NovaEvent on step lifecycle transitions  │
│ • Map events in EventBridge to stream progress to React desktop UI      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE C: Perception & Verification Modernization                        │
│ • Create ObservationProvider adapter wrapping NovaEyesManager           │
│ • Formalize GoalVerifier comparing before/after observations            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE D: Runtime Engine & Execution Budget                              │
│ • Introduce AgentRuntimeEngine coordinating multi-step autonomous loop  │
│ • Integrate execution budgets (wall-clock timeout, step limits)         │
│ • Implement pause, resume, and graceful cancellation reconciliation     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE E: Dynamic Replanning & Failure Recovery                          │
│ • Extend DynamicReplanner with bounded alternative strategy synthesis   │
│ • Implement duplicate-action prevention and loop detection              │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE F: Background & Long-Running Task Support                         │
│ • Enable background task worker thread without blocking user turns      │
│ • Wire terminal dashboard progress bars and activity screen feed        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE G: Comprehensive Regression & Matrix Evaluation                   │
│ • Validate full 8-point task agent matrix and add new resilience tests  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Phase Details
* **Phase A (Foundation):**
  - *Files:* `core/task_agent/models.py`, `core/exceptions.py`, `core/event_bus.py`.
  - *Risk:* Low. Non-breaking additions of data structures.
  - *Rollback:* Revert added dataclasses.
* **Phase B (Telemetry):**
  - *Files:* `core/task_agent/executor.py`, `ui/backend/event_bridge.py`.
  - *Risk:* Low. Purely observational event dispatch.
  - *Rollback:* Disable event publishing in executor.
* **Phase C (Verification):**
  - *Files:* `core/task_agent/verifier.py` (new), `core/eyes/verifier.py`.
  - *Risk:* Medium. Must ensure verifiers do not produce false negatives on slow UIs.
  - *Rollback:* Retain existing heuristic verifiers.
* **Phase D (Runtime Loop):**
  - *Files:* `core/task_agent/runtime.py` (new), `main.py`.
  - *Risk:* Medium. Turn queue routing adjustments.
  - *Rollback:* Route `RoutingDomain.TASK_AGENT` directly to legacy `TaskExecutor`.
* **Phase E (Replanning):**
  - *Files:* `core/task_agent/replanner.py`.
  - *Risk:* Low-Medium. Bounded by `max_replan_cycles = 3`.
  - *Rollback:* Revert to deterministic 2-fallback replanning.

---

## 40. Open Questions & Unknowns

1. **Background Task Concurrency:** Should NOVA allow multiple background agent tasks simultaneously, or enforce strictly one foreground task and at most one background task to avoid macOS window focus conflicts? *(Recommendation: Exactly one active desktop/visual task at a time, with queued background tasks).*
2. **Visual Observation Sampling Frequency:** When running long-running browser or coding workflows, what is the optimal observation sampling rate to prevent unnecessary CPU load on Apple Silicon? *(Recommendation: Event-driven observation triggered only before and after discrete actions, not continuous polling).*
3. **User Confirmation UI Flow:** When `WAITING_USER` state is entered, should the confirmation prompt trigger a modal in Electron, a voice prompt, or both? *(Recommendation: Dual-channel — speak prompt via VoiceManager and display confirmation dialog in React UI).*

---

## NOVA 4.0 AGENT RUNTIME DECISION

### 1. What existing NOVA components are sufficient?
* `core.task_agent.registry:CapabilityRegistry` — Comprehensive, verified catalog of 26+ capabilities covering filesystem, document editing, applications, browser, screen capture, and system controls.
* `core.event_bus:EventBus` — Robust thread-safe publish/subscribe bus.
* `providers.provider_manager:ProviderManager` — Complete multi-provider router with instant failover across Gemini, Groq, OpenRouter, and Cerebras.
* `core.eyes.manager:NovaEyesManager` — In-memory ScreenCaptureKit Retina stream, Accessibility inspector, and Apple Vision OCR.
* `core.computer_agent:ComputerAgent` — Quartz mouse/keyboard interaction engine with coordinate-free semantic element resolution.
* `browser.manager:BrowserManager` — Native AppleScript and URL automation engine.
* `memory.memory_manager:MemoryManager` — Atomic JSON persistence and ChromaDB VectorStore.
* `desktop.safety:DesktopSafetyPolicy` and `browser.safety:BrowserSafetyPolicy` — Proven safety sandboxes.

### 2. What must be extended?
* `core.task_agent.models` — Must add `GoalCriteria`, `ExecutionBudget`, `VerificationResult`, and `RecoveryDecision` models.
* `core.task_agent.executor:TaskExecutor` — Must publish lifecycle events to `EventBus` and enforce `ExecutionBudget`.
* `core.task_agent.replanner:DynamicReplanner` — Must support LLM-guided dynamic replanning when deterministic fallbacks do not apply.
* `core.event_bus.NovaEvent` — Must add task-specific event topics.
* `ui.backend.event_bridge:EventBridge` — Must map task events to stream live progress to React/Electron.

### 3. What genuinely new abstractions are required?
* `core.task_agent.runtime:AgentRuntimeEngine` — A dedicated orchestrator for the autonomous loop (Understand $\to$ Observe $\to$ Plan $\to$ Policy Check $\to$ Act $\to$ Verify $\to$ Recover). This cannot live cleanly in `main.py` without bloating the application entry point.
* `core.task_agent.verifier:GoalVerifier` — A unified verification engine uniting filesystem, visual hash, URL matching, and process checking into an evidence-based contract.

### 4. What should NOT be changed?
* The signature and behavior of `CapabilityDefinition.handler`.
* The public API of `ProviderManager.generate_response`.
* The local-first, in-memory perception architecture of `NovaEyesManager`.
* The turn queue processing loop in `NovaApplication`.
* The security sandboxes preventing system-root modification.

### 5. What is the safest implementation order?
1. Phase A: Models & Contracts (`core/task_agent/models.py`, `core/exceptions.py`, `core/event_bus.py`).
2. Phase B: EventBus & UI Progress Telemetry.
3. Phase C: Perception & Verification Modernization.
4. Phase D: AgentRuntimeEngine & Execution Budget.
5. Phase E: Dynamic Replanning & Error Recovery.
6. Phase F: Background execution & dashboard widgets.

### 6. What are the biggest architectural risks?
* **UI Focus Stealing:** If an autonomous computer action clicks an element while the user is typing, it may interfere with user activity. (Mitigation: Clear avatar state indication, pause on user input).
* **False Verification Negatives:** High-latency web pages may cause verifiers to evaluate before DOM render completes. (Mitigation: Bounded exponential retry with backoff).

### 7. What must be tested before each phase?
* All 8 test cases in `tests/test_task_agent_matrix.py` must pass with zero failures.
* All unit tests in `tests/test_task_models.py`, `tests/test_task_planner.py`, `tests/test_task_executor.py`, and `tests/test_task_replanning.py` must pass.
* Verification that no new background threads linger after `NovaApplication._shutdown()`.

### 8. What should be postponed?
* Multi-agent collaborative swarms (unnecessary complexity for local macOS assistant).
* Continuous video recording of tasks.
* Cloud screen streaming.
* Autonomous external bash terminal script synthesis without confirmation.
