"""Router to map parsed command categories to their specific execution modules."""

from __future__ import annotations

import time

from mac_control.actions.applications import execute_applications_command
from mac_control.actions.brightness import execute_brightness_command
from mac_control.actions.browser import execute_browser_command
from mac_control.actions.clipboard import execute_clipboard_command
from mac_control.actions.finder import execute_finder_command
from mac_control.actions.media import execute_media_command
from mac_control.actions.network import execute_network_command
from mac_control.actions.screenshot import execute_screenshot_command
from mac_control.actions.system import execute_system_command
from mac_control.actions.volume import execute_volume_command
from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand


class CommandRouter:
    """Invokes the appropriate action execution function based on category."""

    def __init__(self) -> None:
        self._handlers = {
            CommandCategory.VOLUME: execute_volume_command,
            CommandCategory.BRIGHTNESS: execute_brightness_command,
            CommandCategory.APPLICATIONS: execute_applications_command,
            CommandCategory.BROWSER: execute_browser_command,
            CommandCategory.MEDIA: execute_media_command,
            CommandCategory.FINDER: execute_finder_command,
            CommandCategory.SCREENSHOT: execute_screenshot_command,
            CommandCategory.CLIPBOARD: execute_clipboard_command,
            CommandCategory.NETWORK: execute_network_command,
            CommandCategory.SYSTEM: execute_system_command
        }

    def route_and_execute(self, cmd: MacCommand) -> ExecutionResult:
        """Route the command, measure wall-clock execution latency, and return the result."""
        handler = self._handlers.get(cmd.category)
        if not handler:
            return ExecutionResult(
                status=ExecutionStatus.NOT_SUPPORTED,
                message=f"No execution handler registered for category: {cmd.category}",
                command_name="Unrouted Action",
                category=cmd.category
            )

        start_time = time.perf_counter()
        try:
            result = handler(cmd)
        except Exception as exc:
            result = ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Unexpected handler execution failure: {exc}",
                command_name="Execution Router",
                category=cmd.category
            )

        latency = int((time.perf_counter() - start_time) * 1000)
        result.execution_time_ms = latency
        return result
