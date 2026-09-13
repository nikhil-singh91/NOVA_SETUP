# 11 — Autonomous Task Agent V3 Subsystem

## Overview
NOVA includes an Autonomous Task Agent (`core.task_agent`) that plans, executes, verifies, and dynamically recovers multi-step operational tasks on macOS.

---

## 🏗️ Core Architecture Components

```
User Goal ("Create a project folder, scaffold a Python script, and search Google for docs")
         │
         ▼
[TaskPlanner (`core.task_agent.planner.TaskPlanner`)]
  ├── Decomposes goal into sequential `TaskStep` definitions
  ├── Assigns step IDs, capability names, parameter dicts, and dependencies
  └── Returns a validated `TaskPlan`
         │
         ▼
[TaskExecutor (`core.task_agent.executor.TaskExecutor`)]
  ├── Iterates through `plan.steps` sequentially
  ├── Step Pre-check: Validates step dependencies and cancellation flags
  ├── Capability Dispatch: Looks up capability handler in `CapabilityRegistry`
  ├── Step Execution: Runs handler with `TaskContext`
  ├── Step Verification: Executes capability-specific verifier function
  │     ├──> Step Succeeded: Updates `TaskContext` and advances to next step
  │     └──> Step Failed: Invokes `DynamicReplanner`
         │
         ▼
[DynamicReplanner (`core.task_agent.replanner.DynamicReplanner`)]
  ├── Analyzes step failure, error message, and real-time screen state
  ├── Generates alternative steps (e.g. alternate path, browser fallback)
  ├── Injects recovery steps into active plan
  └── Allows up to `max_replans=3` before declaring task failure
```

---

## 📦 Data Models (`core.task_agent.models`)
- **`TaskGoal`:** High-level description, priority, and risk rating.
- **`TaskStep`:** `step_id`, `name`, `capability`, `parameters`, `status` (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `CANCELLED`), `dependencies`, `result`, `error`.
- **`TaskPlan`:** `plan_id`, `goal`, `steps`, `status`, `max_steps=10`, `timeout_seconds=120.0`.
- **`TaskContext`:** Shared state across steps tracking created folders, files, opened apps, active URLs, and artifacts.
- **`TaskResult`:** Final outcome with execution time, steps completed, and spoken response.
