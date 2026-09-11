"""WiFi interface controls, active SSID discovery, and detailed network diagnostics for macOS."""

from __future__ import annotations

import re
import socket
import subprocess
import time
from typing import Any

from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand


def _get_wifi_interface() -> str:
    """Dynamically determine the primary Wi-Fi interface name (typically en0)."""
    try:
        res = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2.0,
        )
        ports = res.stdout
        match = re.search(r"Hardware Port:\s*Wi-Fi\s*\nDevice:\s*(\w+)", ports, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass

    # Fallback: check default routing interface
    try:
        res = subprocess.run(
            ["netstat", "-rn", "-f", "inet"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2.0,
        )
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 6 and parts[0] == "default" and parts[5].startswith("en"):
                return parts[5]
    except Exception:
        pass

    return "en0"


def get_wifi_status(interface: str | None = None) -> bool:
    """Check if WiFi power is currently ON."""
    if not interface:
        interface = _get_wifi_interface()

    try:
        res = subprocess.run(
            ["networksetup", "-getairportpower", interface],
            capture_output=True,
            text=True,
            check=True,
            timeout=2.0,
        )
        return ": on" in res.stdout.lower()
    except Exception:
        pass

    try:
        import CoreWLAN
        client = CoreWLAN.CWWiFiClient.sharedWiFiClient()
        iface = client.interfaceWithName_(interface) if hasattr(client, "interfaceWithName_") else client.interface()
        if iface:
            return bool(iface.powerOn())
    except Exception:
        pass

    return False


def get_wifi_interface() -> str:
    """Public wrapper to dynamically determine the primary Wi-Fi interface name."""
    return _get_wifi_interface()


def get_wifi_power_state(interface: str | None = None) -> str:
    """Return 'ON' or 'OFF' string representing actual Wi-Fi power state."""
    return "ON" if get_wifi_status(interface) else "OFF"


def get_current_ssid(interface: str | None = None) -> str | None:
    """Retrieve the real connected Wi-Fi network SSID without requiring Location Services."""
    if not interface:
        interface = _get_wifi_interface()

    # Method 1: ipconfig getsummary <interface> (Extremely fast, reliable on macOS Sonoma / Sequoia)
    try:
        res = subprocess.run(
            ["ipconfig", "getsummary", interface],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                m = re.match(r"^\s*SSID\s*:\s*(.+)$", line)
                if m:
                    ssid = m.group(1).strip()
                    if ssid and "not associated" not in ssid.lower():
                        return ssid
    except Exception:
        pass

    # Method 2: system_profiler SPAirPortDataType
    try:
        res = subprocess.run(
            ["system_profiler", "SPAirPortDataType"],
            capture_output=True,
            text=True,
            timeout=4.0,
        )
        if res.returncode == 0 and res.stdout:
            lines = res.stdout.splitlines()
            for i, line in enumerate(lines):
                if "Current Network Information:" in line:
                    # The next non-empty indented line is the network name followed by a colon
                    for subline in lines[i + 1 : i + 5]:
                        stripped = subline.strip()
                        if stripped and stripped.endswith(":"):
                            cand = stripped[:-1].strip()
                            if cand and not cand.startswith("PHY Mode") and not cand.startswith("Channel"):
                                return cand
    except Exception:
        pass

    # Method 3: networksetup -getairportnetwork <interface>
    try:
        res = subprocess.run(
            ["networksetup", "-getairportnetwork", interface],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        out = res.stdout.strip()
        match = re.search(r"Current Wi-Fi Network:\s*(.+)", out, re.IGNORECASE)
        if match:
            ssid = match.group(1).strip()
            if "not associated" not in ssid.lower():
                return ssid
    except Exception:
        pass

    # Method 4: CoreWLAN (if permissions exist)
    try:
        import CoreWLAN
        client = CoreWLAN.CWWiFiClient.sharedWiFiClient()
        iface = client.interfaceWithName_(interface) if hasattr(client, "interfaceWithName_") else client.interface()
        if iface and iface.ssid():
            return str(iface.ssid())
    except Exception:
        pass

    return None


get_connected_ssid = get_current_ssid


def get_wifi_info() -> dict[str, Any]:
    """Inspect and return full structured WiFi state."""
    interface = _get_wifi_interface()
    power = get_wifi_status(interface)
    ssid = get_current_ssid(interface) if power else None
    return {
        "interface": interface,
        "power": power,
        "connected": bool(ssid),
        "ssid": ssid,
    }


def get_network_details(interface: str | None = None) -> dict[str, Any]:
    """Inspect full detailed network status including IP, gateway, and internet reachability."""
    if not interface:
        interface = _get_wifi_interface()

    power = get_wifi_status(interface)
    ssid = get_current_ssid(interface) if power else None

    # Local IP
    local_ip = None
    try:
        res = subprocess.run(["ipconfig", "getifaddr", interface], capture_output=True, text=True, timeout=1.0)
        if res.returncode == 0 and res.stdout.strip():
            local_ip = res.stdout.strip()
    except Exception:
        pass

    # Gateway router IP
    gateway = None
    try:
        res = subprocess.run(["netstat", "-rn", "-f", "inet"], capture_output=True, text=True, timeout=1.5)
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "default":
                gateway = parts[1]
                break
    except Exception:
        pass

    # Internet check (fast non-blocking probe to Cloudflare DNS / Google DNS)
    internet_reachable = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.2)
        s.connect(("1.1.1.1", 53))
        s.close()
        internet_reachable = True
    except Exception:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.2)
            s.connect(("8.8.8.8", 53))
            s.close()
            internet_reachable = True
        except Exception:
            internet_reachable = False

    return {
        "interface": interface,
        "power": power,
        "power_str": "ON" if power else "OFF",
        "connected": bool(ssid),
        "ssid": ssid or "None",
        "local_ip": local_ip or "Unavailable",
        "gateway": gateway or "Unavailable",
        "internet": "Connected" if internet_reachable else "Offline",
        "internet_reachable": internet_reachable,
    }


def set_wifi_power(enable: bool, interface: str | None = None) -> tuple[bool, str]:
    """Turn WiFi power on or off and verify actual state."""
    if not interface:
        interface = _get_wifi_interface()

    target_state = "on" if enable else "off"
    try:
        subprocess.run(["networksetup", "-setairportpower", interface, target_state], check=True, timeout=4.0)
    except subprocess.CalledProcessError:
        try:
            subprocess.run(["networksetup", "-setapower", interface, target_state], check=True, timeout=4.0)
        except Exception as exc:
            return False, f"Failed to issue Wi-Fi power command: {exc}"
    except Exception as exc:
        return False, f"Failed to toggle Wi-Fi power: {exc}"

    # Verify actual resulting state with a brief settle delay
    time.sleep(0.5)
    actual_state = get_wifi_status(interface)
    if actual_state == enable:
        return True, f"Wi-Fi turned {target_state.upper()}"
    return False, f"Attempted to turn Wi-Fi {target_state.upper()}, but current state is {'ON' if actual_state else 'OFF'}"


def execute_wifi_command(cmd: MacCommand | str) -> ExecutionResult:
    """Execute WiFi network interface commands."""
    start_time = time.monotonic()
    action = (cmd if isinstance(cmd, str) else cmd.action).lower()
    interface = _get_wifi_interface()

    try:
        if action in ("on", "enable"):
            success, msg = set_wifi_power(True, interface)
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message="Done Boss. Wi-Fi is on.",
                    command_name="Turn WiFi On",
                    category=CommandCategory.NETWORK,
                    details={"interface": interface, "power": True},
                    execution_time_ms=elapsed_ms,
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=msg,
                    command_name="Turn WiFi On",
                    category=CommandCategory.NETWORK,
                    error=msg,
                    execution_time_ms=elapsed_ms,
                )

        elif action in ("off", "disable"):
            success, msg = set_wifi_power(False, interface)
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message="Done Boss. Wi-Fi is off.",
                    command_name="Turn WiFi Off",
                    category=CommandCategory.NETWORK,
                    details={"interface": interface, "power": False},
                    execution_time_ms=elapsed_ms,
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=msg,
                    command_name="Turn WiFi Off",
                    category=CommandCategory.NETWORK,
                    error=msg,
                    execution_time_ms=elapsed_ms,
                )

        elif action in ("ssid", "network", "which"):
            info = get_wifi_info()
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if not info["power"]:
                status_msg = "Wi-Fi is currently off."
            elif info["ssid"]:
                status_msg = f"You are connected to {info['ssid']}."
            else:
                status_msg = "Wi-Fi is on, but you are not connected to any network."

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=status_msg,
                command_name="Get Connected Network",
                category=CommandCategory.NETWORK,
                details=info,
                execution_time_ms=elapsed_ms,
            )

        elif action in ("details", "info", "network_info", "ip"):
            details = get_network_details(interface)
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if not details["power"]:
                status_msg = "Wi-Fi is currently off."
            elif details["connected"]:
                status_msg = f"You are connected to {details['ssid']} on {details['interface']} with IP {details['local_ip']}. Internet is {details['internet']}."
            else:
                status_msg = f"Wi-Fi is on ({details['interface']}), but not connected. IP: {details['local_ip']}."

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=status_msg,
                command_name="Get Network Details",
                category=CommandCategory.NETWORK,
                details=details,
                execution_time_ms=elapsed_ms,
            )

        elif action in ("get", "status", "check"):
            info = get_wifi_info()
            elapsed_ms = (time.monotonic() - start_time) * 1000
            power = info["power"]
            ssid = info["ssid"]

            if not power:
                status_msg = "Wi-Fi is currently off."
            elif ssid:
                status_msg = f"Wi-Fi is on and connected to '{ssid}'."
            else:
                status_msg = "Wi-Fi is on, but you're not connected to a Wi-Fi network."

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=status_msg,
                command_name="Get WiFi Status",
                category=CommandCategory.NETWORK,
                details=info,
                execution_time_ms=elapsed_ms,
            )

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start_time) * 1000
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"WiFi operation failed: {exc}",
            command_name="WiFi Control",
            category=CommandCategory.NETWORK,
            error=str(exc),
            execution_time_ms=elapsed_ms,
        )

    elapsed_ms = (time.monotonic() - start_time) * 1000
    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown WiFi action: {action}",
        command_name="WiFi Control",
        category=CommandCategory.NETWORK,
        execution_time_ms=elapsed_ms,
    )
