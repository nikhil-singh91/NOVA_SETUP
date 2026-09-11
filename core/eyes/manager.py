"""NOVA Eyes Manager: Real-time screen perception and world-state engine.

Orchestrates live in-memory screen capture, native macOS Accessibility,
Apple Vision neural OCR, and dynamic coordinate resolution.
Strictly local-first, zero disk writes, zero continuous cloud streaming.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from core.eyes.accessibility import AccessibilityInspector, SemanticElement
from core.eyes.capture import DisplayMetrics, MemoryFrame, ScreenCapturer
from core.eyes.interaction import EyesInteractionManager
from core.eyes.planner import ActionType, ConfidenceLevel, EyesTargetResolver
from core.eyes.state import ScreenState
from core.eyes.verifier import EyesStateVerifier, VerificationOutcome
from core.eyes.vision_ocr import VisionOCR
from core.logger import get_logger

logger = get_logger(__name__)


class NovaEyesManager:
    """NOVA's primary real-time perception layer for macOS."""

    def __init__(self) -> None:
        self.capturer = ScreenCapturer()
        self.ax_inspector = AccessibilityInspector()
        self.ocr = VisionOCR()
        self.interaction = EyesInteractionManager()

        self._lock = threading.Lock()
        self._is_running = False
        self._is_paused = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Latest perceived state in RAM (strictly latest, no unbounded history)
        self._latest_state: ScreenState | None = None
        self._latest_hash: str = ""
        self._last_perception_time: float = 0.0
        self._last_ocr_time: float = 0.0

        # Performance & telemetry metrics
        self._frames_captured: int = 0
        self._frames_dropped: int = 0
        self._ocr_runs: int = 0
        self._active_display: DisplayMetrics = DisplayMetrics.get_primary_metrics()

    # =========================================================================
    # LIFECYCLE CONTROLS
    # =========================================================================

    def start(self) -> bool:
        """Start passive screen perception loop in background thread."""
        with self._lock:
            if self._is_running:
                logger.debug("NovaEyesManager already running.")
                return True

            self._stop_event.clear()
            self._is_running = True
            self._is_paused = False

            # Refresh display metrics on startup
            self._active_display = DisplayMetrics.get_primary_metrics()
            self.interaction.update_metrics(self._active_display)

            self._thread = threading.Thread(target=self._perception_loop, name="NovaEyesPerceptionLoop", daemon=True)
            self._thread.start()
            logger.info("NovaEyesManager started successfully (passive awareness active).")
            return True

    def stop(self) -> bool:
        """Stop perception loop and release resources."""
        with self._lock:
            if not self._is_running:
                return True

            self._stop_event.set()
            self._is_running = False
            self._is_paused = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        logger.info("NovaEyesManager stopped.")
        return True

    def pause(self) -> None:
        """Pause active background perception to preserve CPU when inactive."""
        self._is_paused = True
        logger.info("NovaEyesManager paused.")

    def resume(self) -> None:
        """Resume background perception."""
        self._is_paused = False
        logger.info("NovaEyesManager resumed.")

    @property
    def is_running(self) -> bool:
        return self._is_running and not self._is_paused

    def get_status(self) -> dict[str, Any]:
        """Status report for dashboard and health monitoring."""
        return {
            "status": "ACTIVE" if self.is_running else ("PAUSED" if self._is_paused else "STOPPED"),
            "capture_engine": "Quartz/ScreenCaptureKit (in-memory)",
            "semantic_engine": "macOS Accessibility (AXUIElement)",
            "vision_engine": "Apple Vision (VNRecognizeTextRequest)",
            "ocr_mode": "Local-first",
            "disk_storage": "OFF (0 bytes persisted)",
            "recording": "OFF",
            "cloud_streaming": "OFF",
            "display": f"{self._active_display.logical_width}x{self._active_display.logical_height} (scale={self._active_display.scale_factor:.1f})",
            "frames_captured": self._frames_captured,
            "frames_dropped": self._frames_dropped,
            "ocr_runs": self._ocr_runs,
            "active_app": self._latest_state.active_application if self._latest_state else "None",
            "active_window": self._latest_state.active_window if self._latest_state else "None",
            "elements_visible": len(self._latest_state.elements) if self._latest_state else 0,
        }

    # =========================================================================
    # ACTIVE OBSERVATION (ON-DEMAND FOR ACTIONS & VERIFICATION)
    # =========================================================================

    def observe_now(self, force_ocr: bool = True) -> ScreenState:
        """Capture fresh screen state in RAM immediately for action planning or verification."""
        start_time = time.time()
        self._active_display = DisplayMetrics.get_primary_metrics()
        self.interaction.update_metrics(self._active_display)

        # 1. Grab fresh in-memory frame
        frame = self.capturer.capture_frame(self._active_display)
        if frame is None:
            # Fallback placeholder state if display disconnected
            return ScreenState(
                timestamp=datetime.now(timezone.utc),
                active_application="Desktop",
                active_window="Screen",
                metrics=self._active_display,
                visual_hash="",
            )

        self._frames_captured += 1

        # 2. Extract semantic Accessibility tree from frontmost window
        active_app, active_win, ax_elements = self.ax_inspector.inspect_frontmost_window()

        # 3. Extract Vision OCR elements from memory buffer if requested
        ocr_elements: list[SemanticElement] = []
        if force_ocr:
            ocr_elements = self.ocr.recognize_text(frame)
            self._ocr_runs += 1

        # 4. Synthesize unified ScreenState in RAM
        state = ScreenState.build_from_sources(
            timestamp=datetime.now(timezone.utc),
            active_app=active_app,
            active_win=active_win,
            metrics=self._active_display,
            visual_hash=frame.visual_hash,
            ax_elements=ax_elements,
            ocr_elements=ocr_elements,
        )

        with self._lock:
            self._latest_state = state
            self._latest_hash = frame.visual_hash
            self._last_perception_time = time.time()

        elapsed_ms = (time.time() - start_time) * 1000.0
        logger.debug(
            "observe_now() completed in %.1fms: app='%s', win='%s', elements=%d, ocr=%d",
            elapsed_ms,
            active_app,
            active_win,
            len(ax_elements),
            len(ocr_elements),
        )
        return state

    def get_latest_state(self) -> ScreenState:
        """Retrieve latest perceived ScreenState or observe fresh if stale."""
        with self._lock:
            cur = self._latest_state

        if cur is None or not cur.is_fresh(max_age_seconds=2.5):
            return self.observe_now(force_ocr=False)

        return cur

    # =========================================================================
    # PASSIVE PERCEPTION LOOP (ADAPTIVE & LOW CPU)
    # =========================================================================

    def _perception_loop(self) -> None:
        """Adaptive background perception: captures frames, updates state on change, drops stale frames."""
        logger.info("NOVA Eyes perception loop active.")

        while not self._stop_event.is_set():
            if self._is_paused:
                time.sleep(0.5)
                continue

            try:
                now = time.time()
                # Rate limit passive perception to ~2-3 FPS to conserve CPU
                if now - self._last_perception_time < 0.35:
                    time.sleep(0.1)
                    continue

                frame = self.capturer.capture_frame(self._active_display)
                if frame is None:
                    time.sleep(0.5)
                    continue

                self._frames_captured += 1

                # Cheap visual hash check: if hash is unchanged, skip expensive OCR
                is_changed = (frame.visual_hash != self._latest_hash)

                # Periodic OCR refresh every 5 seconds or whenever screen changes
                should_run_ocr = is_changed or (now - self._last_ocr_time > 5.0)

                active_app, active_win, ax_elements = self.ax_inspector.inspect_frontmost_window()

                ocr_elements: list[SemanticElement] = []
                if should_run_ocr:
                    ocr_elements = self.ocr.recognize_text(frame)
                    self._ocr_runs += 1
                    self._last_ocr_time = now
                elif self._latest_state:
                    # Retain previous OCR elements if screen is stable
                    ocr_elements = [e for e in self._latest_state.elements if e.source == "ocr"]

                state = ScreenState.build_from_sources(
                    timestamp=datetime.now(timezone.utc),
                    active_app=active_app,
                    active_win=active_win,
                    metrics=self._active_display,
                    visual_hash=frame.visual_hash,
                    ax_elements=ax_elements,
                    ocr_elements=ocr_elements,
                )

                with self._lock:
                    self._latest_state = state
                    self._latest_hash = frame.visual_hash
                    self._last_perception_time = now

            except Exception as exc:
                logger.debug("Passive perception error: %s", exc)
                time.sleep(0.5)

        logger.info("NOVA Eyes perception loop terminated.")


# Global singleton instance
nova_eyes = NovaEyesManager()
