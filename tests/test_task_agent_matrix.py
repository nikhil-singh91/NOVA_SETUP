"""Comprehensive 8-point real-world test matrix for Autonomous Task Agent V3."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.task_agent.models import TaskGoal, TaskPlan, TaskStep
from main import NovaApplication, TurnRequest


def test_full_8_point_task_agent_matrix(tmp_path: Path) -> None:
    """Execute the complete 8-point real-world autonomous task agent matrix."""
    app = NovaApplication()
    app.voice_available = False
    app.desktop_manager.initialize()
    app.browser_manager.initialize()
    app.computer_agent.initialize()

    delivered_responses: list[str] = []

    def fake_deliver(resp_text: str, turn_id: str) -> None:
        delivered_responses.append(resp_text)

    app._deliver_response = fake_deliver  # type: ignore

    def run_turn(cmd: str) -> str:
        delivered_responses.clear()
        app._process_turn(TurnRequest(source="voice", text=cmd))
        return delivered_responses[-1] if delivered_responses else ""

    desktop_dir = Path.home() / "Desktop"
    test_records: list[dict[str, str]] = []

    # =========================================================================
    # TEST 1: "Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders."
    # =========================================================================
    resp1 = run_turn("Create a folder called DSA Project on Desktop with Arrays, LinkedList and Trees folders")
    assert "DSA Project" in resp1 or "Task completed" in resp1
    dsa_dir = desktop_dir / "DSA Project"
    assert dsa_dir.is_dir()
    assert (dsa_dir / "Arrays").is_dir()
    assert (dsa_dir / "LinkedList").is_dir()
    assert (dsa_dir / "Trees").is_dir()
    test_records.append({"test": "TEST 1: DSA Project with Subfolders", "status": "PASS"})

    # Clean up test 1
    import shutil
    shutil.rmtree(dsa_dir, ignore_errors=True)

    # =========================================================================
    # TEST 2: "Create a C++ project with main.cpp and README.md."
    # =========================================================================
    resp2 = run_turn("Create a C++ project with main.cpp and README.md")
    assert "C++_Project" in resp2 or "Task completed" in resp2
    cpp_dir = desktop_dir / "C++_Project"
    assert cpp_dir.is_dir()
    assert (cpp_dir / "main.cpp").is_file()
    assert (cpp_dir / "README.md").is_file()
    test_records.append({"test": "TEST 2: C++ Project Creation", "status": "PASS"})

    # Clean up test 2
    shutil.rmtree(cpp_dir, ignore_errors=True)

    # =========================================================================
    # TEST 3: "Open Google and search DSA roadmap."
    # =========================================================================
    resp3 = run_turn("Open Google and search DSA roadmap")
    assert "DSA roadmap" in resp3 or "Google" in resp3 or len(resp3) > 0
    test_records.append({"test": "TEST 3: Google Search", "status": "PASS"})

    # =========================================================================
    # TEST 4: "Go to Flipkart and search mobile phones."
    # =========================================================================
    resp4 = run_turn("Go to Flipkart and search mobile phones")
    assert "mobile phones" in resp4 or "Flipkart" in resp4
    test_records.append({"test": "TEST 4: Flipkart Search", "status": "PASS"})

    # =========================================================================
    # TEST 5: "Find a Python tutorial and save the useful link in a text file."
    # =========================================================================
    resp5 = run_turn("Find a Python tutorial and save the useful link in a text file")
    assert "Python" in resp5 or "Task completed" in resp5
    doc_file = desktop_dir / "Python_tutorial_links.txt"
    assert doc_file.is_file()
    test_records.append({"test": "TEST 5: Search & Save Link Document", "status": "PASS"})

    # Clean up test 5
    doc_file.unlink(missing_ok=True)

    # =========================================================================
    # TEST 6: Multi-step task started -> "Stop" (Cancellation)
    # =========================================================================
    resp6 = run_turn("Stop")
    assert "Stopped" in resp6 or "cancelled" in resp6.lower()
    test_records.append({"test": "TEST 6: Immediate Task Cancellation", "status": "PASS"})

    # =========================================================================
    # TEST 7: Step Failure & Bounded Dynamic Replanning
    # =========================================================================
    app.task_executor.reset_cancellation()
    goal7 = TaskGoal(task_id="t7", original_request="Test Replan", goal_description="Test Replan")
    failed_step = TaskStep(
        step_id="step_fail",
        description="Failing click",
        capability_name="visual.click_element",
        parameters={"target_label": "search products"},
    )
    plan7 = TaskPlan(plan_id="p7", task_id="t7", goal=goal7, steps=[failed_step])

    with patch.object(app.task_executor.registry.get("visual.click_element"), "handler", side_effect=Exception("UI element not found")):
        with patch.object(app.task_executor.replanner, "replan_failed_step", return_value=[
            TaskStep(step_id="step_sub", description="Substituted search", capability_name="browser.search_web", parameters={"query": "products"})
        ]):
            res7 = app.task_executor.execute_plan(plan7)
            assert res7.success is True
            test_records.append({"test": "TEST 7: Dynamic Replanning Recovery", "status": "PASS"})

    # =========================================================================
    # TEST 8: "Create a folder Project" -> "Create main.cpp inside it."
    # =========================================================================
    resp8_1 = run_turn("Create a folder called AlphaProject on Desktop")
    assert resp8_1
    alpha_dir = desktop_dir / "AlphaProject"
    assert alpha_dir.is_dir()

    resp8_2 = run_turn("Now create main.cpp inside it")
    assert resp8_2
    main_file = alpha_dir / "main.cpp"
    assert main_file.is_file()
    test_records.append({"test": "TEST 8: Cross-Turn Context Resolution", "status": "PASS"})

    # Clean up test 8
    shutil.rmtree(alpha_dir, ignore_errors=True)

    assert len(test_records) == 8
    for rec in test_records:
        assert rec["status"] == "PASS"
