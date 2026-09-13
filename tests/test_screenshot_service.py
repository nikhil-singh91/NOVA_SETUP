"""Unit and regression tests for NOVA Centralized Screenshot Action System."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from core.screenshot import ScreenshotResult, ScreenshotService, screenshot_service
from core.task_agent.registry import capability_registry
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent
from mac_control.actions.screenshot import execute_screenshot_command
from mac_control.models import CommandCategory, ExecutionStatus, MacCommand


@pytest.fixture
def intent_engine() -> NaturalLanguageIntentEngine:
    return NaturalLanguageIntentEngine()


# ==============================================================================
# TEST 1: Service Initialization and Directory Management
# ==============================================================================

def test_screenshot_service_initialization(tmp_path: Path) -> None:
    """Validate ScreenshotService custom and default paths."""
    service = ScreenshotService(output_dir=tmp_path)
    assert service.output_dir == tmp_path

    # Default output dir should point to ~/Desktop/NOVA Screenshots
    expected_default = (Path.home() / "Desktop" / "NOVA Screenshots").resolve()
    assert screenshot_service.output_dir == expected_default


# ==============================================================================
# TEST 2: Unique Timestamped Filename Generation & Collision Handling
# ==============================================================================

def test_unique_filename_generation(tmp_path: Path) -> None:
    """Test timestamped and collision-safe file path generation."""
    service = ScreenshotService(output_dir=tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    # 1. Custom filename without collision
    p1 = service._generate_unique_filepath("custom_shot.png")
    assert p1.name == "custom_shot.png"
    p1.touch()

    # 2. Collision handling on custom filename
    p2 = service._generate_unique_filepath("custom_shot.png")
    assert p2.name == "custom_shot_1.png"
    p2.touch()

    p3 = service._generate_unique_filepath("custom_shot.png")
    assert p3.name == "custom_shot_2.png"

    # 3. Default timestamp format
    p_default = service._generate_unique_filepath()
    assert p_default.name.startswith("Screenshot_")
    assert p_default.name.endswith(".png")


# ==============================================================================
# TEST 3: Successful Screen Capture (Mocked Subprocess)
# ==============================================================================

def test_capture_full_screen_mocked(tmp_path: Path) -> None:
    """Test capture_full_screen lifecycle with mocked screencapture."""
    service = ScreenshotService(output_dir=tmp_path)

    def fake_screencapture(cmd, capture_output=True, text=True, timeout=5.0):
        # Last argument is the target file path
        target = Path(cmd[-1])
        target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # valid dummy PNG bytes
        return subprocess_result_mock(returncode=0)

    with patch("subprocess.run", side_effect=fake_screencapture):
        with patch.object(service, "check_permissions", return_value=(True, "Permissions verified.")):
            res: ScreenshotResult = service.capture_full_screen(custom_filename="test_capture.png")
            assert res.success is True
            assert res.file_path is not None
            assert res.file_path.exists()
            assert res.file_path.name == "test_capture.png"
            assert res.filename == "test_capture.png"
            assert res.error is None


# ==============================================================================
# TEST 4: Permission Denied Clean Failure Handling
# ==============================================================================

def test_permission_denied_handling(tmp_path: Path) -> None:
    """Test graceful failure and actionable error message when macOS permissions are denied."""
    service = ScreenshotService(output_dir=tmp_path)

    with patch.object(service, "check_permissions", return_value=(False, "macOS Screen Recording permission is missing.")):
        res = service.capture_full_screen()
        assert res.success is False
        assert res.error_type == "PERMISSION_DENIED"
        assert "Screen Recording permission is missing" in (res.error or "")
        assert res.file_path is None


# ==============================================================================
# TEST 5: Subprocess Failure & Empty File Handling
# ==============================================================================

def test_screencapture_failure_handling(tmp_path: Path) -> None:
    """Test screencapture non-zero exit and empty output handling."""
    service = ScreenshotService(output_dir=tmp_path)

    # 1. Non-zero exit code
    with patch("subprocess.run", return_value=subprocess_result_mock(returncode=1, stderr="screencapture error")):
        with patch.object(service, "check_permissions", return_value=(True, "OK")):
            res = service.capture_full_screen(custom_filename="fail.png")
            assert res.success is False
            assert "exited with code 1" in (res.error or "")

    # 2. 0-byte output file
    def fake_empty_screencapture(cmd, capture_output=True, text=True, timeout=5.0):
        target = Path(cmd[-1])
        target.touch()  # 0 bytes
        return subprocess_result_mock(returncode=0)

    with patch("subprocess.run", side_effect=fake_empty_screencapture):
        with patch.object(service, "check_permissions", return_value=(True, "OK")):
            res2 = service.capture_full_screen(custom_filename="empty.png")
            assert res2.success is False
            assert "empty or missing" in (res2.error or "")


# ==============================================================================
# TEST 6: Natural Language Variation Matrix (All User & Paraphrase Variations)
# ==============================================================================

@pytest.mark.parametrize(
    "phrase",
    [
        # Exact requested variations:
        "NOVA take a screenshot",
        "take a screenshot",
        "capture my screen",
        "capture the screen",
        "screenshot this",
        "take screen capture",
        "save what I am seeing",
        "capture what I am looking at",
        "take a picture of my screen",
        # Additional colloquial & natural variations:
        "Hey Nova, take a screenshot",
        "Nova, please capture my screen",
        "take screenshot",
        "capture screen",
        "save my screen",
        "save the screen",
        "snap my screen",
        "snap the screen",
        "snap a screenshot",
        "grab my screen",
        "grab the screen",
        "grab a screenshot",
        "take a photo of my screen",
        "take photo of my screen",
        "take picture of my screen",
        "take a snapshot of my screen",
        "take a snapshot of the screen",
        "snapshot this",
        "save what is on my screen",
        "save what's on my screen",
        "capture what is on my screen",
        "capture what's on my screen",
        # Bilingual / Hindi-English phrasing:
        "screenshot lo",
        "screenshot le lo",
        "screen ka screenshot lo",
        "screen capture karo",
        "screen ki photo lo",
    ],
)
def test_screenshot_natural_language_variations(intent_engine: NaturalLanguageIntentEngine, phrase: str) -> None:
    """Ensure all natural language variations map reliably to CanonicalIntent.SCREEN_CAPTURE."""
    action = intent_engine.parse(phrase)
    assert action.intent == CanonicalIntent.SCREEN_CAPTURE
    assert action.confidence >= 0.85


# ==============================================================================
# TEST 7: Disambiguation with Camera Photo Commands
# ==============================================================================

def test_camera_vs_screenshot_disambiguation(intent_engine: NaturalLanguageIntentEngine) -> None:
    """Ensure camera photo commands map to TAKE_PHOTO while screen picture commands map to SCREEN_CAPTURE."""
    # Camera commands
    cam_act1 = intent_engine.parse("take a picture")
    assert cam_act1.intent == CanonicalIntent.TAKE_PHOTO

    cam_act2 = intent_engine.parse("take a photo")
    assert cam_act2.intent == CanonicalIntent.TAKE_PHOTO

    # Screen picture commands
    screen_act1 = intent_engine.parse("take a picture of my screen")
    assert screen_act1.intent == CanonicalIntent.SCREEN_CAPTURE

    screen_act2 = intent_engine.parse("take a photo of my screen")
    assert screen_act2.intent == CanonicalIntent.SCREEN_CAPTURE


# ==============================================================================
# TEST 8: mac_control Integration Delegation
# ==============================================================================

def test_mac_control_screenshot_action_delegation(tmp_path: Path) -> None:
    """Ensure mac_control screenshot handler delegates to ScreenshotService."""
    with patch.object(screenshot_service, "capture_full_screen", return_value=ScreenshotResult(
        success=True,
        file_path=tmp_path / "Screenshot_test.png",
        filename="Screenshot_test.png",
    )):
        cmd = MacCommand(category=CommandCategory.SCREENSHOT, action="capture_full", raw_input="take a screenshot")
        res = execute_screenshot_command(cmd)
        assert res.status == ExecutionStatus.SUCCESS
        assert "Screenshot_test.png" in res.message


# ==============================================================================
# TEST 9: CapabilityRegistry Registration
# ==============================================================================

def test_capability_registry_screen_capture() -> None:
    """Ensure screen.capture is registered with CapabilityRegistry."""
    cap = capability_registry.get("screen.capture")
    assert cap is not None
    assert cap.name == "screen.capture"
    assert cap.subsystem == "screen_capture"


# ==============================================================================
# Helper
# ==============================================================================

def subprocess_result_mock(returncode: int = 0, stdout: str = "", stderr: str = ""):
    res = MagicMock()
    res.returncode = returncode
    res.stdout = stdout
    res.stderr = stderr
    return res
