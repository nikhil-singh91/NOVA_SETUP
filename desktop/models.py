"""Data models, enums, task plans, and execution results for NOVA Desktop Actions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DesktopActionType(str, Enum):
    """Canonical desktop interaction intent types."""

    # Application Actions
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    SWITCH_APP = "switch_app"

    # File & Directory Operations
    CREATE_FOLDER = "create_folder"
    OPEN_FOLDER = "open_folder"
    FIND_ITEM = "find_item"
    OPEN_FILE = "open_file"
    RENAME_ITEM = "rename_item"
    DELETE_ITEM = "delete_item"
    CREATE_FILES = "create_files"
    CREATE_PROJECT_TREE = "create_project_tree"

    # Code & Project Creation
    CREATE_CODE_PROJECT = "create_code_project"
    WRITE_CODE_FILE = "write_code_file"
    OPEN_VS_CODE = "open_vs_code"

    # Document & Text Writing
    WRITE_DOCUMENT = "write_document"

    # Camera & Vision
    OPEN_CAMERA = "open_camera"
    TAKE_PHOTO = "take_photo"

    # Task & Lifecycle Management
    STOP_DESKTOP_TASK = "stop_desktop_task"


class DesktopStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DesktopActionPlan(BaseModel):
    """Structured plan for a single desktop action."""

    action_type: DesktopActionType
    target_name: str = ""
    target_path: str = ""
    app_name: str = ""
    file_names: list[str] = Field(default_factory=list)
    subfolders: list[str] = Field(default_factory=list)
    content_topic: str = ""
    content_text: str = ""
    code_language: str = ""
    raw_prompt: str = ""
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DesktopResult(BaseModel):
    """Result of a desktop action execution."""

    success: bool
    action_type: DesktopActionType
    message: str = ""
    spoken_response: str = ""
    target_path: str = ""
    error: str | None = None
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DesktopStep:
    """Individual step within a multi-step desktop task."""

    step_id: int
    name: str
    action_type: DesktopActionType
    parameters: dict[str, Any] = field(default_factory=dict)
    status: DesktopStepStatus = DesktopStepStatus.PENDING
    result_message: str = ""
    output_path: str | None = None


@dataclass
class DesktopTaskPlan:
    """Bounded, multi-step desktop automation plan."""

    task_id: str = field(default_factory=lambda: f"dtk_{uuid.uuid4().hex[:8]}")
    goal: str = ""
    steps: list[DesktopStep] = field(default_factory=list)
    max_steps: int = 10
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
