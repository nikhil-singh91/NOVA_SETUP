"""macOS camera integration, viewfinder launching, and safe photo capture."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import settings
from core.event_bus import NovaEvent
from core.logger import get_logger
from core.registry import registry

from desktop.apps import AppLauncher
from desktop.models import DesktopActionType, DesktopResult

logger = get_logger(__name__)


class CameraManager:
    """Provides camera device discovery, viewfinder application opening, and photo capture."""

    def __init__(self) -> None:
        self.output_dir = Path(getattr(settings, "desktop_camera_output_dir", "~/Pictures/NOVA")).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _publish_event(self, event: NovaEvent, **payload: Any) -> None:
        try:
            if registry.exists("event_bus"):
                bus = registry.get("event_bus")
                bus.publish(event, **payload)
        except Exception as exc:
            logger.debug("Failed to publish camera event %s: %s", event.value, exc)

    def open_camera(self) -> DesktopResult:
        """Open macOS Photo Booth as a live camera preview / viewfinder."""
        self._publish_event(NovaEvent.DESKTOP_ACTION_STARTED, action="open_camera")
        success, msg, spoken = AppLauncher.launch("Photo Booth")
        res = DesktopResult(
            success=success,
            action_type=DesktopActionType.OPEN_CAMERA,
            message=msg,
            spoken_response="Opening camera viewfinder." if success else spoken,
        )
        if success:
            self._publish_event(NovaEvent.DESKTOP_ACTION_COMPLETED, action="open_camera")
        else:
            self._publish_event(NovaEvent.DESKTOP_ACTION_FAILED, action="open_camera", error=msg)
        return res

    def capture_photo(self, filename: str | None = None) -> DesktopResult:
        """Capture a photo upon explicit user command and save to ~/Pictures/NOVA/."""
        self._publish_event(NovaEvent.CAMERA_CAPTURE_STARTED)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        target_name = filename or f"photo_{ts}.jpg"
        if not target_name.endswith((".jpg", ".jpeg", ".png")):
            target_name += ".jpg"

        target_path = (self.output_dir / target_name).resolve()

        # 1. Primary Method: FFmpeg AVFoundation Frame Grabber
        ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
        if os.path.exists(ffmpeg_bin):
            cmd = [
                ffmpeg_bin,
                "-y",
                "-f",
                "avfoundation",
                "-framerate",
                "30",
                "-video_size",
                "1280x720",
                "-i",
                "0",
                "-vframes",
                "1",
                str(target_path),
            ]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=8.0)
                if target_path.exists() and target_path.stat().st_size > 0:
                    logger.info("Photo captured successfully via FFmpeg: %s (%d bytes)", target_path, target_path.stat().st_size)
                    self._publish_event(NovaEvent.CAMERA_CAPTURE_COMPLETED, path=str(target_path))
                    return DesktopResult(
                        success=True,
                        action_type=DesktopActionType.TAKE_PHOTO,
                        message=f"Photo captured and saved to '{target_path}'.",
                        spoken_response="Photo captured and saved to your Pictures folder.",
                        target_path=str(target_path),
                        metadata={"saved_path": str(target_path), "size_bytes": target_path.stat().st_size},
                    )
            except Exception as exc:
                logger.warning("FFmpeg camera capture failed: %s", exc)

        # 2. Secondary Method: ImageSnap CLI tool
        imagesnap_bin = shutil.which("imagesnap")
        if imagesnap_bin:
            try:
                subprocess.run([imagesnap_bin, str(target_path)], capture_output=True, text=True, timeout=8.0)
                if target_path.exists() and target_path.stat().st_size > 0:
                    logger.info("Photo captured successfully via ImageSnap: %s", target_path)
                    self._publish_event(NovaEvent.CAMERA_CAPTURE_COMPLETED, path=str(target_path))
                    return DesktopResult(
                        success=True,
                        action_type=DesktopActionType.TAKE_PHOTO,
                        message=f"Photo captured and saved to '{target_path}'.",
                        spoken_response="Photo captured and saved to your Pictures folder.",
                        target_path=str(target_path),
                    )
            except Exception as exc:
                logger.warning("ImageSnap camera capture failed: %s", exc)

        # 3. Fallback: Open Photo Booth if direct capture device is unavailable
        AppLauncher.launch("Photo Booth")
        self._publish_event(NovaEvent.CAMERA_CAPTURE_FAILED, reason="Direct capture unavailable; opened Photo Booth")
        return DesktopResult(
            success=True,
            action_type=DesktopActionType.OPEN_CAMERA,
            message="Opened Photo Booth for camera capture.",
            spoken_response="Opened camera viewfinder.",
        )
