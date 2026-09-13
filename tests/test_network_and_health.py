"""Comprehensive test suite for Phase 13 test matrix:
1. Bluetooth status, control, and connected-device discovery.
2. Wi-Fi status, control, SSID, and network details.
3. Provider health checks, real error classification, and metrics.
4. System alerts and automatic recovery.
5. Natural-language variant normalization.
6. Mac Control and Activity Feed telemetry.
"""

import unittest

from intent.matcher import LinguisticIntentMatcher
from intent.models import CanonicalIntent
from mac_control.actions.bluetooth import (
    execute_bluetooth_command,
    get_bluetooth_power_state,
    get_connected_bluetooth_devices,
)
from mac_control.actions.wifi import (
    execute_wifi_command,
    get_connected_ssid,
    get_network_details,
    get_wifi_interface,
    get_wifi_power_state,
)
from mac_control.models import ExecutionStatus
from providers.provider_manager import classify_provider_error
from ui.health_checker import DashboardStatsManager


class TestNetworkAndHealth(unittest.TestCase):

    def setUp(self):
        DashboardStatsManager.clear_logs()
        DashboardStatsManager.update("mac_intent", "None")
        DashboardStatsManager.update("mac_target", "None")
        DashboardStatsManager.update("command_status", "IDLE")
        DashboardStatsManager.update("mac_result", "None")

    # =========================================================================
    # 1. Real macOS Wi-Fi Tests
    # =========================================================================

    def test_wifi_interface_discovery(self):
        """Verify dynamic Wi-Fi interface discovery (e.g. en0)."""
        iface = get_wifi_interface()
        self.assertIsNotNone(iface, "Wi-Fi interface should be discovered on macOS")
        self.assertTrue(iface.startswith("en"), f"Interface {iface} should be a valid enX device")

    def test_wifi_power_state_detection(self):
        """Verify real Wi-Fi power state is ON or OFF (never UNKNOWN or fake)."""
        state = get_wifi_power_state()
        self.assertIn(state, ("ON", "OFF"), f"Real power state should be ON or OFF, got {state}")

    def test_wifi_connected_ssid_detection(self):
        """Verify real SSID is retrieved when Wi-Fi is connected."""
        power = get_wifi_power_state()
        if power == "ON":
            ssid = get_connected_ssid()
            # If connected, verify SSID is not empty and not "None"
            if ssid:
                self.assertIsInstance(ssid, str)
                self.assertTrue(len(ssid) > 0)
                print(f"[TEST] Real active Wi-Fi SSID detected: '{ssid}'")

    def test_wifi_network_details(self):
        """Verify detailed network diagnostics return structured dictionary with real values."""
        details = get_network_details()
        self.assertIn("power", details)
        self.assertIn("interface", details)
        self.assertIn("ssid", details)
        self.assertIn("local_ip", details)
        self.assertIn("gateway", details)
        self.assertIn("internet_reachable", details)
        print(f"[TEST] Network details: power={details['power']}, iface={details['interface']}, ssid={details['ssid']}, ip={details['local_ip']}, inet={details['internet_reachable']}")

    def test_wifi_command_execution(self):
        """Verify execute_wifi_command handles status, ssid, and details."""
        res_status = execute_wifi_command("status")
        self.assertEqual(res_status.status, ExecutionStatus.SUCCESS)
        self.assertIn("Wi-Fi is", res_status.message)
        self.assertGreater(res_status.execution_time_ms, 0)

        res_ssid = execute_wifi_command("ssid")
        self.assertEqual(res_ssid.status, ExecutionStatus.SUCCESS)

        res_details = execute_wifi_command("details")
        self.assertEqual(res_details.status, ExecutionStatus.SUCCESS)
        self.assertIn("local_ip", res_details.details)

    # =========================================================================
    # 2. Real macOS Bluetooth Tests
    # =========================================================================

    def test_bluetooth_power_state_detection(self):
        """Verify real Bluetooth power state using IOBluetooth preference."""
        state = get_bluetooth_power_state()
        self.assertIn(state, ("ON", "OFF"), f"Bluetooth power state must be ON or OFF, got {state}")
        print(f"[TEST] Real Bluetooth power state: {state}")

    def test_bluetooth_connected_devices(self):
        """Verify real connected Bluetooth device discovery via IOBluetoothDevice."""
        devices, err = get_connected_bluetooth_devices()
        self.assertIsNone(err, f"Connected device discovery should not error: {err}")
        self.assertIsInstance(devices, list)
        print(f"[TEST] Real connected Bluetooth devices ({len(devices)}): {devices}")

    def test_bluetooth_command_execution(self):
        """Verify execute_bluetooth_command handles status and devices query."""
        res_status = execute_bluetooth_command("status")
        self.assertEqual(res_status.status, ExecutionStatus.SUCCESS)
        self.assertIn("power", res_status.details)
        self.assertGreater(res_status.execution_time_ms, 0)

        res_devices = execute_bluetooth_command("devices")
        self.assertEqual(res_devices.status, ExecutionStatus.SUCCESS)
        self.assertIn("devices", res_devices.details)

    # =========================================================================
    # 3. Intent Normalization & Natural Language Variants
    # =========================================================================

    def test_natural_language_wifi_variants(self):
        """Verify diverse natural language variants map to CONTROL_WIFI."""
        matcher = LinguisticIntentMatcher()
        queries = [
            ("Is Wi-Fi on?", "status"),
            ("Check Wi-Fi", "status"),
            ("What Wi-Fi am I connected to?", "ssid"),
            ("Which network am I using?", "ssid"),
            ("What is my network status?", "details"),
            ("Am I connected to the internet?", "details"),
            ("Turn Wi-Fi off", "off"),
            ("Disable Wi-Fi", "off"),
            ("Switch Wi-Fi off", "off"),
            ("Turn Wi-Fi on", "on"),
            ("Enable Wi-Fi", "on"),
            ("Nova, check my Wi-Fi", "status"),
            ("Now check my Wi-Fi", "status"),
            ("Hey Nova, what Wi-Fi am I connected to?", "ssid"),
            ("Now turn Wi-Fi off", "off"),
        ]

        for q, expected_action in queries:
            action = matcher.match(q)
            self.assertIsNotNone(action, f"Failed to match query: '{q}'")
            self.assertEqual(action.intent, CanonicalIntent.CONTROL_WIFI, f"Query '{q}' should be CONTROL_WIFI")
            self.assertEqual(action.parameters.get("action"), expected_action, f"Query '{q}' should have action '{expected_action}'")

    def test_natural_language_bluetooth_variants(self):
        """Verify diverse natural language variants map to CONTROL_BLUETOOTH."""
        matcher = LinguisticIntentMatcher()
        queries = [
            ("Is Bluetooth on?", "status"),
            ("Check Bluetooth", "status"),
            ("What's my Bluetooth status?", "status"),
            ("What Bluetooth device is connected?", "devices"),
            ("Which Bluetooth devices are connected?", "devices"),
            ("What devices are connected through Bluetooth?", "devices"),
            ("Turn Bluetooth off", "off"),
            ("Disable Bluetooth", "off"),
            ("Turn Bluetooth on", "on"),
            ("Enable Bluetooth", "on"),
            ("Hey Nova, is my Bluetooth on?", "status"),
            ("Nova please turn Bluetooth off", "off"),
            ("Now turn Bluetooth on", "on"),
        ]

        for q, expected_action in queries:
            action = matcher.match(q)
            self.assertIsNotNone(action, f"Failed to match query: '{q}'")
            self.assertEqual(action.intent, CanonicalIntent.CONTROL_BLUETOOTH, f"Query '{q}' should be CONTROL_BLUETOOTH")
            self.assertEqual(action.parameters.get("action"), expected_action, f"Query '{q}' should have action '{expected_action}'")

    # =========================================================================
    # 4. Provider Error Classification & Health Telemetry
    # =========================================================================

    def test_provider_error_classification(self):
        """Verify exceptions are mapped to exact required status codes."""
        # 402 Payment Required / Quota
        e402 = Exception("Error code: 402 - {'error': {'message': 'Payment required', 'code': 'insufficient_quota'}}")
        status, reason, retry = classify_provider_error(e402)
        self.assertEqual(status, "QUOTA_EXCEEDED")
        self.assertIn("402", reason)

        # 429 Rate Limit
        e429 = Exception("Error code: 429 - {'error': {'message': 'Rate limit reached. Please retry in 23s'}}")
        status, reason, retry = classify_provider_error(e429)
        self.assertEqual(status, "RATE_LIMITED")
        self.assertIn("Rate limit", reason)
        self.assertIsNotNone(retry)

        # 401 Auth Error
        e401 = Exception("Error code: 401 - {'error': {'message': 'Invalid API Key'}}")
        status, reason, retry = classify_provider_error(e401)
        self.assertEqual(status, "AUTH_ERROR")

        # 403 Forbidden
        e403 = Exception("Error code: 403 - Forbidden")
        status, reason, retry = classify_provider_error(e403)
        self.assertEqual(status, "AUTH_ERROR")

        # Timeout
        etimeout = TimeoutError("Connection timed out after 5.0s")
        status, reason, retry = classify_provider_error(etimeout)
        self.assertEqual(status, "TIMEOUT")

        # Connection / Network error
        econn = ConnectionError("Failed to establish a new connection: [Errno 8] nodename nor servname provided")
        status, reason, retry = classify_provider_error(econn)
        self.assertEqual(status, "NETWORK_ERROR")

    # =========================================================================
    # 5. Alert System & Auto-Recovery
    # =========================================================================

    def test_alert_lifecycle_and_auto_recovery(self):
        """Verify alerts are raised with details and automatically removed on recovery."""
        # Step 1: Record failure
        DashboardStatsManager.record_provider_failure(
            "cerebras",
            status="RATE_LIMITED",
            error_msg="Payment required / Quota exhausted (HTTP 402)",
            latency_ms=320.0,
            retry_after=60.0,
        )

        active = DashboardStatsManager.get_active_alerts()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].subsystem, "PROVIDER")
        self.assertIn("Cerebras", active[0].title)
        self.assertIn("Payment required", active[0].details)

        # Step 2: Record recovery
        DashboardStatsManager.record_provider_success("cerebras", latency_ms=180.0)

        active_after = DashboardStatsManager.get_active_alerts()
        self.assertEqual(len(active_after), 0, "Alert should be auto-cleared when provider recovers")

        resolved = DashboardStatsManager.get_resolved_alerts()
        self.assertTrue(len(resolved) > 0)
        self.assertIn("Cerebras recovered", resolved[0].title)

    # =========================================================================
    # 6. Mac Control & Activity Feed Telemetry
    # =========================================================================

    def test_mac_control_and_activity_feed_telemetry(self):
        """Verify complete activity flow: YOU -> UNDERSTOOD -> ACTION -> RESULT."""
        # 1. Start interaction
        interaction = DashboardStatsManager.start_interaction("What Wi-Fi am I connected to?", source="voice")
        self.assertEqual(interaction.user_query, "What Wi-Fi am I connected to?")

        # 2. Record Understood
        DashboardStatsManager.record_understood(
            intent="network.wifi",
            details={"action": "ssid", "target": "wifi"},
        )

        # 3. Record Action
        DashboardStatsManager.record_action("Querying active Wi-Fi network...")

        # 4. Record Mac Action
        DashboardStatsManager.record_mac_action(
            command_text="What Wi-Fi am I connected to?",
            intent="network.wifi",
            target="wifi",
            status="SUCCESS",
            latency_ms=45.2,
            result_message="Connected to Hi-Tech_hostel",
        )

        # 5. Record Result & Nova response
        DashboardStatsManager.record_result("You are connected to Hi-Tech_hostel.", success=True)
        DashboardStatsManager.record_nova("You are connected to Hi-Tech_hostel.")

        # Verify Dashboard stats
        stats = DashboardStatsManager.get_all()
        self.assertEqual(stats["last_command"], "What Wi-Fi am I connected to?")
        self.assertEqual(stats["mac_intent"], "network.wifi")
        self.assertEqual(stats["command_status"], "SUCCESS")
        self.assertEqual(stats["mac_result"], "Connected to Hi-Tech_hostel")
        self.assertEqual(stats["mac_latency"], "45 ms")

        # Verify activity interaction steps
        steps = interaction.steps
        categories = [s.category for s in steps]
        self.assertEqual(categories, ["YOU", "UNDERSTOOD", "ACTION", "RESULT", "NOVA"])


if __name__ == "__main__":
    unittest.main()
