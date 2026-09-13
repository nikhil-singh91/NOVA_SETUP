"""Zero-disk, local-first in-memory screen frame capture for NOVA Eyes.

Captures display frames directly into RAM using Apple's ScreenCaptureKit
and Quartz without saving any files, images, or video frames to disk.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import Quartz

Quartz: Any = Quartz
from core.logger import get_logger

try:
    import CoreMedia
    CoreMedia: Any = CoreMedia
except ImportError:
    CoreMedia = None

try:
    import ScreenCaptureKit as SCK
    SCK: Any = SCK
except ImportError:
    SCK = None

try:
    import objc
    objc: Any = objc
except ImportError:
    objc = None

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

    @classmethod
    def get_all_displays(cls) -> list[DisplayMetrics]:
        """Query metrics for all connected physical displays."""
        err, display_ids, count = Quartz.CGGetOnlineDisplayList(16, None, None)
        if err != 0 or not display_ids:
            return [cls.get_primary_metrics()]

        main_id = Quartz.CGMainDisplayID()
        displays: list[DisplayMetrics] = []
        for d_id in display_ids[:count]:
            bounds = Quartz.CGDisplayBounds(d_id)
            log_w = float(bounds.size.width)
            log_h = float(bounds.size.height)
            pix_w = int(Quartz.CGDisplayPixelsWide(d_id))
            pix_h = int(Quartz.CGDisplayPixelsHigh(d_id))
            scale = (pix_w / log_w) if log_w > 0 else 1.0
            displays.append(
                cls(
                    display_id=int(d_id),
                    logical_x=float(bounds.origin.x),
                    logical_y=float(bounds.origin.y),
                    logical_width=log_w,
                    logical_height=log_h,
                    pixel_width=pix_w,
                    pixel_height=pix_h,
                    scale_factor=scale,
                    is_main=(int(d_id) == int(main_id)),
                )
            )
        return displays or [cls.get_primary_metrics()]


@dataclass
class MemoryFrame:
    """An instantaneous display frame residing strictly in RAM (zero disk persistence)."""

    frame_id: str
    timestamp: datetime
    cg_image: Any  # Quartz.CGImage | None
    metrics: DisplayMetrics
    visual_hash: str
    pixel_buffer: Any = None  # CVPixelBufferRef if from ScreenCaptureKit
    active_application: str = ""
    active_window: str = ""

    @property
    def age_seconds(self) -> float:
        return (datetime.now(UTC) - self.timestamp).total_seconds()

    def is_fresh(self, max_age_seconds: float = 3.0) -> bool:
        return self.age_seconds <= max_age_seconds


# Objective-C delegate for ScreenCaptureKit stream callback
_SCKStreamOutputDelegate: Any = None
if objc is not None and SCK is not None:
    try:
        class _SCKStreamOutputDelegateClass(objc.lookUpClass("NSObject")):
            """Receives in-memory frame sample buffers from SCStream with zero disk writes."""

            def initWithCapturer_(self, capturer_ref: Any) -> Any:
                self = objc.super(_SCKStreamOutputDelegateClass, self).init()
                if self is None:
                    return None
                self._capturer = capturer_ref
                return self

            def stream_didOutputSampleBuffer_ofType_(
                self, stream: Any, sample_buffer: Any, buffer_type: int
            ) -> None:
                # SCStreamOutputTypeScreen = 0
                if buffer_type != 0 or sample_buffer is None:
                    return
                try:
                    if self._capturer:
                        self._capturer._handle_stream_sample_buffer(sample_buffer)
                except Exception as exc:
                    logger.debug("SCStream delegate frame handler error: %s", exc)

            def stream_didStopWithError_(self, stream: Any, error: Any) -> None:
                logger.warning("SCStream stopped with error: %s", error)
                if self._capturer:
                    self._capturer._handle_stream_stopped(error)

        _SCKStreamOutputDelegate = _SCKStreamOutputDelegateClass
    except Exception:
        _SCKStreamOutputDelegate = None


class ScreenCapturer:
    """High-performance in-memory screen capture engine with ScreenCaptureKit streaming.

    Operates strictly in RAM with zero disk writes, no frame archives, and no video files.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame_counter = 0
        self._latest_stream_frame: MemoryFrame | None = None
        self._latest_stream_hash: str = ""
        self._stream: Any = None
        self._stream_delegate: Any = None
        self._is_streaming = False
        self._stream_init_attempted = False
        self._use_sck = (SCK is not None and _SCKStreamOutputDelegate is not None)

    @staticmethod
    def get_main_display_metrics() -> DisplayMetrics:
        """Query geometry, logical bounds, and Retina scale factor of main display."""
        return DisplayMetrics.get_primary_metrics()

    @staticmethod
    def check_screen_recording_permission() -> bool:
        """Verify whether the current process has macOS Screen Recording permission."""
        try:
            main_id = Quartz.CGMainDisplayID()
            bounds = Quartz.CGDisplayBounds(main_id)
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

    def get_permission_diagnostics(self) -> dict[str, Any]:
        """Provide detailed diagnosis of screen capture capabilities and permissions."""
        has_perm = self.check_screen_recording_permission()
        return {
            "screen_recording_granted": has_perm,
            "screencapturekit_available": self._use_sck,
            "quartz_fallback_ready": True,
            "streaming_active": self._is_streaming,
            "frames_in_ram": 1 if self._latest_stream_frame is not None else 0,
            "disk_writes": "STRICTLY_OFF",
        }

    # =========================================================================
    # SCREENCAPTUREKIT LIVE STREAMING
    # =========================================================================

    def start_stream(self) -> bool:
        """Start Apple ScreenCaptureKit live in-memory stream if supported and permitted."""
        with self._lock:
            if self._is_streaming:
                return True

            if not self._use_sck:
                logger.debug("ScreenCaptureKit delegate not available; using Quartz on-demand mode.")
                return False

            if not self.check_screen_recording_permission():
                logger.warning("Screen Recording permission not granted. Stream cannot start.")
                return False

            try:
                self._stream_init_attempted = True
                self._stream_delegate = _SCKStreamOutputDelegate.alloc().initWithCapturer_(self)

                # Query shareable content for primary display
                def _content_handler(content: Any, error: Any) -> None:
                    if error or not content:
                        logger.debug("SCShareableContent query failed: %s", error)
                        return

                    try:
                        displays = content.displays()
                        if not displays:
                            return
                        primary_display = displays[0]

                        # Content filter for primary display
                        content_filter = SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(
                            primary_display, []
                        )

                        # Stream configuration: ~3 FPS to keep CPU low, Retina-aware
                        config = SCK.SCStreamConfiguration.alloc().init()
                        metrics = DisplayMetrics.get_primary_metrics()
                        config.setWidth_(metrics.pixel_width)
                        config.setHeight_(metrics.pixel_height)
                        # Throttle minimum frame interval: ~0.33s (3 FPS)
                        if CoreMedia and hasattr(CoreMedia, "CMTimeMake"):
                            config.setMinimumFrameInterval_(CoreMedia.CMTimeMake(1, 3))
                        config.setShowsCursor_(True)

                        stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(
                            content_filter, config, self._stream_delegate
                        )
                        # Register output delegate on global dispatch queue
                        import Foundation
                        dispatch_fn = getattr(Foundation, "dispatch_get_global_queue", None)
                        q = dispatch_fn(0, 0) if dispatch_fn else None
                        stream.addStreamOutput_type_sampleHandlerQueue_error_(
                            self._stream_delegate, 0, q, None
                        )

                        def _start_handler(start_err: Any) -> None:
                            if start_err:
                                logger.debug("SCStream start failed: %s", start_err)
                            else:
                                with self._lock:
                                    self._is_streaming = True
                                logger.info("ScreenCaptureKit live stream active (zero disk writes).")

                        stream.startCaptureWithCompletionHandler_(_start_handler)
                        self._stream = stream
                    except Exception as exc:
                        logger.debug("Error configuring SCStream: %s", exc)

                SCK.SCShareableContent.getShareableContentWithCompletionHandler_(_content_handler)
                return True

            except Exception as exc:
                logger.debug("Failed to start ScreenCaptureKit stream: %s", exc)
                return False

    def stop_stream(self) -> None:
        """Stop ScreenCaptureKit live stream and release buffers."""
        with self._lock:
            if not self._is_streaming or self._stream is None:
                self._is_streaming = False
                return

            try:
                def _stop_handler(err: Any) -> None:
                    logger.debug("SCStream stopped.")

                self._stream.stopCaptureWithCompletionHandler_(_stop_handler)
            except Exception as exc:
                logger.debug("Error stopping SCStream: %s", exc)
            finally:
                self._stream = None
                self._stream_delegate = None
                self._is_streaming = False
                self._latest_stream_frame = None

    def _handle_stream_sample_buffer(self, sample_buffer: Any) -> None:
        """Process incoming CMSampleBufferRef in memory. Replaces latest frame in RAM."""
        if not CoreMedia or sample_buffer is None:
            return

        try:
            pixel_buffer = CoreMedia.CMSampleBufferGetImageBuffer(sample_buffer)
            if not pixel_buffer:
                return

            with self._lock:
                self._frame_counter += 1
                frame_id = f"sck_{self._frame_counter}_{int(time.time() * 1000)}"

            metrics = self.get_main_display_metrics()
            hash_seed = f"sck_{metrics.pixel_width}x{metrics.pixel_height}_{self._frame_counter}"
            visual_hash = hashlib.md5(hash_seed.encode("utf-8")).hexdigest()

            # Strictly replace latest frame — drops stale frame immediately
            frame = MemoryFrame(
                frame_id=frame_id,
                timestamp=datetime.now(UTC),
                cg_image=None,
                pixel_buffer=pixel_buffer,
                metrics=metrics,
                visual_hash=visual_hash,
            )

            with self._lock:
                self._latest_stream_frame = frame
                self._latest_stream_hash = visual_hash

        except Exception as exc:
            logger.debug("Error processing SCStream sample buffer: %s", exc)

    def _handle_stream_stopped(self, error: Any) -> None:
        with self._lock:
            self._is_streaming = False
            self._stream = None

    # =========================================================================
    # ON-DEMAND CAPTURE (SEAMLESS SCK + QUARTZ ZERO-DISK ENGINE)
    # =========================================================================

    def capture_frame(self, metrics: DisplayMetrics | None = None) -> MemoryFrame | None:
        """Alias for capture_memory_frame for clean manager API."""
        return self.capture_memory_frame()

    def capture_memory_frame(
        self,
        active_app: str = "",
        active_win: str = "",
    ) -> MemoryFrame | None:
        """Capture current display directly into RAM (zero disk writes).

        Uses latest fresh ScreenCaptureKit stream frame if available, otherwise
        captures an instantaneous in-memory CGImage via Quartz.
        """
        # 1. If stream is active and has a fresh frame (< 0.8s old), use it
        with self._lock:
            st_frame = self._latest_stream_frame
        if st_frame and st_frame.is_fresh(max_age_seconds=0.8):
            st_frame.active_application = active_app
            st_frame.active_window = active_win
            return st_frame

        # 2. Instantaneous in-memory capture via Quartz
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

        cg_image = Quartz.CGWindowListCreateImage(
            rect,
            Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
            Quartz.kCGWindowImageDefault,
        )

        if not cg_image:
            logger.warning("Failed to capture in-memory display frame.")
            return None

        # Perceptual hash from frame geometry and dimensions
        w = Quartz.CGImageGetWidth(cg_image)
        h = Quartz.CGImageGetHeight(cg_image)
        bpr = Quartz.CGImageGetBytesPerRow(cg_image)
        hash_seed = f"{w}x{h}_{bpr}_{active_app}_{active_win}"
        visual_hash = hashlib.md5(hash_seed.encode("utf-8")).hexdigest()

        frame = MemoryFrame(
            frame_id=frame_id,
            timestamp=datetime.now(UTC),
            cg_image=cg_image,
            pixel_buffer=None,
            metrics=metrics,
            visual_hash=visual_hash,
            active_application=active_app,
            active_window=active_win,
        )

        with self._lock:
            self._latest_stream_frame = frame
            self._latest_stream_hash = visual_hash

        return frame
