"""Data models and schemas for NOVA Autonomous Task Agent V3."""

from __future__ import annotations

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


@dataclass
class TaskStep:
    """A discrete, verifiable operation within a structured TaskPlan."""

    step_id: str
    description: str
    capability_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    verification_type: str = "file_exists"  # "file_exists", "dir_exists", "url_match", "process_running", "visual_diff", "custom"
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
