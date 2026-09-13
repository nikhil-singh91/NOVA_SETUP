"""Router and diagnostics compiler for all network interfaces (WiFi, Bluetooth)."""

from __future__ import annotations

from mac_control.actions.bluetooth import execute_bluetooth_command
from mac_control.actions.wifi import execute_wifi_command
from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand


def execute_network_command(cmd: MacCommand) -> ExecutionResult:
    """Route network related commands to their specific WiFi/Bluetooth handlers."""
    action = cmd.action
    target = cmd.args.get("target", "all").lower().strip()

    if target == "wifi":
        return execute_wifi_command(cmd)
    elif target == "bluetooth":
        return execute_bluetooth_command(cmd)

    # If generic status query
    if action == "get":
        try:
            wifi_res = execute_wifi_command(MacCommand(CommandCategory.NETWORK, "get", cmd.raw_input))
            bt_res = execute_bluetooth_command(MacCommand(CommandCategory.NETWORK, "get", cmd.raw_input))

            wifi_msg = wifi_res.message if wifi_res.status == ExecutionStatus.SUCCESS else "WiFi status unknown"
            bt_msg = bt_res.message if bt_res.status == ExecutionStatus.SUCCESS else "Bluetooth status unknown"

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"{wifi_msg} | {bt_msg}",
                command_name="Get Network Status",
                category=CommandCategory.NETWORK,
                details={
                    "wifi": wifi_res.details if wifi_res.status == ExecutionStatus.SUCCESS else {},
                    "bluetooth": bt_res.details if bt_res.status == ExecutionStatus.SUCCESS else {}
                }
            )
        except Exception as exc:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Network diagnostic failed: {exc}",
                command_name="Get Network Status",
                category=CommandCategory.NETWORK
            )

    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown generic network operation: {action} (Target: {target})",
        command_name="Network Control",
        category=CommandCategory.NETWORK
    )
