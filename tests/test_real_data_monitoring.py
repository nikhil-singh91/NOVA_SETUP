"""Automated test suite for NOVA Real System State & Control Center Telemetry."""

import time
import pytest
from ui.health_checker import DashboardStatsManager, SystemAlert
from ui.terminal_dashboard import TerminalDashboard
from providers.provider_manager import ProviderManager, ProviderRuntimeStatus


def test_provider_runtime_telemetry_and_quota_classification():
    """Verify provider error classification for quota limits, auth, timeouts, and offline states."""
    pm = ProviderManager()

    # 1. Quota Exceeded exception
    exc_quota = Exception("Gemini API request failed: You exceeded your current quota, please retry in 23s")
    status_cat, clean_msg, retry_sec = pm._classify_error(exc_quota)
    assert status_cat == "QUOTA EXCEEDED"
    assert "Quota" in clean_msg
    assert retry_sec == 23.0

    # 2. Rate Limit exception
    exc_rate = Exception("429 Too Many Requests: Rate limit reached. Retry in 15 seconds.")
    status_cat, clean_msg, retry_sec = pm._classify_error(exc_rate)
    assert status_cat == "RATE LIMITED"
    assert retry_sec == 15.0

    # 3. Auth error
    exc_auth = Exception("401 Unauthorized: Invalid API key provided.")
    status_cat, clean_msg, _ = pm._classify_error(exc_auth)
    assert status_cat == "ERROR"
    assert "API key" in clean_msg

    # 4. Network error
    exc_net = Exception("Connection refused / DNS lookup failed")
    status_cat, clean_msg, _ = pm._classify_error(exc_net)
    assert status_cat == "OFFLINE"


def test_provider_health_transition_and_recovery():
    """Verify dynamic provider status transitions: HEALTHY -> QUOTA EXCEEDED -> FALLBACK -> RECOVERED."""
    DashboardStatsManager.clear_logs()

    # 1. Initially Unknown/Healthy
    DashboardStatsManager.record_provider_success("gemini", latency_ms=450.0)
    stats = DashboardStatsManager.get_provider_stats()
    assert stats["gemini"]["status"] == "HEALTHY"
    assert stats["gemini"]["latency"] == "450 ms"
    assert DashboardStatsManager.get_active_alerts() == []

    # 2. Gemini hits Quota Exceeded error
    DashboardStatsManager.record_provider_failure(
        "gemini",
        status="QUOTA EXCEEDED",
        error_msg="You exceeded your current quota",
        latency_ms=617.0,
        retry_after=23.0,
    )
    stats = DashboardStatsManager.get_provider_stats()
    assert stats["gemini"]["status"] == "QUOTA EXCEEDED"
    assert stats["gemini"]["latency"] == "617 ms"
    assert stats["gemini"]["retry_after"] == "23s"

    # Verify active alert was created
    alerts = DashboardStatsManager.get_active_alerts()
    assert len(alerts) == 1
    assert alerts[0].title == "Gemini quota exceeded"
    assert alerts[0].subsystem == "PROVIDER"
    assert alerts[0].retry_after == 23.0

    # 3. Fallback to Groq succeeds
    DashboardStatsManager.record_provider_success(
        "groq",
        latency_ms=67.0,
        fallback_used=True,
        primary_failed="gemini",
    )
    stats = DashboardStatsManager.get_provider_stats()
    all_stats = DashboardStatsManager.get_all()
    assert stats["groq"]["status"] == "HEALTHY"
    assert stats["groq"]["latency"] == "67 ms"
    assert all_stats["active_provider"] == "Groq"
    assert all_stats["fallback_active"] is True
    assert all_stats["fallback_provider"] == "Groq"
    assert all_stats["primary_failed_provider"] == "Gemini"

    # 4. Gemini later succeeds and recovers
    DashboardStatsManager.record_provider_success("gemini", latency_ms=380.0)
    stats = DashboardStatsManager.get_provider_stats()
    assert stats["gemini"]["status"] == "HEALTHY"
    assert stats["gemini"]["latency"] == "380 ms"
    assert stats["gemini"]["last_error"] is None

    # Verify alert moved to resolved history
    assert DashboardStatsManager.get_active_alerts() == []
    resolved = DashboardStatsManager.get_resolved_alerts()
    assert len(resolved) >= 1
    assert "Gemini recovered" in resolved[0].title


def test_mac_control_real_execution_telemetry():
    """Verify Mac Control panel records real command names, intents, latencies, and execution outcomes."""
    DashboardStatsManager.clear_logs()

    # 1. Execute Open YouTube
    DashboardStatsManager.record_mac_action(
        command_text="Open YouTube",
        intent="application.open",
        target="YouTube",
        status="SUCCESS",
        latency_ms=245.0,
        result_message="YouTube opened successfully",
    )

    all_stats = DashboardStatsManager.get_all()
    assert all_stats["last_command"] == "Open YouTube"
    assert all_stats["mac_intent"] == "application.open"
    assert all_stats["mac_target"] == "YouTube"
    assert all_stats["command_status"] == "SUCCESS"
    assert all_stats["mac_latency"] == "245 ms"
    assert all_stats["mac_result"] == "YouTube opened successfully"

    # 2. Execute Volume Increase
    DashboardStatsManager.record_mac_action(
        command_text="Increase volume",
        intent="system.volume.increase",
        target="Volume Up",
        status="SUCCESS",
        latency_ms=85.0,
        result_message="Volume set to 70%",
    )

    all_stats = DashboardStatsManager.get_all()
    assert all_stats["last_command"] == "Increase volume"
    assert all_stats["mac_result"] == "Volume set to 70%"

    # 3. Failed command execution
    DashboardStatsManager.record_mac_action(
        command_text="Open DSA folder",
        intent="filesystem.folder.open",
        target="DSA",
        status="FAILED",
        latency_ms=110.0,
        result_message="Could not find folder DSA on Desktop",
    )

    all_stats = DashboardStatsManager.get_all()
    assert all_stats["last_command"] == "Open DSA folder"
    assert all_stats["command_status"] == "FAILED"
    assert all_stats["mac_result"] == "Could not find folder DSA on Desktop"

    # Verify recent Mac actions history
    recent = DashboardStatsManager.get_recent_mac_actions()
    assert len(recent) == 3
    assert recent[0]["command"] == "Open DSA folder"
    assert recent[0]["status"] == "FAILED"
    assert recent[1]["command"] == "Increase volume"
    assert recent[2]["command"] == "Open YouTube"


def test_mac_control_access_permission_check():
    """Verify real macOS permission check returns valid status string."""
    status = DashboardStatsManager.check_mac_control_access()
    assert status in ("GRANTED", "LIMITED", "DENIED (Accessibility required)", "LIMITED (Non-macOS)", "UNKNOWN")


def test_terminal_dashboard_real_data_rendering():
    """Verify TerminalDashboard renders all real monitoring cards properly without errors."""
    DashboardStatsManager.clear_logs()

    # Populate real test state
    DashboardStatsManager.record_provider_failure(
        "gemini",
        status="QUOTA EXCEEDED",
        error_msg="You exceeded your current quota",
        latency_ms=620.0,
        retry_after=23.0,
    )
    DashboardStatsManager.record_provider_success(
        "groq",
        latency_ms=67.0,
        fallback_used=True,
        primary_failed="gemini",
    )
    DashboardStatsManager.record_mac_action(
        command_text="Increase volume",
        intent="system.volume.increase",
        target="Volume Up",
        status="SUCCESS",
        latency_ms=85.0,
        result_message="Volume set to 70%",
    )

    dashboard = TerminalDashboard()
    dashboard.draw_dashboard()

    # Verify no exceptions and state preserved
    assert dashboard.filter_mode == "ACTIVITY"
    assert DashboardStatsManager.get_all()["fallback_active"] is True
