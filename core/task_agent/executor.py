"""Sequential task executor with step verification, dynamic replanning, and goal validation."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.event_bus import EventBus, NovaEvent
from core.logger import get_logger
from core.task_agent.models import (
    StepStatus,
    TaskContext,
    TaskPlan,
    TaskResult,
    TaskStatus,
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
    """Executes structured TaskPlans with dynamic parameter binding, step verification,
    and replanning.
    """

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        replanner: DynamicReplanner | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.registry = registry or capability_registry
        self.replanner = replanner or DynamicReplanner(self.registry)
        self._event_bus: EventBus | None = event_bus
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.Lock()
        self.current_context: TaskContext | None = None

    @property
    def event_bus(self) -> EventBus | None:
        """Access the current EventBus, falling back to the service registry if available."""
        if self._event_bus is not None:
            return self._event_bus
        try:
            from core.registry import registry as global_registry

            if global_registry.exists("event_bus"):
                return global_registry.get("event_bus")
        except Exception:
            pass
        return None

    @event_bus.setter
    def event_bus(self, bus: EventBus | None) -> None:
        self._event_bus = bus

    def _safe_publish(self, event: NovaEvent, **payload: Any) -> None:
        """Safely publish telemetry to EventBus without risking task execution."""
        try:
            bus = self.event_bus
            if bus is not None:
                bus.publish(event, **payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telemetry publish failed for event '%s': %s", event.value, exc)

    def cancel_task(self) -> bool:
        """Interrupt and cancel any running autonomous task."""
        self._stop_event.set()
        self._pause_event.clear()
        logger.info("TaskExecutor stop requested.")
        return True

    def pause_task(self) -> bool:
        """Pause task execution loop."""
        self._pause_event.set()
        task_id = self.current_context.task_id if self.current_context else ""
        self._safe_publish(
            NovaEvent.TASK_PAUSED,
            task_id=task_id,
            status="paused",
            timestamp=time.time(),
            message="Task execution paused.",
        )
        return True

    def resume_task(self) -> bool:
        """Resume task execution loop."""
        self._pause_event.clear()
        task_id = self.current_context.task_id if self.current_context else ""
        self._safe_publish(
            NovaEvent.TASK_RESUMED,
            task_id=task_id,
            status="running",
            timestamp=time.time(),
            message="Task execution resumed.",
        )
        return True

    def reset_cancellation(self) -> None:
        """Reset cancellation and pause flags for new execution."""
        self._stop_event.clear()
        self._pause_event.clear()

    # =========================================================================
    # PRIMARY EXECUTION ENGINE
    # =========================================================================

    def execute_plan(  # noqa: C901
        self,
        plan: TaskPlan,
        context: TaskContext | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> TaskResult:
        """Execute a TaskPlan step-by-step with verification and dynamic recovery."""
        ctx = context or TaskContext(task_id=plan.task_id)
        self.current_context = ctx
        goal_id = (
            getattr(plan.goal, "goal_id", None)
            or getattr(plan.goal, "task_id", None)
            or plan.task_id
        )

        if self._stop_event.is_set():
            plan.status = TaskStatus.CANCELLED
            self._safe_publish(
                NovaEvent.TASK_CANCELLED,
                task_id=plan.task_id,
                goal_id=goal_id,
                status="cancelled",
                completed_steps=0,
                total_steps=len(plan.steps),
                message="Task was cancelled by user.",
                timestamp=time.time(),
            )
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

        self._safe_publish(
            NovaEvent.TASK_CREATED,
            task_id=plan.task_id,
            goal_id=goal_id,
            goal_description=plan.goal.goal_description,
            total_steps=len(plan.steps),
            status="running",
            progress_percent=0.0,
            timestamp=time.time(),
            message=f"Starting task: {plan.goal.goal_description}",
        )

        if not plan.steps:
            self._safe_publish(
                NovaEvent.TASK_COMPLETED,
                task_id=plan.task_id,
                goal_id=goal_id,
                status="completed",
                completed_steps=0,
                total_steps=0,
                success=True,
                progress_percent=100.0,
                final_verification_passed=True,
                message="No executable steps required.",
                timestamp=time.time(),
            )
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
            # 0. Pause Check
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.05)

            # 1. Cancellation Check
            if self._stop_event.is_set():
                plan.status = TaskStatus.CANCELLED
                log_task_agent_debug(
                    "TASK_CANCELLED",
                    {"task_id": plan.task_id, "completed": completed_count},
                )
                self._safe_publish(
                    NovaEvent.TASK_CANCELLED,
                    task_id=plan.task_id,
                    goal_id=goal_id,
                    status="cancelled",
                    completed_steps=completed_count,
                    total_steps=len(plan.steps),
                    message="Task was cancelled by user.",
                    timestamp=time.time(),
                )
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
            current_step.started_at = datetime.now(UTC)

            # Deterministic step index and progress percentage
            step_idx = completed_count + 1
            tot_steps = len(plan.steps)
            prog_pct = round((completed_count / max(1, tot_steps)) * 100.0, 1)

            self._safe_publish(
                NovaEvent.TASK_STEP_STARTED,
                task_id=plan.task_id,
                goal_id=goal_id,
                step_id=current_step.step_id,
                step_index=step_idx,
                total_steps=tot_steps,
                capability=current_step.capability_name,
                description=current_step.description,
                status="running",
                progress_percent=prog_pct,
                timestamp=time.time(),
                message=f"Step {step_idx}/{tot_steps}: {current_step.description}",
            )

            # 2. Dependency Validation
            if not plan.are_dependencies_met(current_step):
                current_step.status = StepStatus.FAILED
                current_step.error_message = "Prerequisite steps have not completed."
                plan.status = TaskStatus.FAILED
                self._safe_publish(
                    NovaEvent.TASK_FAILED,
                    task_id=plan.task_id,
                    goal_id=goal_id,
                    step_id=current_step.step_id,
                    step_index=step_idx,
                    total_steps=tot_steps,
                    capability=current_step.capability_name,
                    status="failed",
                    error=current_step.error_message,
                    failure_category="dependency_unmet",
                    completed_steps=completed_count,
                    timestamp=time.time(),
                    message=f"Step '{current_step.step_id}' failed: dependencies unmet.",
                )
                return TaskResult(
                    task_id=plan.task_id,
                    success=False,
                    status=TaskStatus.FAILED,
                    message=f"Step '{current_step.step_id}' failed: dependencies unmet.",
                    spoken_response=(
                        f"Task could not proceed: {current_step.description} was blocked."
                    ),
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
                current_step.error_message = (
                    f"Capability '{current_step.capability_name}' not registered."
                )
                plan.status = TaskStatus.FAILED
                self._safe_publish(
                    NovaEvent.TASK_FAILED,
                    task_id=plan.task_id,
                    goal_id=goal_id,
                    step_id=current_step.step_id,
                    step_index=step_idx,
                    total_steps=tot_steps,
                    capability=current_step.capability_name,
                    status="failed",
                    error=current_step.error_message,
                    failure_category="capability_not_found",
                    completed_steps=completed_count,
                    timestamp=time.time(),
                    message=current_step.error_message,
                )
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

            self._safe_publish(
                NovaEvent.TASK_ACTION_STARTED,
                task_id=plan.task_id,
                goal_id=goal_id,
                step_id=current_step.step_id,
                step_index=step_idx,
                total_steps=tot_steps,
                capability=current_step.capability_name,
                description=current_step.description,
                status="executing",
                timestamp=time.time(),
                message=f"Executing {current_step.capability_name}",
            )

            action_start = time.monotonic()
            try:
                exec_result = cap_def.handler(bound_params, ctx)
                step_success = bool(exec_result.get("success", False))
                current_step.result_data = exec_result
            except Exception as exc:
                logger.error("Exception during step '%s': %s", current_step.step_id, exc)
                step_success = False
                exec_result = {"success": False, "error": str(exc)}

            action_elapsed = time.monotonic() - action_start

            self._safe_publish(
                NovaEvent.TASK_ACTION_COMPLETED,
                task_id=plan.task_id,
                goal_id=goal_id,
                step_id=current_step.step_id,
                step_index=step_idx,
                total_steps=tot_steps,
                capability=current_step.capability_name,
                success=step_success,
                status="action_completed" if step_success else "action_failed",
                execution_time_seconds=round(action_elapsed, 4),
                timestamp=time.time(),
                message=(
                    f"Action {current_step.capability_name} "
                    f"{'succeeded' if step_success else 'failed'}"
                ),
            )

            # 6. Step-Level Verification
            if step_success and cap_def.verifier:
                self._safe_publish(
                    NovaEvent.TASK_VERIFICATION_STARTED,
                    task_id=plan.task_id,
                    goal_id=goal_id,
                    step_id=current_step.step_id,
                    step_index=step_idx,
                    total_steps=tot_steps,
                    verification_type=current_step.verification_type or "capability_verifier",
                    status="verifying",
                    timestamp=time.time(),
                    message=f"Verifying step {step_idx}: {current_step.description}",
                )
                try:
                    step_success = cap_def.verifier(bound_params, exec_result, ctx)
                except Exception as ver_exc:
                    logger.error(
                        "Exception during verification of step '%s': %s",
                        current_step.step_id,
                        ver_exc,
                    )
                    step_success = False

                self._safe_publish(
                    NovaEvent.TASK_VERIFICATION_COMPLETED,
                    task_id=plan.task_id,
                    goal_id=goal_id,
                    step_id=current_step.step_id,
                    step_index=step_idx,
                    total_steps=tot_steps,
                    success=step_success,
                    status="verified" if step_success else "verification_failed",
                    timestamp=time.time(),
                    message=(
                        f"Verification passed for {current_step.description}"
                        if step_success
                        else f"Verification failed for {current_step.description}"
                    ),
                )

            # 7. Evaluate Step Outcome & Replanning
            if step_success:
                current_step.status = StepStatus.COMPLETED
                current_step.completed_at = datetime.now(UTC)
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
                    self._safe_publish(
                        NovaEvent.TASK_RECOVERY_STARTED,
                        task_id=plan.task_id,
                        goal_id=goal_id,
                        step_id=current_step.step_id,
                        step_index=step_idx,
                        total_steps=tot_steps,
                        failure_type=fail_type.value,
                        retry_count=current_step.retry_count,
                        max_retries=current_step.max_retries,
                        recovery_action="retry",
                        status="recovering",
                        timestamp=time.time(),
                        message=(
                            f"Retrying step {step_idx} (attempt {current_step.retry_count}):"
                            f" {err_msg}"
                        ),
                    )
                    time.sleep(0.3)
                    step_queue.insert(0, current_step)  # Re-enqueue for retry
                    continue

                # Check Dynamic Replanning
                if replan_cycles < max_replan_cycles:
                    replan_cycles += 1
                    self._safe_publish(
                        NovaEvent.TASK_REPLANNING,
                        task_id=plan.task_id,
                        goal_id=goal_id,
                        step_id=current_step.step_id,
                        step_index=step_idx,
                        total_steps=tot_steps,
                        failure_type=fail_type.value,
                        replan_cycle=replan_cycles,
                        max_replan_cycles=max_replan_cycles,
                        status="replanning",
                        timestamp=time.time(),
                        message=f"Replanning around failed step {step_idx}: {err_msg}",
                    )
                    sub_steps = self.replanner.replan_failed_step(
                        plan, current_step, fail_type, ctx
                    )
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
                self._safe_publish(
                    NovaEvent.TASK_FAILED,
                    task_id=plan.task_id,
                    goal_id=goal_id,
                    step_id=current_step.step_id,
                    step_index=step_idx,
                    total_steps=tot_steps,
                    capability=current_step.capability_name,
                    error=err_msg,
                    failure_category=fail_type.value,
                    status="failed",
                    completed_steps=completed_count,
                    timestamp=time.time(),
                    message=f"Step '{current_step.description}' failed: {err_msg}",
                )
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
        spoken_msg = (
            f"Task completed: {plan.goal.goal_description}"
            if final_ok
            else "Task finished with verification warnings."
        )

        if final_ok:
            self._safe_publish(
                NovaEvent.TASK_COMPLETED,
                task_id=plan.task_id,
                goal_id=goal_id,
                status="completed",
                success=True,
                completed_steps=completed_count,
                total_steps=len(plan.steps),
                progress_percent=100.0,
                final_verification_passed=True,
                timestamp=time.time(),
                message=f"Task completed successfully: {plan.goal.goal_description}",
            )
        else:
            self._safe_publish(
                NovaEvent.TASK_FAILED,
                task_id=plan.task_id,
                goal_id=goal_id,
                status="failed",
                success=False,
                completed_steps=completed_count,
                total_steps=len(plan.steps),
                final_verification_passed=False,
                error="Final goal verification failed.",
                failure_category="goal_verification_failed",
                timestamp=time.time(),
                message="Task finished with verification warnings: final goal checks failed.",
            )

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
        """Resolve dynamic variables and deictic references ('it', 'parent_path')
        using TaskContext.
        """
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
        """Verify that holistic criteria (files/folders created by this plan)
        exist on the system.
        """
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
