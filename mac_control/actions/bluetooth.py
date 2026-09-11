"""Bluetooth hardware controls, real-time power detection, and connected device discovery for macOS."""

from __future__ import annotations

import ctypes
import re
import shutil
import subprocess
import time
from typing import Any

from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand


def get_bluetooth_status() -> bool:
    """Check if Bluetooth power is currently ON using native macOS frameworks."""
    # Method 1: IOBluetooth C preference function (instantaneous ~1ms)
    try:
        iob = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOBluetooth.framework/IOBluetooth")
        if hasattr(iob, "IOBluetoothPreferenceGetControllerPowerState"):
            iob.IOBluetoothPreferenceGetControllerPowerState.restype = ctypes.c_int
            power_code = iob.IOBluetoothPreferenceGetControllerPowerState()
            return bool(power_code == 1)
    except Exception:
        pass

    # Method 2: blueutil CLI (if installed)
    blueutil_path = shutil.which("blueutil")
    if blueutil_path:
        try:
            res = subprocess.run([blueutil_path, "-p"], capture_output=True, text=True, timeout=1.5)
            if res.returncode == 0:
                return res.stdout.strip() == "1"
        except Exception:
            pass

    # Method 3: Native macOS system_profiler SPBluetoothDataType
    try:
        res = subprocess.run(
            ["system_profiler", "SPBluetoothDataType"],
            capture_output=True,
            text=True,
            timeout=4.0,
        )
        if res.returncode == 0:
            match = re.search(r"State:\s*(On|Off)", res.stdout, re.IGNORECASE)
            if match:
                return match.group(1).lower() == "on"
    except Exception:
        pass

    return False


def get_bluetooth_power_state() -> str:
    """Return 'ON' or 'OFF' string representing actual Bluetooth power state."""
    return "ON" if get_bluetooth_status() else "OFF"


def get_connected_bluetooth_devices() -> tuple[list[str], str | None]:
    """Retrieve connected Bluetooth devices and error if any."""
    try:
        devs = get_connected_devices()
        return devs, None
    except Exception as exc:
        return [], str(exc)


def get_connected_devices() -> list[str]:
    """Retrieve the names of all currently connected Bluetooth devices."""
    # Method 1: PyObjC IOBluetooth framework (~5ms)
    try:
        import IOBluetooth
        devices = IOBluetooth.IOBluetoothDevice.pairedDevices()
        if devices:
            connected: list[str] = []
            for d in devices:
                try:
                    if d.isConnected():
                        name = d.nameOrAddress()
                        if name and name not in connected:
                            connected.append(str(name))
                except Exception:
                    continue
            return connected
    except Exception:
        pass

    # Method 2: Parse system_profiler SPBluetoothDataType
    try:
        res = subprocess.run(
            ["system_profiler", "SPBluetoothDataType"],
            capture_output=True,
            text=True,
            timeout=4.0,
        )
        if res.returncode == 0 and res.stdout:
            lines = res.stdout.splitlines()
            in_connected = False
            devices: list[str] = []
            for line in lines:
                stripped = line.strip()
                if stripped == "Connected:":
                    in_connected = True
                    continue
                elif stripped in ("Not Connected:", "Bluetooth Controller:"):
                    in_connected = False
                    continue

                if in_connected and stripped.endswith(":"):
                    # e.g. "Boult Audio Airbass:" -> device name
                    dev_name = stripped[:-1].strip()
                    if dev_name and not dev_name.startswith("Minor Type") and not dev_name.startswith("Address"):
                        if dev_name not in devices:
                            devices.append(dev_name)
            return devices
    except Exception:
        pass

    return []


def set_bluetooth_power(enable: bool) -> tuple[bool, str]:
    """Turn Bluetooth power on or off and verify actual resulting state."""
    target_val = 1 if enable else 0
    target_desc = "ON" if enable else "OFF"

    # Attempt 1: Native IOBluetoothPreferenceSetControllerPowerState
    try:
        iob = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOBluetooth.framework/IOBluetooth")
        if hasattr(iob, "IOBluetoothPreferenceSetControllerPowerState"):
            iob.IOBluetoothPreferenceSetControllerPowerState.argtypes = [ctypes.c_int]
            iob.IOBluetoothPreferenceSetControllerPowerState.restype = ctypes.c_int
            iob.IOBluetoothPreferenceSetControllerPowerState(target_val)
    except Exception:
        pass

    # Attempt 2: blueutil CLI if installed
    blueutil_path = shutil.which("blueutil")
    if blueutil_path:
        try:
            subprocess.run([blueutil_path, "-p", str(target_val)], capture_output=True, timeout=2.0)
        except Exception:
            pass

    # Verify state with brief settle pause
    time.sleep(0.5)
    actual_state = get_bluetooth_status()
    if actual_state == enable:
        return True, f"Bluetooth turned {target_desc}"

    # If verification failed
    return (
        False,
        "Bluetooth control backend unavailable. Please install 'blueutil' via Homebrew ('brew install blueutil') or grant Accessibility privileges."
    )


def execute_bluetooth_command(cmd: MacCommand | str) -> ExecutionResult:
    """Execute Bluetooth hardware interface commands."""
    start_time = time.monotonic()
    action = (cmd if isinstance(cmd, str) else cmd.action).lower()

    try:
        if action in ("get", "status", "check"):
            power = get_bluetooth_status()
            elapsed_ms = (time.monotonic() - start_time) * 1000
            status_msg = f"Bluetooth is {'ON' if power else 'OFF'}."
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=status_msg,
                command_name="Get Bluetooth Status",
                category=CommandCategory.NETWORK,
                details={"power": power, "state": "on" if power else "off"},
                execution_time_ms=elapsed_ms,
            )

        elif action in ("devices", "connected", "device", "which", "list"):
            power = get_bluetooth_status()
            if not power:
                elapsed_ms = (time.monotonic() - start_time) * 1000
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message="Bluetooth is currently OFF.",
                    command_name="Get Bluetooth Devices",
                    category=CommandCategory.NETWORK,
                    details={"power": False, "devices": []},
                    execution_time_ms=elapsed_ms,
                )

            devices = get_connected_devices()
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if devices:
                dev_list_str = ", ".join(devices)
                status_msg = f"Bluetooth is ON. Connected devices: {dev_list_str}."
            else:
                status_msg = "Bluetooth is ON. No currently connected Bluetooth devices."

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=status_msg,
                command_name="Get Bluetooth Devices",
                category=CommandCategory.NETWORK,
                details={"power": True, "devices": devices},
                execution_time_ms=elapsed_ms,
            )

        elif action in ("on", "enable"):
            success, msg = set_bluetooth_power(True)
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message="Done Boss. Bluetooth is on.",
                    command_name="Turn Bluetooth On",
                    category=CommandCategory.NETWORK,
                    details={"state": "on", "power": True},
                    execution_time_ms=elapsed_ms,
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=msg,
                    command_name="Turn Bluetooth On",
                    category=CommandCategory.NETWORK,
                    error=msg,
                    execution_time_ms=elapsed_ms,
                )

        elif action in ("off", "disable"):
            success, msg = set_bluetooth_power(False)
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message="Done Boss. Bluetooth is off.",
                    command_name="Turn Bluetooth Off",
                    category=CommandCategory.NETWORK,
                    details={"state": "off", "power": False},
                    execution_time_ms=elapsed_ms,
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=msg,
                    command_name="Turn Bluetooth Off",
                    category=CommandCategory.NETWORK,
                    error=msg,
                    execution_time_ms=elapsed_ms,
                )

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Bluetooth operation failed: {exc}",
            command_name="Bluetooth Control",
            category=CommandCategory.NETWORK,
            error=str(exc),
            execution_time_ms=elapsed_ms,
        )

    elapsed_ms = (time.monotonic() - start_time) * 1000
    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown Bluetooth action: {action}",
        command_name="Bluetooth Control",
        category=CommandCategory.NETWORK,
        execution_time_ms=elapsed_ms,
    )
