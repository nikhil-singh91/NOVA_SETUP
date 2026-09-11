"""Sequential task executor with step verification, dynamic replanning, and goal validation."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.environment import EnvironmentContext, environment_observer
from core.logger import get_logger
from core.task_agent.models import (
    FailureType,
    RiskLevel,
    StepStatus,
    TaskContext,
    TaskGoal,
    TaskPlan,
    TaskResult,
    TaskStatus,
    TaskStep,
)
from core.task_agent.registry import CapabilityRegistry, capability_registry
from core.task_agent.replanner import DynamicReplanner

logger = get_logger(__name__)


def log_task_agent_debug(stage: str, details: dict[str, Any]) -> None:
    """Log structured debug telemetry if NOVA_TASK_AGENT_DEBUG is enabled."""
    if os.getenv("NOVA_TASK_AGENT_DEBUG", "false").lower() == "true":
        logger.info(
            "[TASK_AGENT_DEBUG] %s => %s",
            stage.upper(),
            " | ".join(f"{k}={v}" for k, v in details.items()),
        )


class TaskExecutor:
    """Executes structured TaskPlans with dynamic parameter binding, step verification, and replanning."""

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        replanner: DynamicReplanner | None = None,
    ) -> None:
        self.registry = registry or capability_registry
        self.replanner = replanner or DynamicReplanner(self.registry)
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()
        self.current_context: TaskContext | None = None

    def cancel_task(self) -> bool:
        """Interrupt and cancel any running autonomous task."""
        self._stop_event.set()
        logger.info("TaskExecutor stop requested.")
        return True

    def reset_cancellation(self) -> None:
        """Reset cancellation and pause flags for new execution."""
        self._stop_event.clear()
        self._pause_event.clear()

    # =========================================================================
    # PRIMARY EXECUTION ENGINE
    # =========================================================================

    def execute_plan(
        self,
        plan: TaskPlan,
        context: TaskContext | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> TaskResult:
        """Execute a TaskPlan step-by-step with verification and dynamic recovery."""
        ctx = context or TaskContext(task_id=plan.task_id)
        self.current_context = ctx

        if self._stop_event.is_set():
            plan.status = TaskStatus.CANCELLED
            return TaskResult(
                task_id=plan.task_id,
                success=False,
                status=TaskStatus.CANCELLED,
                message="Task was cancelled by user.",
                spoken_response="Task cancelled, Boss.",
                completed_steps=0,
                total_steps=len(plan.steps),
                context=ctx,
                error="Cancelled by user",
            )

        plan.status = TaskStatus.RUNNING

        log_task_agent_debug("TASK_STARTED", {
            "task_id": plan.task_id,
            "goal": plan.goal.goal_description,
            "steps_count": len(plan.steps),
        })

        if not plan.steps:
            return TaskResult(
                task_id=plan.task_id,
                success=True,
                status=TaskStatus.COMPLETED,
                message="No executable steps required.",
                spoken_response="Task completed, Boss.",
                final_verification_passed=True,
                context=ctx,
            )

        step_queue = list(plan.steps)
        completed_count = 0
        replan_cycles = 0
        max_replan_cycles = 3

        while step_queue:
            # 1. Cancellation Check
            if self._stop_event.is_set():
                plan.status = TaskStatus.CANCELLED
                log_task_agent_debug("TASK_CANCELLED", {"task_id": plan.task_id, "completed": completed_count})
                return TaskResult(
                    task_id=plan.task_id,
                    success=False,
                    status=TaskStatus.CANCELLED,
                    message="Task was cancelled by user.",
                    spoken_response="Task cancelled, Boss.",
                    completed_steps=completed_count,
                    total_steps=len(plan.steps),
                    context=ctx,
                    error="Cancelled by user",
                )

            current_step = step_queue.pop(0)
            current_step.status = StepStatus.RUNNING
            current_step.started_at = datetime.now(timezone.utc)

            # 2. Dependency Validation
            if not plan.are_dependencies_met(current_step):
                current_step.status = StepStatus.FAILED
                current_step.error_message = "Prerequisite steps have not completed."
                return TaskResult(
                    task_id=plan.task_id,
                    success=False,
                    status=TaskStatus.FAILED,
                    message=f"Step '{current_step.step_id}' failed: dependencies unmet.",
                    spoken_response=f"Task could not proceed: {current_step.description} was blocked.",
                    failed_step=current_step,
                    context=ctx,
                )

            # 3. Dynamic Parameter Binding from TaskContext
            bound_params = self._bind_parameters(current_step.parameters, ctx)

            # 4. Optional Progress Notification
            if progress_callback and current_step.description:
                progress_callback(current_step.description)

            log_task_agent_debug("STEP_EXECUTING", {
                "step_id": current_step.step_id,
                "capability": current_step.capability_name,
                "description": current_step.description,
            })

            # 5. Capability Resolution & Execution
            cap_def = self.registry.get(current_step.capability_name)
            if not cap_def:
                current_step.status = StepStatus.FAILED
                current_step.error_message = f"Capability '{current_step.capability_name}' not registered."
                return TaskResult(
                    task_id=plan.task_id,
                    success=False,
                    status=TaskStatus.FAILED,
                    message=current_step.error_message,
                    spoken_response="I encountered an unsupported operation.",
                    failed_step=current_step,
                    context=ctx,
                )

            step_success = False
            exec_result: dict[str, Any] = {}

            try:
                exec_result = cap_def.handler(bound_params, ctx)
                step_success = bool(exec_result.get("success", False))
                current_step.result_data = exec_result

                # 6. Step-Level Verification
                if step_success and cap_def.verifier:
                    step_success = cap_def.verifier(bound_params, exec_result, ctx)

            except Exception as exc:
                logger.error("Exception during step '%s': %s", current_step.step_id, exc)
                step_success = False
                exec_result = {"success": False, "error": str(exc)}

            # 7. Evaluate Step Outcome & Replanning
            if step_success:
                current_step.status = StepStatus.COMPLETED
                current_step.completed_at = datetime.now(timezone.utc)
                ctx.completed_steps.append(current_step.step_id)
                completed_count += 1
                log_task_agent_debug("STEP_COMPLETED", {"step_id": current_step.step_id})
            else:
                current_step.retry_count += 1
                err_msg = exec_result.get("error", "Execution failed")
                current_step.error_message = err_msg
                fail_type = self.replanner.classify_failure(err_msg)

                log_task_agent_debug("STEP_FAILED", {
                    "step_id": current_step.step_id,
                    "failure_type": fail_type.value,
                    "error": err_msg,
                    "retry_count": current_step.retry_count,
                })

                # Check Retry Eligibility
                if self.replanner.can_retry_step(current_step, fail_type):
                    time.sleep(0.3)
                    step_queue.insert(0, current_step)  # Re-enqueue for retry
                    continue

                # Check Dynamic Replanning
                if replan_cycles < max_replan_cycles:
                    replan_cycles += 1
                    sub_steps = self.replanner.replan_failed_step(plan, current_step, fail_type, ctx)
                    if sub_steps:
                        log_task_agent_debug("REPLAN_SUBSTITUTED", {
                            "replan_cycle": replan_cycles,
                            "new_steps": [s.step_id for s in sub_steps],
                        })
                        step_queue = sub_steps + step_queue
                        continue

                # Fatal Step Failure
                current_step.status = StepStatus.FAILED
                plan.status = TaskStatus.FAILED
                return TaskResult(
                    task_id=plan.task_id,
                    success=False,
                    status=TaskStatus.FAILED,
                    message=f"Step '{current_step.description}' failed: {err_msg}",
                    spoken_response=f"Task could not be fully completed: {err_msg}.",
                    failed_step=current_step,
                    completed_steps=completed_count,
                    total_steps=len(plan.steps),
                    context=ctx,
                    error=err_msg,
                )

        # 8. Final Goal Verification
        final_ok = self._verify_final_goal(plan, ctx)
        log_task_agent_debug("FINAL_VERIFICATION", {"passed": final_ok})

        plan.status = TaskStatus.COMPLETED if final_ok else TaskStatus.FAILED
        spoken_msg = f"Task completed: {plan.goal.goal_description}" if final_ok else "Task finished with verification warnings."

        return TaskResult(
            task_id=plan.task_id,
            success=final_ok,
            status=plan.status,
            message="All steps executed and verified successfully.",
            spoken_response=spoken_msg,
            completed_steps=completed_count,
            total_steps=len(plan.steps),
            final_verification_passed=final_ok,
            context=ctx,
        )

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _bind_parameters(self, params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
        """Resolve dynamic variables and deictic references ('it', 'parent_path') using TaskContext."""
        bound = dict(params)
        for k, v in bound.items():
            if isinstance(v, str):
                if v.lower() == "it":
                    if ctx.last_created_folder:
                        bound[k] = str(ctx.last_created_folder)
                    elif ctx.last_created_file:
                        bound[k] = str(ctx.last_created_file)
                elif v in ctx.variables:
                    bound[k] = str(ctx.variables[v])
        return bound

    def _verify_final_goal(self, plan: TaskPlan, ctx: TaskContext) -> bool:
        """Verify that holistic criteria (files/folders created by this plan) exist on the system."""
        for step in plan.steps:
            if step.status == StepStatus.COMPLETED and step.result_data.get("path"):
                p = Path(step.result_data["path"])
                if step.capability_name == "fs.create_folder" and not p.is_dir():
                    logger.warning("Final verification failed: folder at %s missing", p)
                    return False
                elif step.capability_name == "fs.create_file" and not p.is_file():
                    logger.warning("Final verification failed: file at %s missing", p)
                    return False
        return True


# Global singleton TaskExecutor
task_executor = TaskExecutor()
