"""Data models and schemas for NOVA Autonomous Task Agent V3."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(str, Enum):
    """Lifecycle states of an autonomous task."""

    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Lifecycle states of an individual task step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    """Safety risk tiers for tasks and individual steps."""

    LOW = "low"          # Safe read/create operations
    MEDIUM = "medium"    # Window closing, navigation, app launch
    HIGH = "high"        # Deleting files, modifying critical configs (requires user confirmation)


class FailureType(str, Enum):
    """Classification of errors encountered during step execution."""

    TRANSIENT = "transient"      # Temporary timeout / app delay -> Retry
    NOT_FOUND = "not_found"      # Missing element / file -> Replan or fallback
    PERMISSION = "permission"    # Protected access / sandbox error -> Report blocker
    AMBIGUOUS = "ambiguous"      # Multiple candidates -> Prompt user
    UNSUPPORTED = "unsupported"  # No registered capability -> Report limitation
    CANCELLED = "cancelled"      # User requested stop -> Abort cleanly


# =============================================================================
# PHASE A: AGENT RUNTIME FOUNDATIONAL CONTRACTS
# =============================================================================


class VerificationStatus(str, Enum):
    """Tri-state outcome of an action or goal verification check."""

    PASS = "pass"
    FAIL = "fail"
    UNCERTAIN = "uncertain"


class RecoveryAction(str, Enum):
    """Actions permissible when handling step execution or verification failures."""

    RETRY_IMMEDIATE = "retry_immediate"
    WAIT_AND_RETRY = "wait_and_retry"
    SUBSTITUTE_CAPABILITY = "substitute_capability"
    REPLAN_SUBGRAPH = "replan_subgraph"
    PROMPT_USER = "prompt_user"
    ABORT = "abort"


@dataclass
class GoalCriteria:
    """A discrete, verifiable condition required for goal satisfaction."""

    criteria_id: str
    description: str
    verifier_type: str = "custom"  # "file_exists", "dir_exists", "url_match", "custom"
    params: dict[str, Any] = field(default_factory=dict)
    required: bool = True
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize criterion to a dictionary."""
        return {
            "criteria_id": self.criteria_id,
            "description": self.description,
            "verifier_type": self.verifier_type,
            "params": dict(self.params),
            "required": self.required,
            "passed": self.passed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalCriteria:
        """Construct GoalCriteria from a dictionary."""
        return cls(
            criteria_id=str(data.get("criteria_id", "")),
            description=str(data.get("description", "")),
            verifier_type=str(data.get("verifier_type", "custom")),
            params=dict(data.get("params", {})),
            required=bool(data.get("required", True)),
            passed=bool(data.get("passed", False)),
        )

    @classmethod
    def from_text(cls, text: str, criteria_id: str = "") -> GoalCriteria:
        """Create a GoalCriteria from a plain text description."""
        cid = criteria_id or f"crit_{uuid.uuid4().hex[:8]}"
        return cls(
            criteria_id=cid,
            description=text,
            verifier_type="custom",
            params={},
            required=True,
            passed=False,
        )


@dataclass
class ExecutionBudget:
    """Enforces bounded execution across time, steps, retries, and replans."""

    max_task_duration_seconds: float = 300.0  # Default 5 minutes
    max_step_duration_seconds: float = 45.0
    max_total_steps: int = 20
    max_retries_per_step: int = 2
    max_replan_cycles: int = 3
    max_provider_latency_seconds: float = 20.0
    created_at: float = field(default_factory=time.time)
    _start_monotonic: float = field(default_factory=time.monotonic, repr=False)

    def __post_init__(self) -> None:
        """Validate bounds to prevent infinite, negative, or degenerate configurations."""
        if self.max_task_duration_seconds <= 0:
            raise ValueError(
                f"max_task_duration_seconds must be positive, got {self.max_task_duration_seconds}"
            )
        if self.max_step_duration_seconds <= 0:
            raise ValueError(
                f"max_step_duration_seconds must be positive, got {self.max_step_duration_seconds}"
            )
        if self.max_total_steps < 1:
            raise ValueError(f"max_total_steps must be at least 1, got {self.max_total_steps}")
        if self.max_retries_per_step < 0:
            raise ValueError(
                f"max_retries_per_step cannot be negative, got {self.max_retries_per_step}"
            )
        if self.max_replan_cycles < 0:
            raise ValueError(
                f"max_replan_cycles cannot be negative, got {self.max_replan_cycles}"
            )
        if self.max_provider_latency_seconds <= 0:
            raise ValueError(
                "max_provider_latency_seconds must be positive, got "
                f"{self.max_provider_latency_seconds}"
            )


    def elapsed_seconds(self) -> float:
        """Compute monotonic elapsed execution time since budget creation."""
        return max(0.0, time.monotonic() - self._start_monotonic)

    def remaining_seconds(self) -> float:
        """Compute remaining task duration seconds."""
        return max(0.0, self.max_task_duration_seconds - self.elapsed_seconds())

    def is_expired(self) -> bool:
        """Check whether the task execution duration has exceeded the budget."""
        return self.elapsed_seconds() >= self.max_task_duration_seconds

    def can_retry(self, current_retries: int) -> bool:
        """Check whether another step retry is permissible under the budget."""
        return current_retries < self.max_retries_per_step and not self.is_expired()

    def can_replan(self, current_replans: int) -> bool:
        """Check whether another replan cycle is permissible under the budget."""
        return current_replans < self.max_replan_cycles and not self.is_expired()

    def can_execute_step(self, total_executed_steps: int) -> bool:
        """Check whether another step can be initiated."""
        return total_executed_steps < self.max_total_steps and not self.is_expired()

    def to_dict(self) -> dict[str, Any]:
        """Serialize budget parameters to dictionary."""
        return {
            "max_task_duration_seconds": self.max_task_duration_seconds,
            "max_step_duration_seconds": self.max_step_duration_seconds,
            "max_total_steps": self.max_total_steps,
            "max_retries_per_step": self.max_retries_per_step,
            "max_replan_cycles": self.max_replan_cycles,
            "max_provider_latency_seconds": self.max_provider_latency_seconds,
            "created_at": self.created_at,
            "elapsed_seconds": self.elapsed_seconds(),
            "remaining_seconds": self.remaining_seconds(),
            "is_expired": self.is_expired(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionBudget:
        """Construct ExecutionBudget from dictionary parameters."""
        return cls(
            max_task_duration_seconds=float(data.get("max_task_duration_seconds", 300.0)),
            max_step_duration_seconds=float(data.get("max_step_duration_seconds", 45.0)),
            max_total_steps=int(data.get("max_total_steps", 20)),
            max_retries_per_step=int(data.get("max_retries_per_step", 2)),
            max_replan_cycles=int(data.get("max_replan_cycles", 3)),
            max_provider_latency_seconds=float(data.get("max_provider_latency_seconds", 20.0)),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class VerificationResult:
    """Rigorous, evidence-based outcome of a step or goal verification check."""

    verification_id: str
    step_id: str
    status: VerificationStatus
    expected_state: str
    actual_state: str
    evidence: str
    recoverable: bool = True
    suggested_recovery: str | None = None
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence boundaries."""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")

    @property
    def is_success(self) -> bool:
        """Convenience property for binary pass check."""
        return self.status == VerificationStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        """Serialize verification result safely without exposing raw visual buffers."""
        return {
            "verification_id": self.verification_id,
            "step_id": self.step_id,
            "status": self.status.value,
            "expected_state": self.expected_state,
            "actual_state": self.actual_state,
            "evidence": self.evidence,
            "recoverable": self.recoverable,
            "suggested_recovery": self.suggested_recovery,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationResult:
        """Construct VerificationResult from dictionary."""
        status_val = data.get("status", VerificationStatus.FAIL.value)
        status = VerificationStatus(status_val) if isinstance(status_val, str) else status_val
        ts_val = data.get("timestamp")
        ts = datetime.fromisoformat(ts_val) if isinstance(ts_val, str) else datetime.now(UTC)
        return cls(
            verification_id=str(data.get("verification_id", "")),
            step_id=str(data.get("step_id", "")),
            status=status,
            expected_state=str(data.get("expected_state", "")),
            actual_state=str(data.get("actual_state", "")),
            evidence=str(data.get("evidence", "")),
            recoverable=bool(data.get("recoverable", True)),
            suggested_recovery=data.get("suggested_recovery"),
            confidence=float(data.get("confidence", 1.0)),
            timestamp=ts,
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def from_eyes_outcome(
        cls,
        outcome: Any,
        step_id: str = "",
        expected_state: str = "",
        actual_state: str = "",
    ) -> VerificationResult:
        """Adapter constructing a VerificationResult from an existing Eyes VerificationOutcome."""
        verified = bool(getattr(outcome, "verified", False))
        status = VerificationStatus.PASS if verified else VerificationStatus.FAIL
        summary = str(getattr(outcome, "summary", ""))
        detail = str(getattr(outcome, "detail", ""))
        should_retry = bool(getattr(outcome, "should_retry", not verified))
        suggested = getattr(outcome, "suggested_recovery", None)

        return cls(
            verification_id=f"ver_{uuid.uuid4().hex[:8]}",
            step_id=step_id,
            status=status,
            expected_state=expected_state or "Expected observable visual or system transition",
            actual_state=actual_state or detail,
            evidence=summary or detail,
            recoverable=should_retry,
            suggested_recovery=suggested,
            confidence=1.0 if verified else 0.8,
        )


@dataclass
class RecoveryDecision:
    """Actionable diagnostic decision produced when an action or verification fails."""

    decision_id: str
    failed_step_id: str
    failure_type: FailureType
    action: RecoveryAction
    reason: str
    replacement_steps: list[TaskStep] = field(default_factory=list)
    retry_count: int = 0
    remaining_recovery_budget: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize recovery decision to dictionary."""
        return {
            "decision_id": self.decision_id,
            "failed_step_id": self.failed_step_id,
            "failure_type": self.failure_type.value,
            "action": self.action.value,
            "reason": self.reason,
            "replacement_steps_count": len(self.replacement_steps),
            "retry_count": self.retry_count,
            "remaining_recovery_budget": self.remaining_recovery_budget,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


@dataclass
class TaskGoal:
    """Represents the high-level desired outcome requested by the user."""

    task_id: str
    original_request: str
    goal_description: str
    success_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    criteria: list[GoalCriteria] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Synchronize string success_criteria and structured GoalCriteria objects."""
        if self.success_criteria and not self.criteria:
            self.criteria = [
                GoalCriteria.from_text(text=sc, criteria_id=f"crit_{idx + 1}")
                for idx, sc in enumerate(self.success_criteria)
            ]
        elif self.criteria and not self.success_criteria:
            self.success_criteria = [c.description for c in self.criteria]

    def add_criteria(self, criterion: GoalCriteria) -> None:
        """Add a structured criterion and synchronize success_criteria strings."""
        self.criteria.append(criterion)
        if criterion.description not in self.success_criteria:
            self.success_criteria.append(criterion.description)


@dataclass
class TaskStep:
    """A discrete, verifiable operation within a structured TaskPlan."""

    step_id: str
    description: str
    capability_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    verification_type: str = "file_exists"  # "file_exists", "dir_exists", "url_match", "custom"
    verification_params: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    status: StepStatus = StepStatus.PENDING
    retry_count: int = 0
    max_retries: int = 2
    result_data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class TaskPlan:
    """An ordered graph of TaskSteps designed to achieve a TaskGoal."""

    plan_id: str
    task_id: str
    goal: TaskGoal
    steps: list[TaskStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: TaskStatus = TaskStatus.PENDING
    current_step_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_step(self, step_id: str) -> TaskStep | None:
        """Find a step by its unique ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def are_dependencies_met(self, step: TaskStep) -> bool:
        """Check if all prerequisite steps have completed successfully."""
        for dep_id in step.depends_on:
            dep_step = self.get_step(dep_id)
            if not dep_step or dep_step.status != StepStatus.COMPLETED:
                return False
        return True


@dataclass
class TaskContext:
    """Dynamic context and entity memory preserved across multi-step execution and turns."""

    task_id: str
    created_folders: dict[str, Path] = field(default_factory=dict)
    created_files: dict[str, Path] = field(default_factory=dict)
    opened_apps: list[str] = field(default_factory=list)
    active_urls: list[str] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    completed_steps: list[str] = field(default_factory=list)
    last_created_folder: Path | None = None
    last_created_file: Path | None = None
    last_opened_target: str | None = None
    last_useful_link: str | None = None

    def register_folder(self, name: str, path: Path) -> None:
        """Record a newly created folder for parameter binding."""
        self.created_folders[name] = path
        self.created_folders[name.lower()] = path
        self.last_created_folder = path
        self.variables["it"] = path
        self.variables["last_folder"] = path

    def register_file(self, name: str, path: Path) -> None:
        """Record a newly created file for parameter binding."""
        self.created_files[name] = path
        self.created_files[name.lower()] = path
        self.last_created_file = path
        self.variables["it"] = path
        self.variables["last_file"] = path

    def register_app(self, app_name: str) -> None:
        """Record an opened application for context binding."""
        if app_name not in self.opened_apps:
            self.opened_apps.append(app_name)
        self.last_opened_target = app_name
        self.variables["last_app"] = app_name
        self.variables["it"] = app_name

    def register_application(self, app_name: str) -> None:
        """Record an opened application for context binding (alias for register_app)."""
        self.register_app(app_name)


@dataclass
class TaskResult:
    """Holistic outcome of an autonomous task execution."""

    task_id: str
    success: bool
    status: TaskStatus
    message: str = ""
    spoken_response: str = ""
    completed_steps: int = 0
    total_steps: int = 0
    failed_step: TaskStep | None = None
    final_verification_passed: bool = False
    context: TaskContext | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
