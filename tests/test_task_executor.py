"""Unit tests for TaskExecutor execution and goal verification."""

from __future__ import annotations

from pathlib import Path

from core.task_agent.executor import TaskExecutor
from core.task_agent.models import (
    TaskContext,
    TaskGoal,
    TaskPlan,
    TaskStatus,
    TaskStep,
)


def test_task_executor_folder_project(tmp_path: Path) -> None:
    """Validate sequential step execution with context propagation."""
    executor = TaskExecutor()
    ctx = TaskContext(task_id="t_exec_1")

    goal = TaskGoal(task_id="t_exec_1", original_request="Test Goal", goal_description="Create Project")
    s1 = TaskStep(
        step_id="s1",
        description="Create root",
        capability_name="fs.create_folder",
        parameters={"name": "TestProject", "on_desktop": False, "parent_path": str(tmp_path)},
    )
    s2 = TaskStep(
        step_id="s2",
        description="Create sub",
        capability_name="fs.create_folder",
        parameters={"name": "SubFolder", "on_desktop": False, "parent_path": "it"},
        depends_on=["s1"],
    )

    plan = TaskPlan(plan_id="p1", task_id="t_exec_1", goal=goal, steps=[s1, s2])
    res = executor.execute_plan(plan, context=ctx)

    assert res.success is True
    assert res.status == TaskStatus.COMPLETED
    assert (tmp_path / "TestProject").is_dir()
    assert (tmp_path / "TestProject" / "SubFolder").is_dir()


def test_task_executor_cancellation(tmp_path: Path) -> None:
    """Validate immediate cancellation during task execution."""
    executor = TaskExecutor()
    executor.cancel_task()

    goal = TaskGoal(task_id="t_cancel", original_request="Test", goal_description="Test")
    s1 = TaskStep(
        step_id="s1",
        description="Create root",
        capability_name="fs.create_folder",
        parameters={"name": "NeverCreated", "parent_path": str(tmp_path)},
    )
    plan = TaskPlan(plan_id="p_cancel", task_id="t_cancel", goal=goal, steps=[s1])

    res = executor.execute_plan(plan)
    assert res.success is False
    assert res.status == TaskStatus.CANCELLED
    assert not (tmp_path / "NeverCreated").exists()
