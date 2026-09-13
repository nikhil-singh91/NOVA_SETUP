"""Unit tests for ScreenObserver on-demand capture."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.visual.observer import ScreenObserver


def test_screen_observer_initialization(tmp_path: Path) -> None:
    """Validate ScreenObserver directory creation."""
    obs = ScreenObserver(snapshot_dir=tmp_path / "snaps")
    assert obs.snapshot_dir.exists()


def test_screen_observer_capture_mocked(tmp_path: Path) -> None:
    """Validate silent screen capture and hashing."""
    obs = ScreenObserver(snapshot_dir=tmp_path)
    fake_img = tmp_path / "snap_test.png"

    def fake_screencapture(*args, **kwargs):
        fake_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=fake_screencapture):
        snap = obs.capture_current_screen(custom_id="snap_test")
        assert snap.snapshot_id == "snap_test"
        assert snap.image_path == fake_img
        assert len(snap.screen_hash) > 0
        assert snap.is_fresh() is True


def test_screen_observer_cleanup(tmp_path: Path) -> None:
    """Validate snapshot cleanup prevents disk bloat."""
    obs = ScreenObserver(snapshot_dir=tmp_path)
    for i in range(10):
        (tmp_path / f"snap_{i}.png").write_text(f"dummy {i}")

    cleaned = obs.cleanup_old_snapshots(max_keep=3)
    assert cleaned == 7
    remaining = list(tmp_path.glob("*.png"))
    assert len(remaining) == 3
