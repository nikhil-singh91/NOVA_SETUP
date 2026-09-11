"""Automated tests for NOVA UI V1 backend integration layer, event bridge, and command gateway."""

from __future__ import annotations

import json
import time
import pytest
from core.event_bus import EventBus, NovaEvent
from ui.backend.models import AvatarState, CommandRequest, UIEvent, UIEventType
from ui.backend.event_bridge import EventBridge
from ui.backend.command_gateway import CommandGateway
from ui.backend.server import NovaUIServer


class TestBackendUIIntegration:
    """Test suite for UI event bridge, command gateway, and server endpoints."""

    def test_avatar_state_enum(self):
        expected_states = [
            "idle", "listening", "thinking", "planning",
            "executing", "verifying", "speaking", "success",
            "confused", "error", "offline"
        ]
        for state in expected_states:
            assert AvatarState(state) is not None

    def test_event_bridge_sanitization(self):
        bridge = EventBridge()
        unsafe_payload = {
            "api_key": "sk-proj-secret123456",
            "user_token": "bearer-token-secret",
            "password": "my_super_secret_password",
            "safe_text": "Hello NOVA",
            "nested": {
                "credential": "private_key_data",
                "normal_field": 42
            }
        }
        cleaned = bridge._sanitize_dict(unsafe_payload)
        assert cleaned["api_key"] == "******"
        assert cleaned["user_token"] == "******"
        assert cleaned["password"] == "******"
        assert cleaned["safe_text"] == "Hello NOVA"
        assert cleaned["nested"]["credential"] == "******"
        assert cleaned["nested"]["normal_field"] == 42

    def test_event_bridge_event_mapping(self):
        bus = EventBus()
        bridge = EventBridge(event_bus=bus)

        # Trigger application start
        bus.publish(NovaEvent.APPLICATION_STARTED, message="Testing start")
        assert len(bridge.activity_history) > 0
        assert bridge.activity_history[-1]["event_type"] == UIEventType.NOVA_STARTED.value

        # Trigger speaking start
        bus.publish(NovaEvent.SPEAKING_STARTED, message="Speaking test")
        assert bridge.current_avatar_state == AvatarState.SPEAKING

    def test_command_gateway_validation(self):
        gw = CommandGateway()
        # Empty text rejection
        empty_req = CommandRequest(text="   ")
        resp = gw.submit_command(empty_req)
        assert not resp.accepted
        assert resp.status == "rejected"

        # Valid text acceptance
        valid_req = CommandRequest(text="Open VS Code")
        resp_valid = gw.submit_command(valid_req)
        assert resp_valid.accepted
        assert resp_valid.status in ["queued", "processing"]

    def test_command_gateway_cancellation(self):
        gw = CommandGateway()
        res = gw.cancel_active_tasks()
        assert res["success"] is True

    def test_ui_server_permissions_check(self):
        server = NovaUIServer()
        perms = server._check_system_permissions()
        assert "permissions" in perms
        assert "accessibility" in perms["permissions"]
        assert "microphone" in perms["permissions"]
        assert "screen_recording" in perms["permissions"]
