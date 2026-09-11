"""Central ComputerAgent orchestrator for NOVA Computer Agent V2."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from core.environment import EnvironmentContext, environment_observer
from core.event_bus import EventBus, NovaEvent
from core.lifecycle import lifecycle
from core.logger import get_logger
from core.visual.analysis import ScreenAnalyzer
from core.visual.interaction import ComputerInteractionManager
from core.visual.models import (
    ScreenAnalysis,
    ScreenSnapshot,
    UIElement,
    UIElementType,
    VisualActionPlan,
    VisualActionType,
    VisualConfidence,
    VisualResult,
)
from core.visual.observer import ScreenObserver, screen_observer
from core.visual.resolver import UITargetResolver
from core.visual.verifier import VisualVerifier
from providers.provider_manager import ProviderManager, TaskType

logger = get_logger(__name__)


def log_computer_agent_debug(stage: str, details: dict[str, Any]) -> None:
    """Log structured debug telemetry if NOVA_COMPUTER_AGENT_DEBUG is enabled."""
    if os.getenv("NOVA_COMPUTER_AGENT_DEBUG", "false").lower() == "true":
        logger.info(
            "[COMPUTER_AGENT_DEBUG] %s => %s",
            stage.upper(),
            " | ".join(f"{k}={v}" for k, v in details.items()),
        )


class ComputerAgent:
    """NOVA's primary computer interaction brain: OBSERVE -> UNDERSTAND -> PLAN -> ACT -> VERIFY."""

    def __init__(
        self,
        observer: ScreenObserver | None = None,
        interaction_mgr: ComputerInteractionManager | None = None,
        provider_mgr: ProviderManager | None = None,
    ) -> None:
        self.observer = observer or screen_observer
        self.interaction_mgr = interaction_mgr or ComputerInteractionManager()
        self.provider_mgr = provider_mgr
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._is_active = False

    def initialize(self) -> None:
        """Initialize and register ComputerAgent with lifecycle."""
        logger.info("Initializing ComputerAgent V2...")
        try:
            lifecycle.register_service("computer_agent", self)
        except Exception as exc:
            logger.debug("Could not register ComputerAgent with lifecycle: %s", exc)
        self._is_active = True
        logger.info("ComputerAgent V2 initialized successfully.")

    def stop_active_task(self) -> bool:
        """Interrupt and cancel any running visual action or multi-step routine."""
        self._stop_event.set()
        logger.info("ComputerAgent stop requested.")
        return True

    def reset_cancellation(self) -> None:
        """Reset cancellation event for new tasks."""
        self._stop_event.clear()

    # =========================================================================
    # CORE INTERACTION PIPELINE
    # =========================================================================

    def execute_visual_goal(self, goal_text: str, action_hint: str | None = None) -> VisualResult:
        """Execute a natural visual goal: OBSERVE -> UNDERSTAND -> PLAN -> ACT -> VERIFY."""
        if self._stop_event.is_set():
            return VisualResult(
                success=False,
                action_type=VisualActionType.CLICK,
                message="Visual task cancelled.",
                spoken_response="Task cancelled, Boss.",
                error="Cancelled by user",
            )
        log_computer_agent_debug("TASK_STARTED", {"goal": goal_text, "action_hint": action_hint or "auto"})

        # Step 1: Capture fresh on-demand screen observation
        snapshot = self.observer.capture_current_screen()
        log_computer_agent_debug("SCREEN_OBSERVED", {
            "snapshot_id": snapshot.snapshot_id,
            "app": snapshot.active_application,
            "window": snapshot.active_window,
            "dimensions": f"{snapshot.screen_width}x{snapshot.screen_height}",
        })

        if self._stop_event.is_set():
            return VisualResult(
                success=False,
                action_type=VisualActionType.CLICK,
                message="Visual task cancelled.",
                spoken_response="Task cancelled, Boss.",
                error="Cancelled by user",
            )

        # Step 2: Extract structured UI elements and text
        analysis = ScreenAnalyzer.analyze_snapshot(snapshot, self.provider_mgr)
        log_computer_agent_debug("SCREEN_ANALYZED", {
            "ui_elements": len(analysis.ui_elements),
            "buttons": len(analysis.buttons),
            "inputs": len(analysis.inputs),
            "errors": len(analysis.errors),
        })

        # Step 3: Resolve Target Element & Confidence
        target_elem, confidence, conf_score = UITargetResolver.resolve_target(goal_text, analysis)
        log_computer_agent_debug("TARGET_RESOLVED", {
            "target": target_elem.label if target_elem else "None",
            "type": target_elem.type.value if target_elem else "None",
            "confidence": confidence.value,
            "score": f"{conf_score:.2f}",
        })

        # Check for Low Confidence -> Ask Clarification
        if confidence == VisualConfidence.LOW or target_elem is None:
            spoken = f"I'm not sure which element to click for '{goal_text}'. Could you please clarify?"
            return VisualResult(
                success=False,
                action_type=VisualActionType.CLICK,
                message=spoken,
                spoken_response=spoken,
                confidence_score=conf_score,
                error="Low target resolution confidence",
                before_snapshot=snapshot,
            )

        # Step 4: Dispatch Safe Pointer Action
        success = self.interaction_mgr.click_element(
            target_elem,
            snapshot=snapshot,
            stop_event=self._stop_event,
        )

        if not success:
            spoken = f"Could not click '{target_elem.label}' safely."
            return VisualResult(
                success=False,
                action_type=VisualActionType.CLICK,
                message=spoken,
                spoken_response=spoken,
                error="Interaction failed or cancelled",
                target_element=target_elem,
                before_snapshot=snapshot,
            )

        # Step 5: Post-Action Verification
        time.sleep(0.3)
        after_snapshot = self.observer.capture_current_screen()
        verified, detail = VisualVerifier.verify_action_effect(snapshot, after_snapshot, VisualActionType.CLICK, target_elem)
        log_computer_agent_debug("VERIFICATION", {"verified": verified, "detail": detail})

        spoken = f"Clicked '{target_elem.label}'."
        return VisualResult(
            success=True,
            action_type=VisualActionType.CLICK,
            message=detail,
            spoken_response=spoken,
            verified=verified,
            verification_detail=detail,
            confidence_score=conf_score,
            target_element=target_elem,
            before_snapshot=snapshot,
            after_snapshot=after_snapshot,
        )

    # =========================================================================
    # SPECIALIZED VISUAL ACTIONS
    # =========================================================================

    def close_popup(self) -> VisualResult:
        """Locate and close an active modal, dialog, or sheet."""
        if self._stop_event.is_set():
            return VisualResult(
                success=False,
                action_type=VisualActionType.CLOSE_POPUP,
                message="Action cancelled.",
                spoken_response="Action cancelled, Boss.",
                error="Cancelled by user",
            )
        snapshot = self.observer.capture_current_screen()
        analysis = ScreenAnalyzer.analyze_snapshot(snapshot, self.provider_mgr)

        close_elem, confidence, score = UITargetResolver.resolve_target("close popup", analysis)
        if not close_elem:
            # Fallback: Send escape key
            self.interaction_mgr.press_key("escape", stop_event=self._stop_event)
            spoken = "Closed popup with Escape key."
            return VisualResult(
                success=True,
                action_type=VisualActionType.CLOSE_POPUP,
                message=spoken,
                spoken_response=spoken,
                verified=True,
            )

        success = self.interaction_mgr.click_element(close_elem, snapshot=snapshot, stop_event=self._stop_event)
        time.sleep(0.2)
        after_snapshot = self.observer.capture_current_screen()
        verified, detail = VisualVerifier.verify_action_effect(snapshot, after_snapshot, VisualActionType.CLOSE_POPUP, close_elem)

        spoken = f"Closed popup ({close_elem.label})." if success else "Could not close popup."
        return VisualResult(
            success=success,
            action_type=VisualActionType.CLOSE_POPUP,
            message=detail,
            spoken_response=spoken,
            verified=verified,
            target_element=close_elem,
            before_snapshot=snapshot,
            after_snapshot=after_snapshot,
        )

    def type_into_focused_or_target(self, text: str, target_label: str | None = None, submit: bool = False) -> VisualResult:
        """Focus target input field (or active focus) and type text."""
        if self._stop_event.is_set():
            return VisualResult(
                success=False,
                action_type=VisualActionType.TYPE_TEXT,
                message="Action cancelled.",
                spoken_response="Action cancelled, Boss.",
                error="Cancelled by user",
            )
        snapshot = self.observer.capture_current_screen()

        if target_label:
            analysis = ScreenAnalyzer.analyze_snapshot(snapshot, self.provider_mgr)
            target_elem, conf, score = UITargetResolver.resolve_target(target_label, analysis, target_type=UIElementType.INPUT)
            if target_elem and conf in (VisualConfidence.HIGH, VisualConfidence.MEDIUM):
                self.interaction_mgr.click_element(target_elem, snapshot=snapshot, stop_event=self._stop_event)
                time.sleep(0.15)

        # Type text
        success = self.interaction_mgr.type_text(text, submit=submit, stop_event=self._stop_event)
        spoken = f"Typed '{text}'." + (" Submitted." if submit else "")
        return VisualResult(
            success=success,
            action_type=VisualActionType.TYPE_TEXT,
            message=spoken,
            spoken_response=spoken,
            verified=success,
        )

    def scroll_until_visible(self, target_text: str, max_scrolls: int = 6) -> VisualResult:
        """Scroll down boundedly until target text or element becomes visible."""
        if self._stop_event.is_set():
            return VisualResult(
                success=False,
                action_type=VisualActionType.SCROLL_UNTIL_VISIBLE,
                message="Scrolling cancelled.",
                spoken_response="Scrolling stopped, Boss.",
                error="Cancelled by user",
            )
        clean_target = target_text.lower().strip()

        for step in range(1, max_scrolls + 1):
            if self._stop_event.is_set():
                return VisualResult(
                    success=False,
                    action_type=VisualActionType.SCROLL_UNTIL_VISIBLE,
                    message="Scrolling cancelled.",
                    spoken_response="Scrolling stopped, Boss.",
                    error="Cancelled by user",
                )

            # Observe
            snapshot = self.observer.capture_current_screen()
            analysis = ScreenAnalyzer.analyze_snapshot(snapshot, self.provider_mgr)

            # Check if target is now visible
            matches = analysis.find_elements_by_label(clean_target)
            if matches or any(clean_target in t.lower() for t in analysis.visible_text):
                spoken = f"Found '{target_text}' on screen."
                return VisualResult(
                    success=True,
                    action_type=VisualActionType.SCROLL_UNTIL_VISIBLE,
                    message=spoken,
                    spoken_response=spoken,
                    verified=True,
                    target_element=matches[0] if matches else None,
                    after_snapshot=snapshot,
                )

            # Scroll down
            self.interaction_mgr.scroll(direction="down", lines=6, stop_event=self._stop_event)
            time.sleep(0.6)

        spoken = f"I scrolled through the page but couldn't find '{target_text}'."
        return VisualResult(
            success=False,
            action_type=VisualActionType.SCROLL_UNTIL_VISIBLE,
            message=spoken,
            spoken_response=spoken,
            error="Target text not found after maximum scrolls",
        )

    def explain_active_screen_error(self) -> VisualResult:
        """Explain errors or alerts currently showing on the user's screen."""
        self.reset_cancellation()
        snapshot = self.observer.capture_current_screen()
        analysis = ScreenAnalyzer.analyze_snapshot(snapshot, self.provider_mgr)

        if self.provider_mgr:
            explanation = ScreenAnalyzer.explain_error_on_screen(analysis, self.provider_mgr)
        else:
            explanation = f"Detected error in {snapshot.active_application}: {analysis.errors[0] if analysis.errors else 'No explicit error code found.'}"

        return VisualResult(
            success=True,
            action_type=VisualActionType.EXPLAIN_ERROR,
            message=explanation,
            spoken_response=explanation,
            verified=True,
            before_snapshot=snapshot,
        )

    def explain_screen_content(self) -> VisualResult:
        """Provide a visual summary of what is on screen."""
        self.reset_cancellation()
        snapshot = self.observer.capture_current_screen()
        analysis = ScreenAnalyzer.analyze_snapshot(snapshot, self.provider_mgr, deep_semantic=True)

        desc = analysis.description or f"You are looking at {snapshot.active_window or snapshot.active_application}."
        return VisualResult(
            success=True,
            action_type=VisualActionType.EXPLAIN_SCREEN,
            message=desc,
            spoken_response=desc,
            verified=True,
            before_snapshot=snapshot,
        )


# Global singleton ComputerAgent
computer_agent = ComputerAgent()
