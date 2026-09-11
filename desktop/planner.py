"""Multi-step bounded desktop action planner with cancellation and step execution."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from core.event_bus import NovaEvent
from core.logger import get_logger
from core.registry import registry
from desktop.apps import AppLauncher
from desktop.files import FileSystemManager
from desktop.models import (
    DesktopActionType,
    DesktopResult,
    DesktopStep,
    DesktopStepStatus,
    DesktopTaskPlan,
)
from desktop.safety import DesktopSafetyPolicy

logger = get_logger(__name__)


class DesktopTaskPlanner:
    """Orchestrates bounded multi-step desktop plans with lifecycle cancellation."""

    def __init__(self) -> None:
        self._active_plan: DesktopTaskPlan | None = None

    def _publish_event(self, event: NovaEvent, **payload: Any) -> None:
        try:
            if registry.exists("event_bus"):
                bus = registry.get("event_bus")
                bus.publish(event, **payload)
        except Exception as exc:
            logger.debug("Failed to publish event %s: %s", event.value, exc)

    def execute_plan(
        self,
        task_plan: DesktopTaskPlan,
        stop_event: threading.Event | None = None,
    ) -> DesktopResult:
        """Execute each step in the plan in sequence, respecting stop signals and boundaries."""
        self._active_plan = task_plan
        self._publish_event(NovaEvent.DESKTOP_ACTION_STARTED, task_id=task_plan.task_id, goal=task_plan.goal)
        logger.info("Executing DesktopTaskPlan [%s]: '%s' (%d steps)", task_plan.task_id, task_plan.goal, len(task_plan.steps))

        executed_steps = 0
        last_output_path: str = ""

        from ui.health_checker import DashboardStatsManager

        total_steps = len(task_plan.steps)
        step_descriptions = [s.name for s in task_plan.steps]
        DashboardStatsManager.record_understood("Multi-step task", details={"Steps": step_descriptions})

        for step in task_plan.steps:
            if stop_event and stop_event.is_set():
                logger.info("DesktopTaskPlan [%s] stopped by user request.", task_plan.task_id)
                self._publish_event(NovaEvent.DESKTOP_ACTION_CANCELLED, task_id=task_plan.task_id)
                DashboardStatsManager.record_result("Desktop task was cancelled.", success=False)
                return DesktopResult(
                    success=True,
                    action_type=DesktopActionType.STOP_DESKTOP_TASK,
                    message="Desktop task was cancelled.",
                    spoken_response="I've cancelled the desktop task.",
                )

            if executed_steps >= task_plan.max_steps:
                logger.warning("DesktopTaskPlan [%s] reached maximum bounded steps (%d).", task_plan.task_id, task_plan.max_steps)
                break

            step.status = DesktopStepStatus.RUNNING
            logger.info("Running DesktopStep %d: '%s' (%s)", step.step_id, step.name, step.action_type.value)
            DashboardStatsManager.record_action(step.name, step_num=step.step_id, total_steps=total_steps)

            try:
                # 1. Create Folder
                if step.action_type == DesktopActionType.CREATE_FOLDER:
                    folder_name = step.parameters.get("folder_name", "")
                    parent_p = Path(step.parameters["parent_dir"]) if "parent_dir" in step.parameters and step.parameters["parent_dir"] else None
                    loc = step.parameters.get("location")
                    on_desk = step.parameters.get("on_desktop", False)
                    success, path, msg = FileSystemManager.create_folder(folder_name, parent=parent_p, location=loc, on_desktop=on_desk)
                    step.status = DesktopStepStatus.COMPLETED if success else DesktopStepStatus.FAILED
                    step.result_message = msg
                    step.output_path = str(path)
                    last_output_path = str(path)
                    if success:
                        DashboardStatsManager.record_result(f"✓ Folder created: {path}", success=True)
                    else:
                        DashboardStatsManager.record_result(f"✗ Could not create folder: {msg}", success=False)

                # 2. Create Files
                elif step.action_type == DesktopActionType.CREATE_FILES:
                    file_names = step.parameters.get("file_names", [])
                    loc = step.parameters.get("location")
                    parent_p = Path(last_output_path) if (last_output_path and Path(last_output_path).is_dir()) else (Path(step.parameters["parent_dir"]) if "parent_dir" in step.parameters and step.parameters["parent_dir"] else None)
                    content_map = step.parameters.get("content_map", {})
                    success, paths, msg = FileSystemManager.create_files(file_names, parent=parent_p, location=loc, content_map=content_map)
                    step.status = DesktopStepStatus.COMPLETED if success else DesktopStepStatus.FAILED
                    step.result_message = msg
                    if paths:
                        last_output_path = str(paths[0])
                    if success:
                        DashboardStatsManager.record_result(f"✓ File created: {', '.join(str(p) for p in paths)}", success=True)
                    else:
                        DashboardStatsManager.record_result(f"✗ Could not create file: {msg}", success=False)

                # 3. Open Application / Project
                elif step.action_type in (DesktopActionType.OPEN_APP, DesktopActionType.OPEN_VS_CODE):
                    app = step.parameters.get("app_name", "Visual Studio Code")
                    target = step.parameters.get("target_path", last_output_path)
                    if target and not Path(target).is_absolute() and last_output_path:
                        target = last_output_path
                    success, msg, spoken = AppLauncher.launch(app, target_path=target)
                    step.status = DesktopStepStatus.COMPLETED if success else DesktopStepStatus.FAILED
                    step.result_message = msg
                    if success:
                        DashboardStatsManager.record_result(f"✓ {app} opened", success=True)
                    else:
                        DashboardStatsManager.record_result(f"✗ Could not open {app}: {msg}", success=False)

                executed_steps += 1

            except Exception as exc:
                logger.error("Error executing step %d ('%s'): %s", step.step_id, step.name, exc)
                step.status = DesktopStepStatus.FAILED
                step.result_message = str(exc)
                self._publish_event(NovaEvent.DESKTOP_ACTION_FAILED, task_id=task_plan.task_id, error=str(exc))
                DashboardStatsManager.record_result(f"✗ Step '{step.name}' failed: {exc}", success=False)
                return DesktopResult(
                    success=False,
                    action_type=step.action_type,
                    error=f"Step '{step.name}' failed: {exc}",
                    spoken_response=f"Failed during {step.name}.",
                )

        self._publish_event(NovaEvent.DESKTOP_ACTION_COMPLETED, task_id=task_plan.task_id, goal=task_plan.goal)
        spoken_summary = f"Completed desktop task: {task_plan.goal}."
        DashboardStatsManager.record_result(f"✓ {executed_steps}/{total_steps} steps completed", success=True)
        return DesktopResult(
            success=True,
            action_type=DesktopActionType.CREATE_CODE_PROJECT,
            message=f"Completed {executed_steps} step(s) for '{task_plan.goal}'.",
            spoken_response=spoken_summary,
            target_path=last_output_path,
        )
