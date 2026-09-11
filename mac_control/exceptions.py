"""Custom exceptions for the macOS Control subsystem."""

from core.exceptions import NovaError

class MacControlError(NovaError):
    """Base exception for all macOS control operations."""
    default_message = "An error occurred in the macOS Control subsystem."

class CommandExecutionError(MacControlError):
    """Exception raised when a specific system command fails to execute."""
    def __init__(self, message: str, cmd_name: str, original_exception: Exception | None = None) -> None:
        super().__init__(message, original_exception=original_exception)
        self.cmd_name = cmd_name

class PermissionDeniedError(MacControlError):
    """Exception raised when macOS Accessibility or System permissions are missing."""
    pass
