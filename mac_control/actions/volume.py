"""Volume controls and mute toggles using AppleScript."""

from __future__ import annotations

import subprocess

from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand


def get_volume_level() -> int:
    """Query AppleScript for current system volume setting."""
    return _get_current_volume()


def set_volume_level(val: int) -> int:
    """Set system volume level (0-100) and return actual value."""
    target = max(0, min(100, int(val)))
    subprocess.run(["osascript", "-e", f"set volume output volume {target}"], check=True)
    subprocess.run(["osascript", "-e", "set volume without output muted"], check=False)
    return _get_current_volume()


def execute_volume_command(cmd: MacCommand) -> ExecutionResult:
    """Execute audio volume operations."""
    action = cmd.action.lower()
    args = cmd.args or {}

    try:
        if action == "mute":
            subprocess.run(["osascript", "-e", "set volume with output muted"], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Audio output muted",
                command_name="Mute Volume",
                category=CommandCategory.VOLUME,
                details={"muted": True, "actual_value": 0}
            )

        elif action == "unmute":
            subprocess.run(["osascript", "-e", "set volume without output muted"], check=True)
            current = _get_current_volume()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Audio output unmuted",
                command_name="Unmute Volume",
                category=CommandCategory.VOLUME,
                details={"muted": False, "actual_value": current}
            )

        elif action in ("get", "status", "check"):
            vol = _get_current_volume()
            muted = _is_muted()
            status_msg = f"Volume is {vol}%" + (" (Muted)" if muted else "")
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=status_msg,
                command_name="Get Volume",
                category=CommandCategory.VOLUME,
                details={"volume": vol, "actual_value": vol, "muted": muted}
            )

        elif action == "set":
            raw_val = args.get("value", 50)
            target = max(0, min(100, int(raw_val)))
            actual = set_volume_level(target)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Volume set to {actual}%",
                command_name="Set Volume",
                category=CommandCategory.VOLUME,
                details={"requested_value": target, "actual_value": actual}
            )

        elif action == "increase":
            current = _get_current_volume()
            if "value" in args and args["value"] is not None:
                # "increase volume to 70%" or "increase 70% volume"
                target = max(0, min(100, int(args["value"])))
            elif "step" in args and args["step"] is not None:
                # "increase volume by 20%"
                target = min(100, current + int(args["step"]))
            else:
                target = min(100, current + 10)

            actual = set_volume_level(target)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Volume increased to {actual}%",
                command_name="Increase Volume",
                category=CommandCategory.VOLUME,
                details={"requested_value": target, "actual_value": actual}
            )

        elif action == "decrease":
            current = _get_current_volume()
            if "value" in args and args["value"] is not None:
                # "decrease volume to 30%"
                target = max(0, min(100, int(args["value"])))
            elif "step" in args and args["step"] is not None:
                # "decrease volume by 10%"
                target = max(0, current - int(args["step"]))
            else:
                target = max(0, current - 10)

            actual = set_volume_level(target)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Volume decreased to {actual}%",
                command_name="Decrease Volume",
                category=CommandCategory.VOLUME,
                details={"requested_value": target, "actual_value": actual}
            )

    except subprocess.CalledProcessError as exc:
        err_msg = exc.stderr if exc.stderr else str(exc)
        if "not allowed" in err_msg.lower() or "1743" in err_msg:
            return ExecutionResult(
                status=ExecutionStatus.PERMISSION_DENIED,
                message="macOS Accessibility permission is required to adjust volume.",
                command_name="Volume Control",
                category=CommandCategory.VOLUME,
                error=err_msg
            )
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Volume operation failed: {err_msg}",
            command_name="Volume Control",
            category=CommandCategory.VOLUME,
            error=err_msg
        )
    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Volume operation failed: {exc}",
            command_name="Volume Control",
            category=CommandCategory.VOLUME,
            error=str(exc)
        )

    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown volume action: {action}",
        command_name="Volume Control",
        category=CommandCategory.VOLUME
    )

def _get_current_volume() -> int:
    """Query AppleScript for current system volume setting."""
    try:
        res = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True, text=True, check=True
        )
        return int(res.stdout.strip())
    except Exception:
        return 50

def _is_muted() -> bool:
    """Query AppleScript for current mute state."""
    try:
        res = subprocess.run(
            ["osascript", "-e", "output muted of (get volume settings)"],
            capture_output=True, text=True, check=True
        )
        return res.stdout.strip() == "true"
    except Exception:
        return False
