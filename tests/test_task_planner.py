"""Unit tests for TaskPlanner goal decomposition."""

from __future__ import annotations

from core.task_agent.planner import TaskPlanner


def test_plan_project_with_subfolders() -> None:
    """Validate planning of project folder with subfolders."""
    planner = TaskPlanner()
    plan = planner.plan_goal("Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders")
    assert len(plan.steps) == 4
    assert plan.steps[0].capability_name == "fs.create_folder"
    assert plan.steps[0].parameters["name"] == "DSA Project"
    assert plan.steps[1].parameters["name"] == "Arrays"
    assert plan.steps[2].parameters["name"] == "LinkedList"
    assert plan.steps[3].parameters["name"] == "Trees"
    assert "step_1" in plan.steps[1].depends_on


def test_plan_cpp_project() -> None:
    """Validate planning of C++ project with main.cpp and README.md."""
    planner = TaskPlanner()
    plan = planner.plan_goal("Create a C++ project with main.cpp and README.md")
    assert len(plan.steps) == 3
    assert plan.steps[0].capability_name == "fs.create_folder"
    assert plan.steps[1].capability_name == "fs.create_file"
    assert plan.steps[1].parameters["name"] == "main.cpp"
    assert plan.steps[2].capability_name == "fs.create_file"
    assert plan.steps[2].parameters["name"] == "README.md"


def test_plan_search_and_save_links() -> None:
    """Validate planning of search & save link goal."""
    planner = TaskPlanner()
    plan = planner.plan_goal("Find a Python tutorial and save the useful link in a text file")
    assert len(plan.steps) == 2
    assert plan.steps[0].capability_name == "browser.search_web"
    assert plan.steps[1].capability_name == "fs.create_file"
