"""Verification of newly connected capabilities and Task Agent registry in NOVA V3.5."""

from core.task_agent.models import TaskContext
from core.task_agent.registry import capability_registry
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent
from intent.router import RoutingDomain, get_routing_domain


class TestCapabilityRegistryV35:
    """Test that all newly connected capabilities are registered in CapabilityRegistry."""

    def test_registered_capability_names(self):
        expected_caps = [
            "fs.create_folder",
            "fs.create_file",
            "fs.open_folder",
            "fs.safe_move_to_trash",
            "doc.write_and_open",
            "app.launch",
            "browser.open_site",
            "browser.search_web",
            "browser.search_site",
            "visual.click_element",
            "visual.type_text",
            "visual.close_popup",
            "camera.open_camera",
            "camera.take_photo",
            "clipboard.get",
            "clipboard.set",
            "clipboard.clear",
            "system.wifi",
            "system.bluetooth",
            "screen.record_start",
            "screen.record_stop",
        ]
        for cap_name in expected_caps:
            assert capability_registry.has(cap_name), f"Missing capability in registry: {cap_name}"

    def test_clipboard_capability_execution(self):
        set_cap = capability_registry.get("clipboard.set")
        get_cap = capability_registry.get("clipboard.get")
        clear_cap = capability_registry.get("clipboard.clear")
        assert set_cap is not None
        assert get_cap is not None
        assert clear_cap is not None

        ctx = TaskContext(task_id="test-task-1")
        # Test clear
        res_clear = clear_cap.handler({}, ctx)
        assert res_clear["success"] is True

        # Test set
        res_set = set_cap.handler({"text": "NOVA Test Clipboard Content"}, ctx)
        assert res_set["success"] is True

        # Test get
        res_get = get_cap.handler({}, ctx)
        assert res_get["success"] is True
        assert res_get["text"] == "NOVA Test Clipboard Content"

    def test_routing_domains_v35(self):
        engine = NaturalLanguageIntentEngine()

        # Camera
        act = engine.parse("Open camera", allow_ai_fallback=False)
        assert act.intent == CanonicalIntent.OPEN_CAMERA
        assert get_routing_domain(act.intent) == RoutingDomain.DESKTOP_APP

        act = engine.parse("Take a photo", allow_ai_fallback=False)
        assert act.intent == CanonicalIntent.TAKE_PHOTO
        assert get_routing_domain(act.intent) == RoutingDomain.DESKTOP_APP

        # Clipboard
        act = engine.parse("What is in my clipboard?", allow_ai_fallback=False)
        assert act.intent == CanonicalIntent.GET_CLIPBOARD
        assert get_routing_domain(act.intent) == RoutingDomain.SYSTEM

        # Wi-Fi
        act = engine.parse("Turn off Wi-Fi", allow_ai_fallback=False)
        assert act.intent == CanonicalIntent.CONTROL_WIFI
        assert get_routing_domain(act.intent) == RoutingDomain.SYSTEM

        # Bluetooth
        act = engine.parse("Turn on Bluetooth", allow_ai_fallback=False)
        assert act.intent == CanonicalIntent.CONTROL_BLUETOOTH
        assert get_routing_domain(act.intent) == RoutingDomain.SYSTEM

        # Lock Screen
        act = engine.parse("Lock screen", allow_ai_fallback=False)
        assert act.intent == CanonicalIntent.LOCK_SCREEN
        assert get_routing_domain(act.intent) == RoutingDomain.SYSTEM
