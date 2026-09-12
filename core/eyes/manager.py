"""NOVA Eyes Manager: Real-time continuous computer perception and world-state engine.

Orchestrates live in-memory screen capture via Apple ScreenCaptureKit,
native macOS Accessibility (AXUIElement), event-driven NSWorkspace observers,
Apple Vision neural OCR, and dynamic coordinate resolution.
Strictly local-first, zero disk writes, zero continuous cloud streaming.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from core.eyes.accessibility import (
    AccessibilityInspector,
    SemanticElement,
    WorkspaceEventsObserver,
)
from core.eyes.capture import DisplayMetrics, MemoryFrame, ScreenCapturer
from core.eyes.interaction import EyesInteractionManager
from core.eyes.planner import ActionType, ConfidenceLevel, EyesTargetResolver
from core.eyes.proactive import ProactiveAssistanceEngine, ProactiveOpportunity
from core.eyes.state import ScreenState
from core.eyes.verifier import EyesStateVerifier, VerificationOutcome
from core.eyes.vision_ocr import VisionOCR, VisualEntityCard
from core.logger import get_logger

logger = get_logger(__name__)


class NovaEyesManager:
    """NOVA's primary real-time computer perception layer for macOS."""

    def __init__(self) -> None:
        self.capturer = ScreenCapturer()
        self.ax_inspector = AccessibilityInspector()
        self.ocr = VisionOCR()
        self.interaction = EyesInteractionManager()
        self.proactive = ProactiveAssistanceEngine()

        self._lock = threading.Lock()
        self._is_running = False
        self._is_paused = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Event observer for app switches and desktop lifecycle
        self._workspace_observer: WorkspaceEventsObserver | None = None
        self._app_switch_flag = threading.Event()

        # Latest perceived state in RAM (strictly latest, no unbounded history)
        self._latest_state: ScreenState | None = None
        self._latest_hash: str = ""
        self._last_perception_time: float = 0.0
        self._last_ocr_time: float = 0.0

        # Proactive opportunity callback
        self._proactive_callback: Callable[[ProactiveOpportunity], None] | None = None

        # Performance & telemetry metrics
        self._frames_captured: int = 0
        self._frames_dropped: int = 0
        self._ocr_runs: int = 0
        self._active_display: DisplayMetrics = DisplayMetrics.get_primary_metrics()

    # =========================================================================
    # LIFECYCLE CONTROLS
    # =========================================================================

    def start(self) -> bool:
        """Start continuous screen perception loop and ScreenCaptureKit stream in background."""
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

            # Start ScreenCaptureKit live in-memory stream if available
            self.capturer.start_stream()

            # Start event-driven workspace observer for desktop transitions
            self._workspace_observer = WorkspaceEventsObserver(self._on_workspace_event)
            self._workspace_observer.start()

            self._thread = threading.Thread(
                target=self._perception_loop,
                name="NovaEyesPerceptionLoop",
                daemon=True,
            )
            self._thread.start()
            logger.info("NovaEyesManager started successfully (continuous perception active).")
            return True

    def stop(self) -> bool:
        """Stop perception loop and release resources."""
        with self._lock:
            if not self._is_running:
                return True

            self._stop_event.set()
            self._is_running = False
            self._is_paused = False

        # Stop workspace observer
        if self._workspace_observer:
            self._workspace_observer.stop()
            self._workspace_observer = None

        # Stop ScreenCaptureKit stream
        self.capturer.stop_stream()

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

    def set_proactive_callback(self, callback: Callable[[ProactiveOpportunity], None]) -> None:
        """Register listener for proactive assistance suggestions."""
        self._proactive_callback = callback

    def _on_workspace_event(self, event_name: str, app_name: str) -> None:
        """Invoked when NSWorkspace fires an app activation or desktop transition."""
        self._app_switch_flag.set()
        logger.debug("Workspace event '%s' from '%s' flagged immediate perception refresh.", event_name, app_name)

    def get_status(self) -> dict[str, Any]:
        """Status report for dashboard and health monitoring."""
        diag = self.capturer.get_permission_diagnostics()
        cap_engine = (
            "ScreenCaptureKit (in-memory stream)"
            if diag.get("streaming_active")
            else "Quartz / ScreenCaptureKit (in-memory)"
        )
        return {
            "status": "ACTIVE" if self.is_running else ("PAUSED" if self._is_paused else "STOPPED"),
            "capture_engine": cap_engine,
            "semantic_engine": "macOS Accessibility (AXUIElement + WorkspaceObserver)",
            "vision_engine": "Apple Vision (VNRecognizeTextRequest + VNClassifyImageRequest)",
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
            "page_category": self._latest_state.page_category.value if self._latest_state else "general",
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
        visual_cards: list[VisualEntityCard] = []
        if force_ocr:
            ocr_elements = self.ocr.recognize_text(frame)
            self._ocr_runs += 1
            if ocr_elements:
                visual_cards = self.ocr.detect_visual_cards(ocr_elements)

        # 4. Extract browser context if active app is a browser
        browser_info = self._get_browser_context(active_app)

        # 5. Synthesize unified ScreenState in RAM
        state = ScreenState.build_from_sources(
            timestamp=datetime.now(timezone.utc),
            active_app=active_app,
            active_win=active_win,
            metrics=self._active_display,
            visual_hash=frame.visual_hash,
            ax_elements=ax_elements,
            ocr_elements=ocr_elements,
            visual_cards=visual_cards,
            browser_info=browser_info,
        )

        with self._lock:
            self._latest_state = state
            self._latest_hash = frame.visual_hash
            self._last_perception_time = time.time()

        elapsed_ms = (time.time() - start_time) * 1000.0
        logger.debug(
            "observe_now() completed in %.1fms: app='%s', win='%s', cat=%s, elements=%d, ocr=%d",
            elapsed_ms,
            active_app,
            active_win,
            state.page_category.value,
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

    def _get_browser_context(self, active_app: str) -> dict[str, Any]:
        """Query active browser state if frontmost application is a web browser."""
        app_lower = active_app.lower()
        if not any(b in app_lower for b in ("chrome", "safari", "brave", "edge", "arc")):
            return {}

        try:
            from core.environment import environment_observer
            ctx = environment_observer.refresh(force=False)
            return {
                "active_browser": ctx.active_browser or active_app,
                "active_tab_index": ctx.active_tab_index or 1,
                "active_tab_count": ctx.active_tab_count or 1,
                "current_page_title": ctx.current_page_title or "",
                "current_url": ctx.current_url or "",
                "current_domain": ctx.current_domain or "",
            }
        except Exception:
            return {"active_browser": active_app}

    # =========================================================================
    # PASSIVE PERCEPTION LOOP (ADAPTIVE & LOW CPU)
    # =========================================================================

    def _perception_loop(self) -> None:
        """Adaptive background perception: captures frames, updates state on change, drops stale frames."""
        logger.info("NOVA Eyes continuous perception loop active.")

        while not self._stop_event.is_set():
            if self._is_paused:
                time.sleep(0.5)
                continue

            try:
                now = time.time()
                # Fast track if workspace signaled an app switch event
                event_triggered = self._app_switch_flag.is_set()
                if event_triggered:
                    self._app_switch_flag.clear()

                # Rate limit passive perception to ~2-3 FPS to conserve CPU unless an event triggered
                if not event_triggered and (now - self._last_perception_time < 0.35):
                    time.sleep(0.1)
                    continue

                frame = self.capturer.capture_frame(self._active_display)
                if frame is None:
                    time.sleep(0.4)
                    continue

                self._frames_captured += 1

                # Visual hash check: if hash changed or app switched, trigger state refresh
                is_changed = (frame.visual_hash != self._latest_hash) or event_triggered

                # Refresh OCR every 4-5 seconds or whenever the screen visually changed
                should_run_ocr = is_changed or (now - self._last_ocr_time > 4.5)

                active_app, active_win, ax_elements = self.ax_inspector.inspect_frontmost_window()

                ocr_elements: list[SemanticElement] = []
                visual_cards: list[VisualEntityCard] = []
                if should_run_ocr:
                    ocr_elements = self.ocr.recognize_text(frame)
                    self._ocr_runs += 1
                    self._last_ocr_time = now
                    if ocr_elements:
                        visual_cards = self.ocr.detect_visual_cards(ocr_elements)
                elif self._latest_state:
                    ocr_elements = [e for e in self._latest_state.elements if e.source == "vision_ocr"]

                browser_info = self._get_browser_context(active_app)

                state = ScreenState.build_from_sources(
                    timestamp=datetime.now(timezone.utc),
                    active_app=active_app,
                    active_win=active_win,
                    metrics=self._active_display,
                    visual_hash=frame.visual_hash,
                    ax_elements=ax_elements,
                    ocr_elements=ocr_elements,
                    visual_cards=visual_cards,
                    browser_info=browser_info,
                )

                with self._lock:
                    self._latest_state = state
                    self._latest_hash = frame.visual_hash
                    self._last_perception_time = now

                # Evaluate proactive assistance opportunity
                if self._proactive_callback and should_run_ocr:
                    opp = self.proactive.evaluate_state(state)
                    if opp:
                        try:
                            self._proactive_callback(opp)
                        except Exception as exc:
                            logger.debug("Error delivering proactive opportunity: %s", exc)

            except Exception as exc:
                logger.debug("Passive perception loop iteration error: %s", exc)
                time.sleep(0.5)

        logger.info("NOVA Eyes perception loop terminated.")


# Global singleton instance
nova_eyes = NovaEyesManager()
