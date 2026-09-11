"""macOS Control subsystem package for native hardware/software automation."""

from __future__ import annotations

from mac_control.manager import MacControlManager
from mac_control.models import MacCommand, ExecutionResult, ExecutionStatus, CommandCategory

__all__ = [
    "MacControlManager",
    "MacCommand",
    "ExecutionResult",
    "ExecutionStatus",
    "CommandCategory"
]
