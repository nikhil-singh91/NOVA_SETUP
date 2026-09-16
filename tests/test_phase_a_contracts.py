"""Unit tests for NOVA 4.0 Phase A: Foundational Contracts and Models.

Verifies:
- GoalCriteria (creation, defaults, serialization, TaskGoal backwards-compatibility)
- ExecutionBudget (bounds validation, monotonic elapsed/remaining calculations, expiration)
- VerificationResult (tri-state status, confidence boundaries, serialization, Eyes adapter)
- RecoveryDecision (FailureType, RecoveryAction, replacement step handling)
- AgentRuntimeError exception hierarchy (inheritance, chaining, dual inheritance)
- NovaEvent enum extensions and EventBus integration
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import pytest
from core.event_bus import EventBus, NovaEvent
from core.exceptions import (
    ActionExecutionError,
    AgentRuntimeError,
    AmbiguousGoalError,
    CapabilityUnavailableError,
    DependencyMissingError,
    NovaError,
    ObservationTimeoutError,
    PermissionDeniedError,
    PermissionRequiredError,
    PolicyViolationError,
    TaskBudgetExceededError,
    VerificationFailedError,
)
from core.task_agent.models import (
    ExecutionBudget,
    FailureType,
    GoalCriteria,
    RecoveryAction,
    RecoveryDecision,
    TaskGoal,
    TaskStep,
    VerificationResult,
    VerificationStatus,
)

# =============================================================================
# A. GOAL CRITERIA CONTRACT TESTS
# =============================================================================


def test_goal_criteria_construction_and_defaults() -> None:
    """Verify GoalCriteria can be constructed with explicit and default values."""
    criterion = GoalCriteria(
        criteria_id="crit_1",
        description="File exists on Desktop",
    )
    assert criterion.criteria_id == "crit_1"
    assert criterion.description == "File exists on Desktop"
    assert criterion.verifier_type == "custom"
    assert criterion.params == {}
    assert criterion.required is True
    assert criterion.passed is False


def test_goal_criteria_serialization() -> None:
    """Verify to_dict and from_dict roundtrip preserves all criterion attributes."""
    original = GoalCriteria(
        criteria_id="crit_search_1",
        description="URL matches Google search results",
        verifier_type="url_match",
        params={"pattern": "google.com/search"},
        required=False,
        passed=True,
    )
    serialized = original.to_dict()
    assert serialized["criteria_id"] == "crit_search_1"
    assert serialized["verifier_type"] == "url_match"
    assert serialized["params"]["pattern"] == "google.com/search"
    assert serialized["required"] is False
    assert serialized["passed"] is True

    reconstituted = GoalCriteria.from_dict(serialized)
    assert reconstituted.criteria_id == original.criteria_id
    assert reconstituted.description == original.description
    assert reconstituted.verifier_type == original.verifier_type
    assert reconstituted.params == original.params
    assert reconstituted.required is False
    assert reconstituted.passed is True


def test_goal_criteria_from_text() -> None:
    """Verify GoalCriteria.from_text creates structured criteria from string."""
    criterion = GoalCriteria.from_text("Folder exists", criteria_id="crit_root")
    assert criterion.criteria_id == "crit_root"
    assert criterion.description == "Folder exists"
    assert criterion.required is True
    assert criterion.passed is False


def test_task_goal_backwards_compatibility_and_criteria_sync() -> None:
    """Verify TaskGoal string success_criteria automatically syncs with criteria objects."""
    # Test 1: legacy construction using string success_criteria
    legacy_goal = TaskGoal(
        task_id="t_legacy",
        original_request="Create project folder",
        goal_description="Create project folder",
        success_criteria=["Folder 'Project' exists", "main.py exists"],
    )
    assert len(legacy_goal.success_criteria) == 2
    assert len(legacy_goal.criteria) == 2
    assert legacy_goal.criteria[0].description == "Folder 'Project' exists"
    assert legacy_goal.criteria[1].description == "main.py exists"

    # Test 2: structured addition via add_criteria
    new_criterion = GoalCriteria(
        criteria_id="crit_readme",
        description="README.md exists",
        verifier_type="file_exists",
    )
    legacy_goal.add_criteria(new_criterion)
    assert len(legacy_goal.criteria) == 3
    assert "README.md exists" in legacy_goal.success_criteria


# =============================================================================
# B. EXECUTION BUDGET CONTRACT TESTS
# =============================================================================


def test_execution_budget_defaults() -> None:
    """Verify ExecutionBudget initializes with sensible, finite positive bounds."""
    budget = ExecutionBudget()
    assert budget.max_task_duration_seconds == 300.0
    assert budget.max_step_duration_seconds == 45.0
    assert budget.max_total_steps == 20
    assert budget.max_retries_per_step == 2
    assert budget.max_replan_cycles == 3
    assert budget.max_provider_latency_seconds == 20.0
    assert budget.is_expired() is False
    assert budget.remaining_seconds() > 290.0
    assert budget.can_retry(1) is True
    assert budget.can_retry(2) is False
    assert budget.can_replan(2) is True
    assert budget.can_replan(3) is False
    assert budget.can_execute_step(19) is True
    assert budget.can_execute_step(20) is False


def test_execution_budget_validation() -> None:
    """Verify ExecutionBudget rejects non-positive or negative limits."""
    with pytest.raises(ValueError, match="max_task_duration_seconds must be positive"):
        ExecutionBudget(max_task_duration_seconds=0.0)

    with pytest.raises(ValueError, match="max_task_duration_seconds must be positive"):
        ExecutionBudget(max_task_duration_seconds=-10.0)

    with pytest.raises(ValueError, match="max_step_duration_seconds must be positive"):
        ExecutionBudget(max_step_duration_seconds=0.0)

    with pytest.raises(ValueError, match="max_total_steps must be at least 1"):
        ExecutionBudget(max_total_steps=0)

    with pytest.raises(ValueError, match="max_retries_per_step cannot be negative"):
        ExecutionBudget(max_retries_per_step=-1)

    with pytest.raises(ValueError, match="max_replan_cycles cannot be negative"):
        ExecutionBudget(max_replan_cycles=-1)

    with pytest.raises(ValueError, match="max_provider_latency_seconds must be positive"):
        ExecutionBudget(max_provider_latency_seconds=-5.0)


def test_execution_budget_expiration_monotonic() -> None:
    """Verify budget expiration triggers accurately when elapsed time exceeds limit."""
    short_budget = ExecutionBudget(max_task_duration_seconds=0.05)
    assert short_budget.is_expired() is False
    time.sleep(0.06)
    assert short_budget.is_expired() is True
    assert short_budget.remaining_seconds() == 0.0
    assert short_budget.can_execute_step(0) is False
    assert short_budget.can_retry(0) is False
    assert short_budget.can_replan(0) is False


def test_execution_budget_serialization() -> None:
    """Verify ExecutionBudget serializes to and from dict accurately."""
    budget = ExecutionBudget(
        max_task_duration_seconds=120.0,
        max_total_steps=10,
        max_retries_per_step=1,
    )
    serialized = budget.to_dict()
    assert serialized["max_task_duration_seconds"] == 120.0
    assert serialized["max_total_steps"] == 10
    assert serialized["max_retries_per_step"] == 1
    assert "elapsed_seconds" in serialized
    assert "remaining_seconds" in serialized

    reconstituted = ExecutionBudget.from_dict(serialized)
    assert reconstituted.max_task_duration_seconds == 120.0
    assert reconstituted.max_total_steps == 10
    assert reconstituted.max_retries_per_step == 1


# =============================================================================
# C. VERIFICATION RESULT CONTRACT TESTS
# =============================================================================


def test_verification_result_pass() -> None:
    """Verify VerificationResult with PASS status."""
    result = VerificationResult(
        verification_id="ver_01",
        step_id="step_1",
        status=VerificationStatus.PASS,
        expected_state="Folder 'Project' exists on Desktop",
        actual_state="Path ~/Desktop/Project is a directory",
        evidence="Directory verified via Path.is_dir()",
        confidence=1.0,
    )
    assert result.status == VerificationStatus.PASS
    assert result.is_success is True
    assert result.confidence == 1.0


def test_verification_result_fail() -> None:
    """Verify VerificationResult with FAIL status."""
    result = VerificationResult(
        verification_id="ver_02",
        step_id="step_2",
        status=VerificationStatus.FAIL,
        expected_state="Button 'Submit' clicked",
        actual_state="Active screen unchanged, modal still visible",
        evidence="Visual hash identical after click",
        recoverable=True,
        suggested_recovery="Retry click with fallback search",
        confidence=0.85,
    )
    assert result.status == VerificationStatus.FAIL
    assert result.is_success is False
    assert result.recoverable is True
    assert result.suggested_recovery == "Retry click with fallback search"


def test_verification_result_uncertain() -> None:
    """Verify VerificationResult with UNCERTAIN status."""
    result = VerificationResult(
        verification_id="ver_03",
        step_id="step_3",
        status=VerificationStatus.UNCERTAIN,
        expected_state="Browser navigated to checkout",
        actual_state="Page loading spinner active",
        evidence="Network pending",
        recoverable=True,
        confidence=0.5,
    )
    assert result.status == VerificationStatus.UNCERTAIN
    assert result.is_success is False


def test_verification_result_confidence_bounds() -> None:
    """Verify confidence must be strictly within [0.0, 1.0]."""
    with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
        VerificationResult(
            verification_id="ver_err",
            step_id="step_1",
            status=VerificationStatus.PASS,
            expected_state="",
            actual_state="",
            evidence="",
            confidence=-0.1,
        )

    with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
        VerificationResult(
            verification_id="ver_err2",
            step_id="step_1",
            status=VerificationStatus.PASS,
            expected_state="",
            actual_state="",
            evidence="",
            confidence=1.5,
        )


def test_verification_result_from_eyes_outcome_adapter() -> None:
    """Verify from_eyes_outcome converts Eyes VerificationOutcome into VerificationResult."""
    @dataclass
    class FakeEyesOutcome:
        verified: bool
        summary: str
        detail: str
        should_retry: bool = False
        suggested_recovery: str | None = None

    outcome_pass = FakeEyesOutcome(
        verified=True,
        summary="Clicked 'Submit' button",
        detail="Window modal closed",
    )
    res_pass = VerificationResult.from_eyes_outcome(outcome_pass, step_id="step_click")
    assert res_pass.is_success is True
    assert res_pass.status == VerificationStatus.PASS
    assert res_pass.evidence == "Clicked 'Submit' button"

    outcome_fail = FakeEyesOutcome(
        verified=False,
        summary="No visual delta detected",
        detail="Target element did not respond",
        should_retry=True,
        suggested_recovery="Scroll down and click again",
    )
    res_fail = VerificationResult.from_eyes_outcome(outcome_fail, step_id="step_click")
    assert res_fail.is_success is False
    assert res_fail.status == VerificationStatus.FAIL
    assert res_fail.recoverable is True
    assert res_fail.suggested_recovery == "Scroll down and click again"


def test_verification_result_serialization() -> None:
    """Verify VerificationResult serializes cleanly to and from dict without leaking buffers."""
    original = VerificationResult(
        verification_id="ver_serial",
        step_id="step_10",
        status=VerificationStatus.PASS,
        expected_state="Process active",
        actual_state="PID 1234 running",
        evidence="pgrep exit code 0",
        confidence=0.95,
    )
    data = original.to_dict()
    assert data["status"] == "pass"
    assert data["confidence"] == 0.95

    restored = VerificationResult.from_dict(data)
    assert restored.verification_id == original.verification_id
    assert restored.status == VerificationStatus.PASS
    assert restored.confidence == 0.95


# =============================================================================
# D. RECOVERY DECISION CONTRACT TESTS
# =============================================================================


def test_recovery_decision_construction() -> None:
    """Verify RecoveryDecision accurately captures diagnostics and replacement steps."""
    sub_step = TaskStep(
        step_id="step_fallback_1",
        description="Fallback search in browser",
        capability_name="browser.search_web",
        parameters={"query": "mobile phones"},
    )
    decision = RecoveryDecision(
        decision_id="rec_01",
        failed_step_id="step_click",
        failure_type=FailureType.NOT_FOUND,
        action=RecoveryAction.SUBSTITUTE_CAPABILITY,
        reason="Element not found on screen after 2 retries",
        replacement_steps=[sub_step],
        retry_count=2,
        remaining_recovery_budget=2,
    )
    assert decision.decision_id == "rec_01"
    assert decision.failure_type == FailureType.NOT_FOUND
    assert decision.action == RecoveryAction.SUBSTITUTE_CAPABILITY
    assert len(decision.replacement_steps) == 1
    assert decision.replacement_steps[0].capability_name == "browser.search_web"
    assert decision.retry_count == 2
    assert decision.remaining_recovery_budget == 2

    data = decision.to_dict()
    assert data["decision_id"] == "rec_01"
    assert data["action"] == "substitute_capability"
    assert data["replacement_steps_count"] == 1


# =============================================================================
# E. AGENT RUNTIME EXCEPTION HIERARCHY TESTS
# =============================================================================


def test_agent_runtime_error_hierarchy() -> None:
    """Verify all new exceptions correctly inherit from AgentRuntimeError and NovaError."""
    # 1. Base AgentRuntimeError
    base_err = AgentRuntimeError("Agent failure")
    assert isinstance(base_err, NovaError)
    assert str(base_err) == "Agent failure"

    # 2. CapabilityUnavailableError
    cap_err = CapabilityUnavailableError("fs.format_disk not available")
    assert isinstance(cap_err, AgentRuntimeError)
    assert isinstance(cap_err, NovaError)

    # 3. PermissionRequiredError (Dual inheritance with PermissionDeniedError)
    perm_err = PermissionRequiredError("Screen recording denied")
    assert isinstance(perm_err, AgentRuntimeError)
    assert isinstance(perm_err, PermissionDeniedError)
    assert isinstance(perm_err, NovaError)

    # 4. DependencyMissingError
    dep_err = DependencyMissingError("ffmpeg is not installed")
    assert isinstance(dep_err, AgentRuntimeError)
    assert isinstance(dep_err, NovaError)

    # 5. ActionExecutionError
    act_err = ActionExecutionError("Handler crashed")
    assert isinstance(act_err, AgentRuntimeError)

    # 6. VerificationFailedError
    ver_err = VerificationFailedError("Expected file not found")
    assert isinstance(ver_err, AgentRuntimeError)

    # 7. ObservationTimeoutError
    obs_err = ObservationTimeoutError("Screen capture timed out")
    assert isinstance(obs_err, AgentRuntimeError)

    # 8. PolicyViolationError
    pol_err = PolicyViolationError("Attempted deletion in /System")
    assert isinstance(pol_err, AgentRuntimeError)

    # 9. TaskBudgetExceededError
    bud_err = TaskBudgetExceededError("Task duration exceeded 300s")
    assert isinstance(bud_err, AgentRuntimeError)

    # 10. AmbiguousGoalError
    amb_err = AmbiguousGoalError("Found multiple folders matching 'Project'")
    assert isinstance(amb_err, AgentRuntimeError)


def test_exception_chaining_preserves_cause() -> None:
    """Verify original exception context is cleanly preserved."""
    root_cause = FileNotFoundError("Missing file")
    try:
        raise ActionExecutionError(
            "Step execution failed", original_exception=root_cause
        ) from root_cause
    except ActionExecutionError as exc:
        assert exc.original_exception is root_cause
        assert exc.__cause__ is root_cause


# =============================================================================
# F. EVENTBUS EXTENSIONS TESTS
# =============================================================================


def test_nova_event_task_lifecycle_members() -> None:
    """Verify all 17 new task lifecycle event members are registered on NovaEvent."""
    expected_task_events = [
        "TASK_CREATED",
        "TASK_UNDERSTANDING",
        "TASK_PLANNING",
        "TASK_OBSERVING",
        "TASK_STEP_STARTED",
        "TASK_ACTION_STARTED",
        "TASK_ACTION_COMPLETED",
        "TASK_VERIFICATION_STARTED",
        "TASK_VERIFICATION_COMPLETED",
        "TASK_RECOVERY_STARTED",
        "TASK_REPLANNING",
        "TASK_WAITING_USER",
        "TASK_PAUSED",
        "TASK_RESUMED",
        "TASK_COMPLETED",
        "TASK_FAILED",
        "TASK_CANCELLED",
    ]
    for name in expected_task_events:
        assert hasattr(NovaEvent, name), f"NovaEvent is missing member: {name}"
        member = getattr(NovaEvent, name)
        assert member.value == name.lower()


def test_existing_nova_events_unmodified() -> None:
    """Verify legacy NovaEvent members remain unchanged."""
    assert NovaEvent.APPLICATION_STARTED.value == "application_started"
    assert NovaEvent.APPLICATION_SHUTDOWN.value == "application_shutdown"
    assert NovaEvent.BROWSER_ACTION_STARTED.value == "browser_action_started"
    assert NovaEvent.DESKTOP_ACTION_STARTED.value == "desktop_action_started"


def test_event_bus_publish_subscribe_task_events() -> None:
    """Verify EventBus can subscribe to and publish task lifecycle events."""
    bus = EventBus()
    received_events: list[tuple[str, dict]] = []

    def on_task_created(event: str, payload: dict) -> None:
        received_events.append((event, payload))

    bus.subscribe(NovaEvent.TASK_CREATED, on_task_created)
    bus.publish(NovaEvent.TASK_CREATED, task_id="task_test_01", goal="Scaffold app")

    assert len(received_events) == 1
    assert received_events[0][0] == "task_created"
    assert received_events[0][1]["task_id"] == "task_test_01"
    assert received_events[0][1]["goal"] == "Scaffold app"
