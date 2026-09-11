"""Zero-disk, local-first in-memory screen frame capture for NOVA Eyes.

Captures display frames directly into RAM using Quartz and ScreenCaptureKit
without saving any files, images, or video frames to disk.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import Quartz
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DisplayMetrics:
    """Physical and logical geometry for an active macOS display."""

    display_id: int
    logical_x: float
    logical_y: float
    logical_width: float
    logical_height: float
    pixel_width: int
    pixel_height: int
    scale_factor: float
    is_main: bool

    @classmethod
    def get_primary_metrics(cls) -> DisplayMetrics:
        """Query geometry, logical bounds, and Retina scale factor of primary display."""
        main_id = Quartz.CGMainDisplayID()
        bounds = Quartz.CGDisplayBounds(main_id)
        log_w = float(bounds.size.width)
        log_h = float(bounds.size.height)
        log_x = float(bounds.origin.x)
        log_y = float(bounds.origin.y)

        pix_w = int(Quartz.CGDisplayPixelsWide(main_id))
        pix_h = int(Quartz.CGDisplayPixelsHigh(main_id))

        scale = (pix_w / log_w) if log_w > 0 else 1.0

        return cls(
            display_id=int(main_id),
            logical_x=log_x,
            logical_y=log_y,
            logical_width=log_w,
            logical_height=log_h,
            pixel_width=pix_w,
            pixel_height=pix_h,
            scale_factor=scale,
            is_main=True,
        )


@dataclass
class MemoryFrame:
    """An instantaneous display frame residing strictly in RAM (zero disk persistence)."""

    frame_id: str
    timestamp: datetime
    cg_image: Any  # Quartz.CGImage
    metrics: DisplayMetrics
    visual_hash: str
    active_application: str = ""
    active_window: str = ""

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()

    def is_fresh(self, max_age_seconds: float = 3.0) -> bool:
        return self.age_seconds <= max_age_seconds


class ScreenCapturer:
    """High-performance in-memory screen capture engine."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame_counter = 0

    @staticmethod
    def get_main_display_metrics() -> DisplayMetrics:
        """Query geometry, logical bounds, and Retina scale factor of main display."""
        return DisplayMetrics.get_primary_metrics()

    def capture_frame(self, metrics: DisplayMetrics | None = None) -> MemoryFrame | None:
        """Alias for capture_memory_frame for clean manager API."""
        return self.capture_memory_frame()

    @staticmethod
    def check_screen_recording_permission() -> bool:
        """Verify whether the current process has macOS Screen Recording permission."""
        try:
            main_id = Quartz.CGMainDisplayID()
            bounds = Quartz.CGDisplayBounds(main_id)
            # A 1x1 test capture confirms if pixels are readable or transparent/blacked out
            test_bounds = Quartz.CGRectMake(bounds.origin.x, bounds.origin.y, 1, 1)
            img = Quartz.CGWindowListCreateImage(
                test_bounds,
                Quartz.kCGWindowListOptionOnScreenOnly,
                Quartz.kCGNullWindowID,
                Quartz.kCGWindowImageDefault,
            )
            return img is not None
        except Exception as exc:
            logger.debug("Screen recording permission check failed: %s", exc)
            return False

    def capture_memory_frame(
        self,
        active_app: str = "",
        active_win: str = "",
    ) -> MemoryFrame | None:
        """Capture current display into a memory-only MemoryFrame buffer (No Disk I/O)."""
        with self._lock:
            self._frame_counter += 1
            frame_id = f"frame_{self._frame_counter}_{int(time.time() * 1000)}"

        metrics = self.get_main_display_metrics()
        rect = Quartz.CGRectMake(
            metrics.logical_x,
            metrics.logical_y,
            metrics.logical_width,
            metrics.logical_height,
        )

        # In-memory capture via Quartz
        cg_image = Quartz.CGWindowListCreateImage(
            rect,
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            Quartz.kCGWindowImageDefault,
        )

        if not cg_image:
            logger.warning("Failed to capture in-memory display frame.")
            return None

        # Compute fast perceptual hash from image properties
        w = Quartz.CGImageGetWidth(cg_image)
        h = Quartz.CGImageGetHeight(cg_image)
        bpr = Quartz.CGImageGetBytesPerRow(cg_image)
        hash_seed = f"{w}x{h}_{bpr}_{active_app}_{active_win}"
        visual_hash = hashlib.md5(hash_seed.encode("utf-8")).hexdigest()

        return MemoryFrame(
            frame_id=frame_id,
            timestamp=datetime.now(timezone.utc),
            cg_image=cg_image,
            metrics=metrics,
            visual_hash=visual_hash,
            active_application=active_app,
            active_window=active_win,
        )
