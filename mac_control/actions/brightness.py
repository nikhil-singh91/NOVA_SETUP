"""Brightness controls using native DisplayServices bindings and keycode events."""

from __future__ import annotations

import ctypes
import subprocess
from typing import Any
from mac_control.models import ExecutionResult, ExecutionStatus, CommandCategory, MacCommand

# Try to resolve display ID via Quartz (pyobjc-framework-Quartz)
try:
    from Quartz import CGMainDisplayID
    _has_quartz = True
except ImportError:
    _has_quartz = False

# Try to load macOS private DisplayServices framework
_has_display_services = False
try:
    dspf = ctypes.CDLL('/System/Library/PrivateFrameworks/DisplayServices.framework/Versions/A/DisplayServices')
    dspf.DisplayServicesGetBrightness.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float)]
    dspf.DisplayServicesGetBrightness.restype = ctypes.c_int
    dspf.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]
    dspf.DisplayServicesSetBrightness.restype = ctypes.c_int
    _has_display_services = True
except Exception:
    pass

def get_brightness_level() -> int:
    """Query current brightness level (0-100)."""
    if _has_display_services and _has_quartz:
        try:
            display_id = CGMainDisplayID()
            val = ctypes.c_float()
            dspf.DisplayServicesGetBrightness(display_id, ctypes.byref(val))
            return int(round(val.value * 100))
        except Exception:
            pass
    return 50


def set_brightness_level(val: int) -> int:
    """Set brightness level (0-100) and return actual value."""
    target = max(0, min(100, int(val)))
    if _has_display_services and _has_quartz:
        try:
            display_id = CGMainDisplayID()
            dspf.DisplayServicesSetBrightness(display_id, ctypes.c_float(target / 100.0))
            return get_brightness_level()
        except Exception:
            pass
    return target


def execute_brightness_command(cmd: MacCommand) -> ExecutionResult:
    """Execute screen brightness operations."""
    action = cmd.action.lower()
    args = cmd.args or {}

    # Try native display control first
    if _has_display_services and _has_quartz:
        return _execute_native(action, args)
    else:
        return _execute_fallback(action, args)


def _execute_native(action: str, args: dict[str, Any]) -> ExecutionResult:
    try:
        display_id = CGMainDisplayID()

        if action in ("get", "status", "check"):
            val = ctypes.c_float()
            dspf.DisplayServicesGetBrightness(display_id, ctypes.byref(val))
            percentage = int(round(val.value * 100))
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Brightness is {percentage}%",
                command_name="Get Brightness",
                category=CommandCategory.BRIGHTNESS,
                details={"brightness": percentage, "actual_value": percentage}
            )

        elif action == "set":
            target = args.get("value", 50)
            target = max(0, min(100, int(target)))
            dspf.DisplayServicesSetBrightness(display_id, ctypes.c_float(target / 100.0))
            actual = get_brightness_level()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Brightness set to {actual}%",
                command_name="Set Brightness",
                category=CommandCategory.BRIGHTNESS,
                details={"requested_value": target, "actual_value": actual}
            )

        elif action == "increase":
            val = ctypes.c_float()
            dspf.DisplayServicesGetBrightness(display_id, ctypes.byref(val))
            current_pct = int(round(val.value * 100))

            if "value" in args and args["value"] is not None:
                target_pct = max(0, min(100, int(args["value"])))
            elif "step" in args and args["step"] is not None:
                target_pct = min(100, current_pct + int(args["step"]))
            else:
                target_pct = min(100, current_pct + 10)

            dspf.DisplayServicesSetBrightness(display_id, ctypes.c_float(target_pct / 100.0))
            actual = get_brightness_level()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Brightness increased to {actual}%",
                command_name="Increase Brightness",
                category=CommandCategory.BRIGHTNESS,
                details={"requested_value": target_pct, "actual_value": actual}
            )

        elif action == "decrease":
            val = ctypes.c_float()
            dspf.DisplayServicesGetBrightness(display_id, ctypes.byref(val))
            current_pct = int(round(val.value * 100))

            if "value" in args and args["value"] is not None:
                target_pct = max(0, min(100, int(args["value"])))
            elif "step" in args and args["step"] is not None:
                target_pct = max(0, current_pct - int(args["step"]))
            else:
                target_pct = max(0, current_pct - 10)

            dspf.DisplayServicesSetBrightness(display_id, ctypes.c_float(target_pct / 100.0))
            actual = get_brightness_level()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Brightness decreased to {actual}%",
                command_name="Decrease Brightness",
                category=CommandCategory.BRIGHTNESS,
                details={"requested_value": target_pct, "actual_value": actual}
            )

    except Exception as exc:
        return _execute_fallback(action, args)
        
    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown brightness action: {action}",
        command_name="Brightness Control",
        category=CommandCategory.BRIGHTNESS
    )

def _execute_fallback(action: str, args: dict[str, Any]) -> ExecutionResult:
    """Fallback utilizing AppleScript keycode emulation if private framework fails."""
    try:
        if action == "increase":
            if "value" in args and args["value"] is not None:
                target = max(0, min(100, int(args["value"])))
                actual = set_brightness_level(target)
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Brightness set to {actual}%",
                    command_name="Set Brightness",
                    category=CommandCategory.BRIGHTNESS,
                    details={"requested_value": target, "actual_value": actual}
                )
            # key code 144 is Brightness Up
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 144'], check=True, capture_output=True, text=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Brightness increased",
                command_name="Increase Brightness (Fallback)",
                category=CommandCategory.BRIGHTNESS
            )
        elif action == "decrease":
            if "value" in args and args["value"] is not None:
                target = max(0, min(100, int(args["value"])))
                actual = set_brightness_level(target)
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Brightness set to {actual}%",
                    command_name="Set Brightness",
                    category=CommandCategory.BRIGHTNESS,
                    details={"requested_value": target, "actual_value": actual}
                )
            # key code 145 is Brightness Down
            subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 145'], check=True, capture_output=True, text=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Brightness decreased",
                command_name="Decrease Brightness (Fallback)",
                category=CommandCategory.BRIGHTNESS
            )
        elif action == "set":
            target = args.get("value", 50)
            target = max(0, min(100, int(target)))
            actual = set_brightness_level(target)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Brightness set to {actual}%",
                command_name="Set Brightness",
                category=CommandCategory.BRIGHTNESS,
                details={"requested_value": target, "actual_value": actual}
            )
        elif action in ("get", "status", "check"):
            val = get_brightness_level()
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Brightness is {val}%",
                command_name="Get Brightness",
                category=CommandCategory.BRIGHTNESS,
                details={"brightness": val, "actual_value": val}
            )
    except subprocess.CalledProcessError as exc:
        err_msg = exc.stderr if exc.stderr else str(exc)
        if "not allowed" in err_msg.lower() or "1743" in err_msg:
            return ExecutionResult(
                status=ExecutionStatus.PERMISSION_DENIED,
                message="macOS Accessibility permission is required to adjust screen brightness via System Events.",
                command_name="Brightness Control",
                category=CommandCategory.BRIGHTNESS,
                error=err_msg
            )
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Brightness command failed: {err_msg}",
            command_name="Brightness Control",
            category=CommandCategory.BRIGHTNESS,
            error=err_msg
        )
    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Brightness fallback failed: {exc}",
            command_name="Brightness Control",
            category=CommandCategory.BRIGHTNESS,
            error=str(exc)
        )
        
    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown brightness action: {action}",
        command_name="Brightness Control",
        category=CommandCategory.BRIGHTNESS
    )
