"""Subsystem models, enums, and structured execution data representations."""

from __future__ import annotations

from dataclasses import dataclass, field, InitVar
from enum import Enum
from typing import Any

class CommandCategory(str, Enum):
    VOLUME = "Volume"
    BRIGHTNESS = "Brightness"
    APPLICATIONS = "Applications"
    BROWSER = "Browser"
    MEDIA = "Media"
    FINDER = "Finder"
    SCREENSHOT = "Screenshot"
    CLIPBOARD = "Clipboard"
    NETWORK = "Network"
    SYSTEM = "System"
    UNKNOWN = "Unknown"

class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CANCELLED = "CANCELLED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"

@dataclass
class MacCommand:
    """Represents a validated, parsed macOS command ready for execution."""
    category: CommandCategory
    action: str  # e.g., "increase", "decrease", "set", "open", "mute"
    raw_input: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    is_dangerous: bool = False
    raw_text: InitVar[str | None] = None

    def __post_init__(self, raw_text: str | None = None) -> None:
        if raw_text is not None and not self.raw_input:
            self.raw_input = raw_text

    @property
    def raw_text(self) -> str:
        return self.raw_input

@dataclass
class ExecutionResult:
    """Represents the structured response from executing a macOS command."""
    status: ExecutionStatus
    message: str
    command_name: str
    category: CommandCategory
    execution_time_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
