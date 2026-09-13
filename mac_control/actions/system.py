"""Core macOS system operations (sleep, restart, shutdown, screen locking, emptying trash)."""

from __future__ import annotations

import subprocess

from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand


def execute_system_command(cmd: MacCommand) -> ExecutionResult:
    """Execute dangerous or general macOS system controls (requires confirmation before routing)."""
    action = cmd.action

    try:
        if action == "sleep":
            subprocess.run(["osascript", "-e", 'tell application "System Events" to sleep'], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Mac is going to sleep",
                command_name="Sleep Mac",
                category=CommandCategory.SYSTEM
            )

        elif action == "restart":
            # Dangerous command (pre-confirmed by manager)
            subprocess.run(["osascript", "-e", 'tell application "System Events" to restart'], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Mac is restarting",
                command_name="Restart Mac",
                category=CommandCategory.SYSTEM
            )

        elif action == "shutdown":
            # Dangerous command (pre-confirmed by manager)
            subprocess.run(["osascript", "-e", 'tell application "System Events" to shut down'], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Mac is shutting down",
                command_name="Shutdown Mac",
                category=CommandCategory.SYSTEM
            )

        elif action == "logout":
            subprocess.run(["osascript", "-e", 'tell application "System Events" to log out'], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="User is logging out",
                command_name="Logout User",
                category=CommandCategory.SYSTEM
            )

        elif action == "lock_screen":
            # Standard macOS displaysleepnow command triggers screen lock
            subprocess.run(["pmset", "displaysleepnow"], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Screen locked",
                command_name="Lock Screen",
                category=CommandCategory.SYSTEM
            )

        elif action == "empty_trash":
            # Empty trash via Finder AppleScript (pre-confirmed by manager)
            subprocess.run(["osascript", "-e", 'tell application "Finder" to empty trash'], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Trash emptied",
                command_name="Empty Trash",
                category=CommandCategory.SYSTEM
            )

    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"System operation failed: {exc}",
            command_name="System Control",
            category=CommandCategory.SYSTEM
        )

    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown system action: {action}",
        command_name="System Control",
        category=CommandCategory.SYSTEM
    )


def lock_screen() -> ExecutionResult:
    """Lock macOS display immediately."""
    cmd = MacCommand(category=CommandCategory.SYSTEM, action="lock_screen")
    return execute_system_command(cmd)
