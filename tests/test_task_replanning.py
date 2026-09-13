"""Unit tests for DynamicReplanner failure classification and substitution."""

from __future__ import annotations

from pathlib import Path

from core.task_agent.models import FailureType, TaskContext, TaskGoal, TaskPlan, TaskStep
from core.task_agent.replanner import DynamicReplanner


def test_classify_failures() -> None:
    """Test failure classification into FailureType enums."""
    replanner = DynamicReplanner()
    assert replanner.classify_failure("File not found on system") == FailureType.NOT_FOUND
    assert replanner.classify_failure("Permission denied while accessing directory") == FailureType.PERMISSION
    assert replanner.classify_failure("Action cancelled by user") == FailureType.CANCELLED
    assert replanner.classify_failure("Connection timed out") == FailureType.TRANSIENT


def test_replan_visual_fallback(tmp_path: Path) -> None:
    """Test replanning visual search failure into structured browser search."""
    replanner = DynamicReplanner()
    ctx = TaskContext(task_id="t_rep", active_urls=["https://www.flipkart.com"])
    goal = TaskGoal(task_id="t_rep", original_request="Search", goal_description="Search")
    failed_step = TaskStep(
        step_id="step_click",
        description="Click search bar",
        capability_name="visual.click_element",
        parameters={"target_label": "search mobile phones"},
    )
    plan = TaskPlan(plan_id="p_rep", task_id="t_rep", goal=goal, steps=[failed_step])

    new_steps = replanner.replan_failed_step(plan, failed_step, FailureType.NOT_FOUND, ctx)
    assert new_steps is not None
    assert len(new_steps) == 1
    assert new_steps[0].capability_name == "browser.search_web"
