"""Tests for ScreenRecordingManager lifecycle, permissions, and natural language intent matching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from core.screen_recording import ScreenRecordingManager, ScreenRecordingResult
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent


def test_screen_recording_manager_initialization(tmp_path: Path) -> None:
    """Validate ScreenRecordingManager setup."""
    mgr = ScreenRecordingManager(output_dir=tmp_path)
    assert mgr.output_dir == tmp_path
    assert mgr.is_recording() is False


def test_screen_recording_lifecycle_mocked(tmp_path: Path) -> None:
    """Test start, duplicate prevention, and stop lifecycle with mocked subprocess."""
    mgr = ScreenRecordingManager(output_dir=tmp_path)
    mock_file = tmp_path / "test_recording.mp4"

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.poll.return_value = None  # running

    def fake_wait(timeout=None):
        mock_file.write_bytes(b"\x00\x00\x00\x1cftypqt  " + b"\x00" * 1024)
        return 0

    mock_proc.wait.side_effect = fake_wait

    with patch("subprocess.Popen", return_value=mock_proc):
        with patch("os.killpg"):
            with patch("os.getpgid", return_value=12345):
                # 1. Start recording
                res1 = mgr.start_recording("test_recording.mp4")
                assert isinstance(res1, ScreenRecordingResult)
                assert res1.success is True
                assert res1.spoken_response == "Screen recording started."
                assert res1.recording_active is True
                assert mgr.is_recording() is True

                # 2. Duplicate start prevention
                res2 = mgr.start_recording("another.mp4")
                assert res2.success is False
                assert res2.spoken_response == "Screen recording is already running."
                assert res2.recording_active is True

                # 3. Stop recording
                res3 = mgr.stop_recording()
                assert res3.success is True
                assert res3.spoken_response == "Screen recording stopped and saved to your Desktop."
                assert res3.file_path == mock_file
                assert res3.file_path.exists()
                assert res3.recording_active is False
                assert mgr.is_recording() is False

                # 4. Stop when inactive
                res4 = mgr.stop_recording()
                assert res4.success is False
                assert res4.spoken_response == "There is no active screen recording."
                assert res4.recording_active is False


@pytest.mark.parametrize(
    "phrase,expected_intent",
    [
        # Start commands
        ("start screen recording", CanonicalIntent.START_SCREEN_RECORDING),
        ("NOVA start screen recording", CanonicalIntent.START_SCREEN_RECORDING),
        ("start recording my screen", CanonicalIntent.START_SCREEN_RECORDING),
        ("record my screen", CanonicalIntent.START_SCREEN_RECORDING),
        ("begin screen recording", CanonicalIntent.START_SCREEN_RECORDING),
        ("capture my screen as video", CanonicalIntent.START_SCREEN_RECORDING),
        ("start recording", CanonicalIntent.START_SCREEN_RECORDING),
        ("record what I am doing", CanonicalIntent.START_SCREEN_RECORDING),
        ("record screen", CanonicalIntent.START_SCREEN_RECORDING),
        ("screen record", CanonicalIntent.START_SCREEN_RECORDING),
        # Stop commands
        ("stop screen recording", CanonicalIntent.STOP_SCREEN_RECORDING),
        ("NOVA stop screen recording", CanonicalIntent.STOP_SCREEN_RECORDING),
        ("stop recording", CanonicalIntent.STOP_SCREEN_RECORDING),
        ("end screen recording", CanonicalIntent.STOP_SCREEN_RECORDING),
        ("finish recording my screen", CanonicalIntent.STOP_SCREEN_RECORDING),
        ("finish recording", CanonicalIntent.STOP_SCREEN_RECORDING),
    ],
)
def test_screen_recording_intent_variations(phrase: str, expected_intent: CanonicalIntent) -> None:
    engine = NaturalLanguageIntentEngine()
    action = engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == expected_intent, f"Failed for phrase: '{phrase}' (got {action.intent}, expected {expected_intent})"
