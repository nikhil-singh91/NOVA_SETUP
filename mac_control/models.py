"""Subsystem models, enums, and structured execution data representations."""

from __future__ import annotations

from dataclasses import dataclass, field
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

    def __init__(
        self,
        category: CommandCategory,
        action: str,
        raw_input: str = "",
        args: dict[str, Any] | None = None,
        is_dangerous: bool = False,
        raw_text: str | None = None,
    ) -> None:
        self.category = category
        self.action = action
        self.raw_input = raw_input or (raw_text or "")
        self.args = args if args is not None else {}
        self.is_dangerous = is_dangerous

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
