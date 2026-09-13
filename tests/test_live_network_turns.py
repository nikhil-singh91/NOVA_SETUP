"""Live end-to-end turn verification for network control commands."""

import unittest

from main import NovaApplication, TurnRequest
from ui.health_checker import DashboardStatsManager


class TestLiveNetworkTurns(unittest.TestCase):

    def setUp(self):
        self.app = NovaApplication()
        self.app._delivered = []
        self.app._deliver_response = lambda text, tid: self.app._delivered.append(text)
        DashboardStatsManager.clear_logs()

    def test_turn_wifi_ssid(self):
        """User: 'What Wi-Fi am I connected to?'"""
        req = TurnRequest(text="What Wi-Fi am I connected to?", source="text")
        self.app._process_turn(req)
        self.assertTrue(len(self.app._delivered) > 0)
        resp = self.app._delivered[-1]
        print(f"[TURN RESULT] 'What Wi-Fi am I connected to?' -> '{resp}'")
        self.assertIn("connected to", resp.lower())

        stats = DashboardStatsManager.get_all()
        self.assertEqual(stats["mac_intent"], "network.wifi")
        self.assertEqual(stats["command_status"], "SUCCESS")

    def test_turn_bluetooth_status(self):
        """User: 'Is my Bluetooth on?'"""
        req = TurnRequest(text="Is my Bluetooth on?", source="text")
        self.app._process_turn(req)
        self.assertTrue(len(self.app._delivered) > 0)
        resp = self.app._delivered[-1]
        print(f"[TURN RESULT] 'Is my Bluetooth on?' -> '{resp}'")
        self.assertIn("bluetooth is", resp.lower())

        stats = DashboardStatsManager.get_all()
        self.assertEqual(stats["mac_intent"], "network.bluetooth")
        self.assertEqual(stats["command_status"], "SUCCESS")

    def test_turn_bluetooth_devices(self):
        """User: 'What Bluetooth device is connected?'"""
        req = TurnRequest(text="What Bluetooth device is connected?", source="text")
        self.app._process_turn(req)
        self.assertTrue(len(self.app._delivered) > 0)
        resp = self.app._delivered[-1]
        print(f"[TURN RESULT] 'What Bluetooth device is connected?' -> '{resp}'")
        self.assertTrue("bluetooth" in resp.lower() or "connected" in resp.lower())

        stats = DashboardStatsManager.get_all()
        self.assertEqual(stats["mac_intent"], "network.bluetooth")
        self.assertEqual(stats["command_status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
