"""Unit tests for Task Agent models and context propagation."""

from __future__ import annotations

from pathlib import Path
from core.task_agent.models import (
    StepStatus,
    TaskContext,
    TaskGoal,
    TaskPlan,
    TaskStatus,
    TaskStep,
)


def test_task_plan_dependencies() -> None:
    """Test step dependency resolution in TaskPlan."""
    goal = TaskGoal(
        task_id="t1",
        original_request="Create project",
        goal_description="Create project",
    )
    s1 = TaskStep(step_id="step_1", description="Root folder", capability_name="fs.create_folder")
    s2 = TaskStep(step_id="step_2", description="Subfolder", capability_name="fs.create_folder", depends_on=["step_1"])

    plan = TaskPlan(plan_id="p1", task_id="t1", goal=goal, steps=[s1, s2])

    assert plan.are_dependencies_met(s1) is True
    assert plan.are_dependencies_met(s2) is False

    s1.status = StepStatus.COMPLETED
    assert plan.are_dependencies_met(s2) is True


def test_task_context_folder_binding(tmp_path: Path) -> None:
    """Test TaskContext deictic binding ('it', 'last_folder')."""
    ctx = TaskContext(task_id="t2")
    p = tmp_path / "MyProject"
    ctx.register_folder("MyProject", p)

    assert ctx.last_created_folder == p
    assert ctx.variables["it"] == p
    assert ctx.created_folders["myproject"] == p
