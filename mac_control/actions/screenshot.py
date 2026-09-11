"""Screenshot capture controls delegating to the centralized ScreenshotService."""

from __future__ import annotations

from core.screenshot import screenshot_service
from mac_control.models import ExecutionResult, ExecutionStatus, CommandCategory, MacCommand


def execute_screenshot_command(cmd: MacCommand) -> ExecutionResult:
    """Execute screenshot capture commands via centralized ScreenshotService."""
    action = cmd.action

    try:
        if action == "capture_full":
            res = screenshot_service.capture_full_screen()
            if res.success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Full screenshot saved to NOVA Screenshots: {res.filename}",
                    command_name="Full Screenshot",
                    category=CommandCategory.SCREENSHOT,
                    details={"filepath": str(res.file_path), "filename": res.filename},
                )
            elif res.error_type == "PERMISSION_DENIED":
                return ExecutionResult(
                    status=ExecutionStatus.PERMISSION_DENIED,
                    message=res.error or "Screen recording permission is missing.",
                    command_name="Full Screenshot",
                    category=CommandCategory.SCREENSHOT,
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=res.error or "Screenshot capture failed.",
                    command_name="Full Screenshot",
                    category=CommandCategory.SCREENSHOT,
                )

        elif action == "capture_area":
            res = screenshot_service.capture_area()
            if res.success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Area screenshot saved to NOVA Screenshots: {res.filename}",
                    command_name="Area Screenshot",
                    category=CommandCategory.SCREENSHOT,
                    details={"filepath": str(res.file_path), "filename": res.filename},
                )
            elif res.error_type == "USER_CANCELLED":
                return ExecutionResult(
                    status=ExecutionStatus.CANCELLED,
                    message="Screenshot selection was cancelled by user",
                    command_name="Area Screenshot",
                    category=CommandCategory.SCREENSHOT,
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=res.error or "Area screenshot capture failed.",
                    command_name="Area Screenshot",
                    category=CommandCategory.SCREENSHOT,
                )

        elif action == "capture_window":
            res = screenshot_service.capture_window()
            if res.success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Window screenshot saved to NOVA Screenshots: {res.filename}",
                    command_name="Window Screenshot",
                    category=CommandCategory.SCREENSHOT,
                    details={"filepath": str(res.file_path), "filename": res.filename},
                )
            elif res.error_type == "USER_CANCELLED":
                return ExecutionResult(
                    status=ExecutionStatus.CANCELLED,
                    message="Screenshot selection was cancelled by user",
                    command_name="Window Screenshot",
                    category=CommandCategory.SCREENSHOT,
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=res.error or "Window screenshot capture failed.",
                    command_name="Window Screenshot",
                    category=CommandCategory.SCREENSHOT,
                )

        elif action == "open_folder":
            success, msg = screenshot_service.open_screenshot_folder()
            if success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message="Opened NOVA Screenshots folder",
                    command_name="Open Screenshot Folder",
                    category=CommandCategory.SCREENSHOT,
                    details={"path": str(screenshot_service.output_dir)},
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=msg,
                    command_name="Open Screenshot Folder",
                    category=CommandCategory.SCREENSHOT,
                )

    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Screenshot capture failed: {exc}",
            command_name="Screenshot Capture",
            category=CommandCategory.SCREENSHOT,
        )

    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown screenshot action: {action}",
        command_name="Screenshot Capture",
        category=CommandCategory.SCREENSHOT,
    )
