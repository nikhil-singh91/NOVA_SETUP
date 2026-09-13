"""On-demand screen and window snapshot observer for NOVA Computer Agent V2."""

from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from core.environment import environment_observer
from core.logger import get_logger
from core.visual.models import ScreenSnapshot

logger = get_logger(__name__)


class ScreenObserver:
    """Provides bounded, on-demand screen and window capture without continuous polling."""

    def __init__(self, snapshot_dir: Path | None = None) -> None:
        self.snapshot_dir = snapshot_dir or Path.home() / ".nova" / "snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_snapshot: ScreenSnapshot | None = None

    def get_screen_dimensions(self) -> tuple[int, int]:
        """Query main display pixel dimensions from Quartz or fallback."""
        try:
            import Quartz
            main_id = Quartz.CGMainDisplayID()
            w = int(Quartz.CGDisplayPixelsWide(main_id))
            h = int(Quartz.CGDisplayPixelsHigh(main_id))
            if w > 0 and h > 0:
                return w, h
        except Exception as exc:
            logger.debug("Quartz display dimensions query error: %s", exc)

        return 1470, 956  # Safe macOS standard default

    def capture_current_screen(self, custom_id: str | None = None) -> ScreenSnapshot:
        """Capture an instantaneous, silent full-screen snapshot for the current task."""
        snap_id = custom_id or f"snap_{uuid.uuid4().hex[:10]}"
        timestamp = datetime.now(UTC)
        file_path = self.snapshot_dir / f"{snap_id}.png"

        # 1. Fetch current environment context for metadata
        ctx = environment_observer.get_context()
        screen_w, screen_h = self.get_screen_dimensions()

        # 2. Execute silent native screencapture
        try:
            res = subprocess.run(
                ["screencapture", "-x", "-C", str(file_path)],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
            if res.returncode != 0 or not file_path.exists():
                logger.warning("screencapture exited with code %d: %s", res.returncode, res.stderr)
        except Exception as exc:
            logger.error("Failed to execute screencapture: %s", exc)

        # 3. Compute image hash if file exists
        img_hash = ""
        if file_path.exists() and file_path.stat().st_size > 0:
            try:
                data = file_path.read_bytes()
                img_hash = hashlib.md5(data).hexdigest()
            except Exception:
                pass

        snapshot = ScreenSnapshot(
            snapshot_id=snap_id,
            timestamp=timestamp,
            image_path=file_path if file_path.exists() else None,
            screen_width=screen_w,
            screen_height=screen_h,
            active_application=ctx.active_application or "",
            active_window=ctx.active_window or "",
            screen_hash=img_hash,
            is_window_only=False,
        )

        with self._lock:
            self._last_snapshot = snapshot

        logger.debug(
            "Captured screen snapshot %s (%dx%d, app='%s', hash=%s)",
            snap_id,
            screen_w,
            screen_h,
            snapshot.active_application,
            img_hash[:8] if img_hash else "none",
        )
        return snapshot

    def capture_active_window(self, custom_id: str | None = None) -> ScreenSnapshot:
        """Capture a snapshot of the frontmost window."""
        snap_id = custom_id or f"win_{uuid.uuid4().hex[:10]}"
        timestamp = datetime.now(UTC)
        file_path = self.snapshot_dir / f"{snap_id}.png"

        ctx = environment_observer.get_context()
        screen_w, screen_h = self.get_screen_dimensions()

        # Try window capture (-l flag or fallback to full screen)
        try:
            subprocess.run(
                ["screencapture", "-x", "-w", str(file_path)],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
            if not file_path.exists() or file_path.stat().st_size == 0:
                return self.capture_current_screen(custom_id=snap_id)
        except Exception:
            return self.capture_current_screen(custom_id=snap_id)

        img_hash = ""
        if file_path.exists() and file_path.stat().st_size > 0:
            try:
                img_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
            except Exception:
                pass

        snapshot = ScreenSnapshot(
            snapshot_id=snap_id,
            timestamp=timestamp,
            image_path=file_path if file_path.exists() else None,
            screen_width=screen_w,
            screen_height=screen_h,
            active_application=ctx.active_application or "",
            active_window=ctx.active_window or "",
            screen_hash=img_hash,
            is_window_only=True,
        )
        with self._lock:
            self._last_snapshot = snapshot
        return snapshot

    def capture_region(self, x: int, y: int, width: int, height: int, custom_id: str | None = None) -> ScreenSnapshot:
        """Capture a specific bounding box region of the display."""
        snap_id = custom_id or f"reg_{uuid.uuid4().hex[:10]}"
        timestamp = datetime.now(UTC)
        file_path = self.snapshot_dir / f"{snap_id}.png"

        ctx = environment_observer.get_context()
        rect_arg = f"{x},{y},{width},{height}"

        try:
            subprocess.run(
                ["screencapture", "-x", "-R", rect_arg, str(file_path)],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
        except Exception as exc:
            logger.error("Failed to capture region %s: %s", rect_arg, exc)

        img_hash = ""
        if file_path.exists() and file_path.stat().st_size > 0:
            try:
                img_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
            except Exception:
                pass

        return ScreenSnapshot(
            snapshot_id=snap_id,
            timestamp=timestamp,
            image_path=file_path if file_path.exists() else None,
            screen_width=width,
            screen_height=height,
            active_application=ctx.active_application or "",
            active_window=ctx.active_window or "",
            screen_hash=img_hash,
            is_window_only=False,
        )

    def get_last_snapshot(self) -> ScreenSnapshot | None:
        """Return the most recent snapshot captured."""
        with self._lock:
            return self._last_snapshot

    def cleanup_old_snapshots(self, max_keep: int = 15) -> int:
        """Prune older temporary screenshot files to prevent disk usage buildup."""
        cleaned = 0
        try:
            files = sorted(self.snapshot_dir.glob("*.png"), key=os.path.getmtime, reverse=True)
            for f in files[max_keep:]:
                try:
                    f.unlink(missing_ok=True)
                    cleaned += 1
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Error cleaning up snapshots: %s", exc)
        return cleaned


# Global singleton observer
screen_observer = ScreenObserver()
