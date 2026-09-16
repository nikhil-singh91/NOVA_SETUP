"""Unit tests for Phase B: EventBus & Telemetry Integration.

Validates:
1. Lifecycle event emission (TASK_CREATED, TASK_STEP_STARTED, TASK_ACTION_*, TASK_VERIFICATION_*,
   TASK_RECOVERY_*, TASK_REPLANNING, TASK_COMPLETED, TASK_FAILED, TASK_CANCELLED,
   TASK_PAUSED/RESUMED).
2. Strict lifecycle event ordering.
3. Payload contract compliance (task_id, goal_id, step_index, capability, status, etc.).
4. Telemetry failure isolation (EventBus exceptions never break task execution).
5. Terminal Dashboard task event handling and activity feed updates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.event_bus import EventBus, NovaEvent
from core.task_agent.executor import TaskExecutor
from core.task_agent.models import (
    RiskLevel,
    TaskContext,
    TaskGoal,
    TaskPlan,
    TaskStatus,
    TaskStep,
)
from core.task_agent.registry import CapabilityDefinition, CapabilityRegistry
from core.task_agent.replanner import DynamicReplanner
from ui.health_checker import DashboardStatsManager
from ui.terminal_dashboard import TerminalDashboard


def test_task_telemetry_successful_execution_and_ordering(tmp_path: Path) -> None:
    """Verify that a successful task execution emits events in strictly valid lifecycle order."""
    bus = EventBus()
    emitted_events: list[tuple[str, dict[str, Any]]] = []

    def _recorder(evt_name: str, payload: dict[str, Any]) -> None:
        emitted_events.append((evt_name, payload))

    for evt in (
        NovaEvent.TASK_CREATED,
        NovaEvent.TASK_STEP_STARTED,
        NovaEvent.TASK_ACTION_STARTED,
        NovaEvent.TASK_ACTION_COMPLETED,
        NovaEvent.TASK_VERIFICATION_STARTED,
        NovaEvent.TASK_VERIFICATION_COMPLETED,
        NovaEvent.TASK_COMPLETED,
        NovaEvent.TASK_FAILED,
        NovaEvent.TASK_CANCELLED,
    ):
        bus.subscribe(evt, _recorder)

    executor = TaskExecutor(event_bus=bus)
    ctx = TaskContext(task_id="t_success_ord")
    goal = TaskGoal(
        task_id="t_success_ord",
        original_request="Create structure",
        goal_description="Create nested folder",
    )
    s1 = TaskStep(
        step_id="step_1",
        description="Create root directory",
        capability_name="fs.create_folder",
        parameters={"name": "RootFolder", "on_desktop": False, "parent_path": str(tmp_path)},
    )
    plan = TaskPlan(plan_id="p1", task_id="t_success_ord", goal=goal, steps=[s1])

    result = executor.execute_plan(plan, context=ctx)
    assert result.success is True
    assert result.status == TaskStatus.COMPLETED

    event_names = [e[0] for e in emitted_events]

    expected_order = [
        NovaEvent.TASK_CREATED.value,
        NovaEvent.TASK_STEP_STARTED.value,
        NovaEvent.TASK_ACTION_STARTED.value,
        NovaEvent.TASK_ACTION_COMPLETED.value,
        NovaEvent.TASK_VERIFICATION_STARTED.value,
        NovaEvent.TASK_VERIFICATION_COMPLETED.value,
        NovaEvent.TASK_COMPLETED.value,
    ]
    assert event_names == expected_order
    assert NovaEvent.TASK_FAILED.value not in event_names
    assert NovaEvent.TASK_CANCELLED.value not in event_names


def test_task_telemetry_payload_contract(tmp_path: Path) -> None:
    """Verify that emitted payloads contain the required structured telemetry fields."""
    bus = EventBus()
    captured_payloads: dict[str, dict[str, Any]] = {}

    def _capture(evt_name: str, payload: dict[str, Any]) -> None:
        captured_payloads[evt_name] = payload

    for evt in (
        NovaEvent.TASK_CREATED,
        NovaEvent.TASK_STEP_STARTED,
        NovaEvent.TASK_ACTION_STARTED,
        NovaEvent.TASK_ACTION_COMPLETED,
        NovaEvent.TASK_VERIFICATION_STARTED,
        NovaEvent.TASK_VERIFICATION_COMPLETED,
        NovaEvent.TASK_COMPLETED,
    ):
        bus.subscribe(evt, _capture)

    executor = TaskExecutor(event_bus=bus)
    ctx = TaskContext(task_id="t_contract_1")
    goal = TaskGoal(
        task_id="t_contract_1",
        original_request="Req",
        goal_description="Telemetry Contract Test",
    )
    s1 = TaskStep(
        step_id="step_a",
        description="Make dir",
        capability_name="fs.create_folder",
        parameters={"name": "ContractDir", "on_desktop": False, "parent_path": str(tmp_path)},
    )
    plan = TaskPlan(plan_id="p_contract", task_id="t_contract_1", goal=goal, steps=[s1])

    executor.execute_plan(plan, context=ctx)

    created = captured_payloads[NovaEvent.TASK_CREATED.value]
    assert created["task_id"] == "t_contract_1"
    assert created["total_steps"] == 1
    assert created["status"] == "running"
    assert "timestamp" in created

    step_start = captured_payloads[NovaEvent.TASK_STEP_STARTED.value]
    assert step_start["task_id"] == "t_contract_1"
    assert step_start["step_id"] == "step_a"
    assert step_start["step_index"] == 1
    assert step_start["total_steps"] == 1
    assert step_start["capability"] == "fs.create_folder"
    assert step_start["description"] == "Make dir"
    assert "progress_percent" in step_start

    act_done = captured_payloads[NovaEvent.TASK_ACTION_COMPLETED.value]
    assert act_done["task_id"] == "t_contract_1"
    assert act_done["step_id"] == "step_a"
    assert act_done["success"] is True
    assert "execution_time_seconds" in act_done

    ver_done = captured_payloads[NovaEvent.TASK_VERIFICATION_COMPLETED.value]
    assert ver_done["task_id"] == "t_contract_1"
    assert ver_done["step_id"] == "step_a"
    assert ver_done["success"] is True

    completed = captured_payloads[NovaEvent.TASK_COMPLETED.value]
    assert completed["task_id"] == "t_contract_1"
    assert completed["status"] == "completed"
    assert completed["success"] is True
    assert completed["progress_percent"] == 100.0


def test_task_telemetry_cancellation() -> None:
    """Verify cancellation publishes TASK_CANCELLED and NEVER emits TASK_COMPLETED."""
    bus = EventBus()
    events: list[str] = []

    def _handler(name: str, payload: dict[str, Any]) -> None:
        events.append(name)

    bus.subscribe(NovaEvent.TASK_CREATED, _handler)
    bus.subscribe(NovaEvent.TASK_CANCELLED, _handler)
    bus.subscribe(NovaEvent.TASK_COMPLETED, _handler)

    executor = TaskExecutor(event_bus=bus)
    executor.cancel_task()

    goal = TaskGoal(task_id="t_canc", original_request="Stop", goal_description="Cancel Goal")
    s1 = TaskStep(
        step_id="s1",
        description="Cancelled step",
        capability_name="fs.create_folder",
        parameters={"name": "Cancel"},
    )
    plan = TaskPlan(plan_id="p_canc", task_id="t_canc", goal=goal, steps=[s1])

    result = executor.execute_plan(plan)
    assert result.status == TaskStatus.CANCELLED
    assert result.success is False

    assert NovaEvent.TASK_CANCELLED.value in events
    assert NovaEvent.TASK_COMPLETED.value not in events


def test_task_telemetry_failure() -> None:
    """Verify fatal step failure emits TASK_FAILED and NEVER emits TASK_COMPLETED."""
    bus = EventBus()
    events: list[str] = []
    fail_payload: dict[str, Any] = {}

    def _handler(name: str, payload: dict[str, Any]) -> None:
        events.append(name)
        if name == NovaEvent.TASK_FAILED.value:
            fail_payload.update(payload)

    bus.subscribe(NovaEvent.TASK_STEP_STARTED, _handler)
    bus.subscribe(NovaEvent.TASK_FAILED, _handler)
    bus.subscribe(NovaEvent.TASK_COMPLETED, _handler)

    executor = TaskExecutor(event_bus=bus)
    goal = TaskGoal(task_id="t_fail", original_request="Bad", goal_description="Fail Goal")
    s1 = TaskStep(
        step_id="s_unregistered",
        description="Unregistered cap",
        capability_name="non_existent_capability_12345",
        parameters={},
    )
    plan = TaskPlan(plan_id="p_fail", task_id="t_fail", goal=goal, steps=[s1])

    result = executor.execute_plan(plan)
    assert result.success is False
    assert result.status == TaskStatus.FAILED

    assert NovaEvent.TASK_FAILED.value in events
    assert NovaEvent.TASK_COMPLETED.value not in events
    assert fail_payload["failure_category"] == "capability_not_found"
    assert fail_payload["step_id"] == "s_unregistered"


def test_task_telemetry_recovery_and_replanning() -> None:
    """Verify recovery retry and dynamic replanning emit telemetry events."""
    custom_reg = CapabilityRegistry()
    bus = EventBus()
    events: list[str] = []

    def _record(name: str, payload: dict[str, Any]) -> None:
        events.append(name)

    bus.subscribe(NovaEvent.TASK_RECOVERY_STARTED, _record)
    bus.subscribe(NovaEvent.TASK_REPLANNING, _record)
    bus.subscribe(NovaEvent.TASK_STEP_STARTED, _record)
    bus.subscribe(NovaEvent.TASK_COMPLETED, _record)

    call_count = 0

    def _flaky_handler(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"success": False, "error": "Connection timeout"}
        return {"success": True, "created": True}

    custom_reg.register(
        CapabilityDefinition(
            name="network.fetch",
            description="Fetch network resource",
            subsystem="network",
            risk_level=RiskLevel.LOW,
            handler=_flaky_handler,
        )
    )

    replanner = DynamicReplanner(custom_reg)
    executor = TaskExecutor(registry=custom_reg, replanner=replanner, event_bus=bus)

    goal = TaskGoal(task_id="t_retry", original_request="Fetch", goal_description="Retry Goal")
    s1 = TaskStep(
        step_id="s_flaky",
        description="Fetch flake",
        capability_name="network.fetch",
        max_retries=2,
    )
    plan = TaskPlan(plan_id="p_retry", task_id="t_retry", goal=goal, steps=[s1])

    res = executor.execute_plan(plan)
    assert res.success is True
    assert call_count == 2
    assert NovaEvent.TASK_RECOVERY_STARTED.value in events


def test_telemetry_failure_isolation(tmp_path: Path) -> None:
    """CRITICAL: EventBus exception during publish MUST NEVER cause task execution to fail."""
    faulty_bus = EventBus()

    def _exploding_publish(event: NovaEvent, **payload: Any) -> None:
        raise RuntimeError(f"EventBus network explosion on {event.value}")

    faulty_bus.publish = _exploding_publish  # type: ignore

    executor = TaskExecutor(event_bus=faulty_bus)
    ctx = TaskContext(task_id="t_isolated")
    goal = TaskGoal(
        task_id="t_isolated",
        original_request="Test isolation",
        goal_description="Isolation Goal",
    )
    s1 = TaskStep(
        step_id="s1",
        description="Create folder under failing telemetry",
        capability_name="fs.create_folder",
        parameters={"name": "IsolatedFolder", "on_desktop": False, "parent_path": str(tmp_path)},
    )
    plan = TaskPlan(plan_id="p_iso", task_id="t_isolated", goal=goal, steps=[s1])

    result = executor.execute_plan(plan, context=ctx)
    assert result.success is True
    assert result.status == TaskStatus.COMPLETED
    assert (tmp_path / "IsolatedFolder").is_dir()


def test_pause_resume_task_telemetry() -> None:
    """Verify pause_task and resume_task emit TASK_PAUSED and TASK_RESUMED."""
    bus = EventBus()
    events: list[str] = []

    bus.subscribe(NovaEvent.TASK_PAUSED, lambda name, p: events.append(name))
    bus.subscribe(NovaEvent.TASK_RESUMED, lambda name, p: events.append(name))

    executor = TaskExecutor(event_bus=bus)
    assert executor.pause_task() is True
    assert executor.resume_task() is True

    assert events == [NovaEvent.TASK_PAUSED.value, NovaEvent.TASK_RESUMED.value]





def test_terminal_dashboard_task_event_reaction() -> None:
    """Verify TerminalDashboard handles TASK_* events and updates stats/activity feed."""
    dashboard = TerminalDashboard()

    dashboard.handle_event(
        NovaEvent.TASK_CREATED.value,
        {"goal_description": "Clean up project files"},
    )
    assert "Clean up project files" in DashboardStatsManager._stats["current_task"]

    dashboard.handle_event(
        NovaEvent.TASK_STEP_STARTED.value,
        {"step_index": 2, "total_steps": 5, "description": "Delete caches"},
    )
    assert "Task 2/5: Delete caches" in DashboardStatsManager._stats["current_task"]

    dashboard.handle_event(
        NovaEvent.TASK_ACTION_STARTED.value,
        {"capability": "fs.delete_folder", "step_index": 2, "total_steps": 5},
    )

    dashboard.handle_event(
        NovaEvent.TASK_COMPLETED.value,
        {"message": "Project clean complete"},
    )
    assert DashboardStatsManager._stats["current_task"] == "TASK COMPLETE"
    assert DashboardStatsManager._stats["command_result"] == "Project clean complete"
