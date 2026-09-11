"""Automated test suite for NOVA Operations Control Center Log Viewer Feed."""

import time
import pytest
from core.logger import get_logger, setup_logging
from ui.health_checker import DashboardStatsManager, LogEntry
from ui.terminal_dashboard import TerminalDashboard


def test_log_entry_dataclass():
    """Verify LogEntry attributes, level normalization, and backwards compatibility."""
    now = time.time()
    entry = LogEntry(timestamp=now, level="INFO", message="Microphone stream started", logger_name="voice")
    
    assert entry.level == "INFO"
    assert entry.message == "Microphone stream started"
    assert entry.logger_name == "voice"
    assert len(entry.time_str) == 8  # HH:MM:SS format
    assert "[INFO]" in entry.formatted_line()

    # Backwards compatibility: tuple unpacking
    lvl, msg = entry
    assert lvl == "INFO"
    assert msg == "Microphone stream started"


def test_dashboard_stats_manager_operations():
    """Verify add_log, level filtering, search, clear, and text export."""
    DashboardStatsManager.clear_logs()
    assert len(DashboardStatsManager.get_logs()) == 0

    DashboardStatsManager.add_log("INFO", "Subsystem initialized")
    DashboardStatsManager.add_log("WARNING", "Gemini API quota exceeded: check billing details")
    DashboardStatsManager.add_log("ERROR", "Browser executor connection refused at port 9222")
    DashboardStatsManager.add_log("SUCCESS", "Action completed successfully")
    DashboardStatsManager.add_log("DEBUG", "Intent matched: browser.open")

    all_logs = DashboardStatsManager.get_logs()
    assert len(all_logs) == 5

    # Filter WARN
    warns = DashboardStatsManager.get_logs(level_filter="WARN")
    assert len(warns) == 1
    assert "quota" in warns[0].message

    # Filter ERROR
    errs = DashboardStatsManager.get_logs(level_filter="ERROR")
    assert len(errs) == 1
    assert "Browser executor" in errs[0].message

    # Text Search
    search_res = DashboardStatsManager.get_logs(search_query="billing")
    assert len(search_res) == 1
    assert search_res[0].level == "WARN"

    # Text Export
    exported = DashboardStatsManager.get_logs_as_text()
    assert "Subsystem initialized" in exported
    assert "[ERROR]" in exported

    # Clear logs
    DashboardStatsManager.clear_logs()
    assert len(DashboardStatsManager.get_logs()) == 0


def test_terminal_dashboard_controls():
    """Verify TerminalDashboard layout rendering, scrolling, auto-scroll pausing, filter cycling, and maximize."""
    DashboardStatsManager.clear_logs()
    for i in range(20):
        DashboardStatsManager.add_log("INFO", f"Event log sequence #{i+1}")

    dashboard = TerminalDashboard()
    assert dashboard.auto_scroll is True
    assert dashboard.scroll_offset == 0

    # Draw dashboard
    dashboard.draw_dashboard()

    # Scroll up pauses auto-scroll
    dashboard.scroll_up(5)
    assert dashboard.auto_scroll is False
    assert dashboard.scroll_offset == 5

    # Jump to latest resumes auto-scroll
    dashboard.jump_to_latest()
    assert dashboard.auto_scroll is True
    assert dashboard.scroll_offset == 0

    # Filter cycling
    f1 = dashboard.cycle_filter()
    assert f1 != "ALL"
    assert dashboard.level_filter == f1

    # Maximize mode toggle
    is_max = dashboard.toggle_maximize()
    assert is_max is True
    assert dashboard.maximized is True

    # Restore standard view
    is_max_restored = dashboard.toggle_maximize()
    assert is_max_restored is False
    assert dashboard.maximized is False


def test_core_logger_dashboard_handler():
    """Verify core logger routes messages and full exception tracebacks to DashboardStatsManager."""
    DashboardStatsManager.clear_logs()
    test_logger = get_logger("nova.test")

    test_logger.info("Test info message from logger")
    try:
        raise ValueError("Simulated diagnostic error for logger")
    except Exception:
        test_logger.error("Exception occurred during execution", exc_info=True)

    logs = DashboardStatsManager.get_logs()
    assert len(logs) >= 2
    err_log = [l for l in logs if l.level == "ERROR"][0]
    assert "Exception occurred" in err_log.message
    assert "ValueError: Simulated diagnostic error" in err_log.message
