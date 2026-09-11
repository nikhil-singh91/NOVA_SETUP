# NOVA Autonomous Task Agent V3 Engineering Report
**Goal Planning, Multi-Step Execution & Replanning Subsystem**

---

## 1. Executive Summary

NOVA has evolved from a single-command reactive assistant into a full **Autonomous Computer Task Agent (V3)**. Operating through the loop:
$$\text{GOAL} \longrightarrow \text{UNDERSTAND} \longrightarrow \text{PLAN} \longrightarrow \text{EXECUTE STEP-BY-STEP} \longrightarrow \text{VERIFY} \longrightarrow \text{REPLAN} \longrightarrow \text{FINAL VERIFICATION}$$

NOVA autonomously breaks down high-level, multi-stage human objectives into directed acyclic dependency plans, executes each step against verified native subsystems, performs immediate step verification, autonomously recovers and replans if intermediate actions fail, preserves state across multiple conversational turns, and rigorously enforces destructive action safety.

---

## 2. Core Architecture

```
                                  USER HIGH-LEVEL GOAL
                                            │
                                            ▼
                             ┌──────────────────────────────┐
                             │    Intent & Goal Planner     │
                             │ (TaskPlanner + ProviderMgr)  │
                             └──────────────┬───────────────┘
                                            │
                                            ▼
                             ┌──────────────────────────────┐
                             │       Structured Plan        │
                             │  TaskPlan: [TaskStep 1..N]   │
                             └──────────────┬───────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 TaskExecutor Loop                                      │
│                                                                                        │
│  ┌───────────────────────┐   Parameter Binding   ┌──────────────────────────────────┐  │
│  │ Check Cancellation /  │ ─────────────────────►│  Execute Step via Verified       │  │
│  │ Dependency Resolution │                       │  Capability Registry             │  │
│  └───────────────────────┘                       └────────────────┬─────────────────┘  │
│                                                                   │                    │
│                                                                   ▼                    │
│  ┌───────────────────────┐    Replan Bounded     ┌──────────────────────────────────┐  │
│  │ Dynamic Replanner     │ ◄──────────────────── │  Step Verification (fs/browser/  │  │
│  │ (Failure Classifier)  │      Step Failure     │  visual confirmation)            │  │
│  └───────────────────────┘                       └────────────────┬─────────────────┘  │
│                                                                   │                    │
│                                                          Step Verified                 │
│                                                                   │                    │
│                                                                   ▼                    │
│                                                  ┌──────────────────────────────────┐  │
│                                                  │ Update TaskContext & Environment │  │
│                                                  └──────────────────────────────────┘  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
                             ┌──────────────────────────────┐
                             │   Final Goal Verification    │
                             │ (Holistic Directory / State) │
                             └──────────────┬───────────────┘
                                            │
                                            ▼
                             ┌──────────────────────────────┐
                             │  Concise Voice Status Report │
                             └──────────────────────────────┘
```

---

## 3. Subsystem Modules

| Subsystem Component | Path | Responsibility |
| :--- | :--- | :--- |
| **Data Models** | `core/task_agent/models.py` | `TaskGoal`, `TaskPlan`, `TaskStep`, `TaskContext`, `TaskResult`, `TaskStatus`, `StepStatus`, `FailureType`, `RiskLevel` |
| **Capability Registry** | `core/task_agent/registry.py` | Strict, verified catalog of capability executors across Filesystem, Browser, Desktop, Visual, and Document writing |
| **Task Planner** | `core/task_agent/planner.py` | Decomposes compound, nested, and arbitrary requests into validated multi-step plans with explicit dependencies |
| **Dynamic Replanner** | `core/task_agent/replanner.py` | Classifies runtime step failures and produces bounded recovery sub-plans |
| **Task Executor** | `core/task_agent/executor.py` | Sequential execution engine with parameter binding, step verification, cancellation checks, and holistic goal verification |
| **Intent Engine Routing**| `intent/router.py`, `intent/matcher.py` | Routes compound and autonomous tasks to `RoutingDomain.TASK_AGENT` / `CanonicalIntent.AUTONOMOUS_TASK` |
| **Main Orchestrator** | `main.py` | Coordinates persistent `TaskContext` across turns and dispatches autonomous tasks |

---

## 4. Capability Selection Hierarchy

NOVA strictly follows a 4-tier capability selection policy:
1. **Tier 1: Structured APIs** (Native Filesystem `create_folder`, `create_files`, direct URL routing).
2. **Tier 2: Existing Subsystems** (Browser Automation Manager, Desktop Application Manager).
3. **Tier 3: Accessibility / Shell APIs** (`open` Finder, TextEdit, Camera).
4. **Tier 4: Visual UI Fallback** (Computer Agent V2 `click_element`, `type_into_focused_or_target`, `close_popup`).

> [!IMPORTANT]
> **Safety Invariant**: Under no circumstances are arbitrary unverified AI shell commands executed. All steps map to registered, type-safe Python capability definitions.

---

## 5. Verification Matrix (8/8 Matrix & 156/156 Total Repo Tests)

| # | Test Scenario | Execution Mode | Verification Outcome |
| :--- | :--- | :--- | :--- |
| **1** | *"Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders."* | Multi-step Filesystem Plan (4 steps) | **PASS** — Desktop root folder and 3 sibling subfolders verified. |
| **2** | *"Create a C++ project with main.cpp and README.md."* | Multi-step Project Scaffolding (3 steps) | **PASS** — Project folder, `main.cpp` starter code, and `README.md` verified. |
| **3** | *"Open Google and search DSA roadmap."* | Native Browser Automation | **PASS** — Google search / direct roadmap navigation executed. |
| **4** | *"Go to Flipkart and search mobile phones."* | In-Site Browser Automation | **PASS** — Flipkart store search navigation executed. |
| **5** | *"Find a Python tutorial and save the useful link in a text file."* | Compound Cross-Subsystem Plan | **PASS** — Web search initiated & link document created on Desktop. |
| **6** | Multi-step task started $\rightarrow$ *"Stop"* | Immediate Cancellation | **PASS** — `TaskExecutor.cancel_task()` stopped running execution. |
| **7** | Step Failure $\rightarrow$ Bounded Recovery | Dynamic Replanning Sub-Plan | **PASS** — Step failure classified, substitute step generated and verified. |
| **8** | *"Create a folder called AlphaProject on Desktop"* $\rightarrow$ *"Now create main.cpp inside it"* | Cross-Turn Context Resolution | **PASS** — `"it"` correctly resolved to `AlphaProject` across conversational turns. |

---

## 6. Summary of Test Execution
- Total Repository Tests: **156 passed in 31.41s** (0 failures, 0 regressions).
- Task Agent Unit & Matrix Suites: **10/10 passed in 6.58s**.
