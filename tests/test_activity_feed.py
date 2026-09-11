"""Comprehensive automated test suite for NOVA Live User Activity Feed."""

import time
import pytest
from ui.health_checker import ActivityInteraction, ActivityStep, DashboardStatsManager
from ui.terminal_dashboard import TerminalDashboard


def test_activity_step_and_interaction_models():
    """Verify ActivityStep and ActivityInteraction data models."""
    now = time.time()
    step_you = ActivityStep(category="YOU", text="What is the capital of India?", timestamp=now)
    step_nova = ActivityStep(category="NOVA", text="New Delhi is the capital of India.", timestamp=now)
    step_result = ActivityStep(category="RESULT", text="Conversation completed", timestamp=now, success=True)

    interaction = ActivityInteraction(
        interaction_id="turn_test_1",
        timestamp=now,
        user_query="What is the capital of India?",
        nova_response="New Delhi is the capital of India.",
        result_message="Conversation completed",
        result_success=True,
        steps=[step_you, step_nova, step_result],
        status="COMPLETED",
    )

    assert len(interaction.steps) == 3
    assert interaction.steps[0].category == "YOU"
    assert interaction.steps[1].category == "NOVA"
    assert interaction.steps[2].category == "RESULT"
    assert interaction.status == "COMPLETED"


def test_example_1_normal_conversation():
    """Example 1: Normal conversation turn."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("What is the capital of India?")
    DashboardStatsManager.record_understood("Conversational Query")
    DashboardStatsManager.record_nova("New Delhi is the capital of India.")
    DashboardStatsManager.record_result("Conversation completed", success=True)

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 1
    inter = interactions[0]
    assert inter.user_query == "What is the capital of India?"
    assert inter.nova_response == "New Delhi is the capital of India."
    assert inter.result_message == "Conversation completed"
    assert inter.result_success is True


def test_example_2_open_application():
    """Example 2: Open application."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("Open Sublime Text")
    DashboardStatsManager.record_understood("Open Application", details={"Target": "Sublime Text"})
    DashboardStatsManager.record_action("Opening Sublime Text")
    DashboardStatsManager.record_result("✓ Sublime Text opened successfully", success=True)

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 1
    inter = interactions[0]
    assert inter.user_query == "Open Sublime Text"
    assert inter.understood_intent == "Open Application"
    assert inter.understood_details.get("Target") == "Sublime Text"
    assert "Opening Sublime Text" in inter.actions
    assert "✓ Sublime Text opened successfully" in inter.result_message


def test_example_3_close_application():
    """Example 3: Close application."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("Close Sublime Text")
    DashboardStatsManager.record_understood("Close Application", details={"Target": "Sublime Text"})
    DashboardStatsManager.record_action("Closing Sublime Text")
    DashboardStatsManager.record_result("✓ Sublime Text closed", success=True)

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 1
    inter = interactions[0]
    assert inter.user_query == "Close Sublime Text"
    assert inter.understood_intent == "Close Application"
    assert "Closing Sublime Text" in inter.actions


def test_example_4_screenshot():
    """Example 4: Screenshot capture."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("Take a screenshot")
    DashboardStatsManager.record_understood("Screenshot")
    DashboardStatsManager.record_action("Capturing screen")
    DashboardStatsManager.record_result("✓ Screenshot captured\nSaved to: ~/Desktop/nova_screenshot.png", success=True)

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 1
    inter = interactions[0]
    assert inter.user_query == "Take a screenshot"
    assert "Capturing screen" in inter.actions
    assert "Saved to:" in inter.result_message


def test_example_5_screen_recording():
    """Example 5: Screen recording start and stop."""
    DashboardStatsManager.clear_logs()

    # Start recording
    DashboardStatsManager.start_interaction("Start the screen recording")
    DashboardStatsManager.record_understood("Start Screen Recording")
    DashboardStatsManager.record_action("Starting screen recording")
    DashboardStatsManager.record_result("● Screen recording started", success=True)

    # Stop recording
    DashboardStatsManager.start_interaction("Stop the screen recording")
    DashboardStatsManager.record_understood("Stop Screen Recording")
    DashboardStatsManager.record_action("Stopping screen recording")
    DashboardStatsManager.record_result("✓ Screen recording stopped", success=True)

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 2
    assert interactions[0].user_query == "Start the screen recording"
    assert interactions[1].user_query == "Stop the screen recording"


def test_example_6_browser_search():
    """Example 6: Browser search."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("Go to Flipkart and search for mobile phones")
    DashboardStatsManager.record_understood(
        "Browser Task",
        details={"Website": "Flipkart", "Task": "Search", "Query": "mobile phones"},
    )
    DashboardStatsManager.record_action("Opening Flipkart")
    DashboardStatsManager.record_action('Searching for "mobile phones"')
    DashboardStatsManager.record_nova("I found the Flipkart search page.")
    DashboardStatsManager.record_result("✓ Search completed", success=True)

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 1
    inter = interactions[0]
    assert inter.understood_details.get("Website") == "Flipkart"
    assert inter.understood_details.get("Query") == "mobile phones"
    assert len(inter.actions) == 2


def test_example_7_multistep_task():
    """Example 7: Multi-step desktop task."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction(
        "Open VS Code, create a folder on Desktop called DSA, and create a.cpp"
    )
    DashboardStatsManager.record_understood(
        "Multi-step task",
        details={"Steps": ["Open VS Code", "Create folder ~/Desktop/DSA", "Create ~/Desktop/DSA/a.cpp"]},
    )
    DashboardStatsManager.record_action("Opening VS Code", step_num=1, total_steps=3)
    DashboardStatsManager.record_result("✓ VS Code opened", success=True)

    DashboardStatsManager.record_action("Creating folder: ~/Desktop/DSA", step_num=2, total_steps=3)
    DashboardStatsManager.record_result("✓ Folder created", success=True)

    DashboardStatsManager.record_action("Creating: ~/Desktop/DSA/a.cpp", step_num=3, total_steps=3)
    DashboardStatsManager.record_result("✓ File created", success=True)

    DashboardStatsManager.record_result("✓ 3/3 steps completed", success=True)

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 1
    inter = interactions[0]
    assert len(inter.actions) == 3
    assert inter.status == "COMPLETED"


def test_example_8_unrecognized_intent():
    """Example 8: Unrecognized command handling."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("Random unclear utterance")
    DashboardStatsManager.record_understood("Intent could not be determined")
    DashboardStatsManager.record_nova("I didn't understand that. Could you say it another way?")
    DashboardStatsManager.record_result("⚠ Command not executed", success=False)

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 1
    inter = interactions[0]
    assert inter.understood_intent == "Intent could not be determined"
    assert inter.result_success is False


def test_example_9_action_failure():
    """Example 9: Action failure with clear message."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("Open DSA folder")
    DashboardStatsManager.record_understood("Open Folder", details={"Target": "DSA", "Location": "Desktop"})
    DashboardStatsManager.record_action("Searching Desktop for DSA")
    DashboardStatsManager.record_result("✗ Folder not found", success=False)
    DashboardStatsManager.record_nova("I couldn't find the DSA folder on your Desktop.")

    interactions = DashboardStatsManager.get_activity_interactions()
    assert len(interactions) == 1
    inter = interactions[0]
    assert inter.result_success is False
    assert "✗ Folder not found" in inter.result_message


def test_activity_filtering_and_search():
    """Verify filtering by category and search queries."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("Open YouTube and search for Kesariya")
    DashboardStatsManager.record_understood("Browser Task", details={"Website": "YouTube", "Query": "Kesariya"})
    DashboardStatsManager.record_action("Opening YouTube")
    DashboardStatsManager.record_nova("Playing Kesariya on YouTube.")
    DashboardStatsManager.record_result("✓ Completed", success=True)

    DashboardStatsManager.start_interaction("What is the weather today?")
    DashboardStatsManager.record_understood("Conversational Query")
    DashboardStatsManager.record_nova("The weather is currently clear and 22 degrees.")
    DashboardStatsManager.record_result("Conversation completed", success=True)

    # Search for Kesariya
    res_kesariya = DashboardStatsManager.get_activity_interactions(search_query="Kesariya")
    assert len(res_kesariya) == 1
    assert "Kesariya" in res_kesariya[0].user_query

    # Filter by YOU
    steps_you = DashboardStatsManager.get_activity_steps(filter_category="YOU")
    assert len(steps_you) == 2

    # Filter by NOVA
    steps_nova = DashboardStatsManager.get_activity_steps(filter_category="NOVA")
    assert len(steps_nova) == 2


def test_terminal_dashboard_activity_rendering():
    """Verify TerminalDashboard renders the activity feed properly without raw developer clutter."""
    DashboardStatsManager.clear_logs()

    DashboardStatsManager.start_interaction("Now go to Flipkart and search mobile phones")
    DashboardStatsManager.record_understood("Browser Task", details={"Website": "Flipkart", "Query": "mobile phones"})
    DashboardStatsManager.record_action("Opening Flipkart...")
    DashboardStatsManager.record_action('Searching for "mobile phones"...')
    DashboardStatsManager.record_nova("I found the Flipkart search page.")
    DashboardStatsManager.record_result("✓ Task completed", success=True)

    dashboard = TerminalDashboard()
    assert dashboard.filter_mode == "ACTIVITY"
    assert dashboard.auto_scroll is True

    # Draw dashboard
    dashboard.draw_dashboard()

    # Cycle filter
    next_f = dashboard.cycle_filter()
    assert next_f == "YOU"
    assert dashboard.filter_mode == "YOU"

    # Switch to debug mode
    dashboard.set_filter_mode("DEBUG")
    assert dashboard.filter_mode == "DEBUG"
    dashboard.draw_dashboard()

    # Return to activity mode
    dashboard.set_filter_mode("ACTIVITY")
    assert dashboard.filter_mode == "ACTIVITY"
    dashboard.draw_dashboard()
