"""Central BrowserManager coordinator for NOVA Browser Actions and Natural Language Intent Engine."""

from __future__ import annotations

import threading
from typing import Any

from config.settings import settings
from core.event_bus import NovaEvent
from core.logger import get_logger
from core.registry import registry
from browser.context import BrowserContextManager
from browser.engine import BaseBrowserEngine, MacOSNativeBrowserEngine
from browser.models import (
    ActionType,
    BrowserActionCancelled,
    BrowserActionPlan,
    BrowserResult,
    SensitiveActionBlockedError,
)
from browser.parser import BrowserIntentParser
from browser.planner import BrowserTaskPlanner
from browser.router import BrowserActionRouter
from browser.safety import BrowserSafetyPolicy
from browser.sessions import BrowserSessionManager
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent, StructuredAction
from intent.router import UniversalActionRouter, structured_action_to_browser_plan

logger = get_logger(__name__)


class BrowserManager:
    """Central coordinator for natural language action detection, multi-step planning, safety, and execution."""

    def __init__(self, browser: str | None = None) -> None:
        self.browser_name = browser or settings.default_browser or "chrome"
        self.engine: BaseBrowserEngine = MacOSNativeBrowserEngine(browser=self.browser_name)
        self.sessions: BrowserSessionManager = BrowserSessionManager(self.engine)
        self.context_mgr: BrowserContextManager = BrowserContextManager()
        self.planner: BrowserTaskPlanner = BrowserTaskPlanner()
        self.parser: BrowserIntentParser = BrowserIntentParser()
        self.intent_engine: NaturalLanguageIntentEngine = NaturalLanguageIntentEngine()
        self.router: BrowserActionRouter = BrowserActionRouter(
            self.engine, self.sessions, self.context_mgr
        )
        self._lock = threading.RLock()
        self._stop_requested = threading.Event()
        self._is_initialized = False

    def initialize(self) -> None:
        """Initialize browser engine and automation resources."""
        with self._lock:
            if self._is_initialized:
                return
            logger.info("Initializing BrowserManager (browser=%s)...", self.browser_name)
            self.engine.initialize()
            self._is_initialized = True
            logger.info("BrowserManager initialized successfully.")

    def is_browser_command(self, text: str) -> bool:
        """Fast check to determine if natural language text represents an action command."""
        action = self.intent_engine.parse(text, allow_ai_fallback=False)
        if action.intent != CanonicalIntent.GENERAL_CONVERSATION:
            return True
        return self.parser.parse(text) is not None

    def execute_command(self, text: str) -> BrowserResult | None:
        """Parse natural language command through layered intent engine and execute."""
        # 1. Layered Natural Language Intent Classification
        action: StructuredAction = self.intent_engine.parse(text, allow_ai_fallback=True)

        if action.intent == CanonicalIntent.GENERAL_CONVERSATION:
            # Check legacy parser fallback
            legacy_plan = self.parser.parse(text)
            if legacy_plan is not None:
                return self.execute_plan(legacy_plan)
            return None

        # 2. Desktop App Launch Intent
        if action.intent == CanonicalIntent.LAUNCH_APP:
            app_name = action.parameters.get("app_name", "Application")
            success = UniversalActionRouter.execute_app_launch(app_name)
            spoken = f"Opening {app_name}."
            return BrowserResult(
                success=success,
                action_type=ActionType.OPEN_SITE,
                message=f"Launched desktop application: {app_name}.",
                spoken_response=spoken,
            )

        # 3. Translate StructuredAction to BrowserActionPlan
        plan = structured_action_to_browser_plan(action)
        if plan is None:
            plan = self.parser.parse(text)

        if plan is None:
            return None

        return self.execute_plan(plan)

    def execute_plan(self, plan: BrowserActionPlan) -> BrowserResult:
        """Execute a parsed BrowserActionPlan through safety checks, planner, and skill router."""
        if not self._is_initialized:
            self.initialize()

        self._stop_requested.clear()

        # Synchronize with real browser state if command depends on active browser window
        if plan.action_type in (
            ActionType.READ_PAGE,
            ActionType.SUMMARIZE_PAGE,
            ActionType.EXPLAIN_PAGE,
            ActionType.SWITCH_TAB,
            ActionType.SCROLL_PAGE,
            ActionType.NAVIGATE_BACK,
            ActionType.NAVIGATE_FORWARD,
            ActionType.CLOSE_TAB,
            ActionType.SEARCH_CURRENT_TAB,
            ActionType.OPEN_NEW_TAB,
        ):
            try:
                state = self.engine.refresh_browser_state()
                logger.debug("Refreshed browser state before %s: %s", plan.action_type.value, state)
            except Exception as e:
                logger.debug("State refresh note: %s", e)

        # 1. Stop / Cancel commands
        if plan.action_type == ActionType.STOP_ACTION:
            self.stop_active_task()
            msg = "Stopped browser tasks."
            return BrowserResult(
                success=True,
                action_type=plan.action_type,
                message=msg,
                spoken_response=msg,
            )

        # 2. Evaluate Safety Policy
        safe_plan = BrowserSafetyPolicy.evaluate(plan)

        # 3. Check for sensitive confirmation requirement
        if safe_plan.requires_confirmation:
            logger.warning("Action '%s' blocked by safety policy requiring confirmation.", plan.action_type.value)
            return BrowserResult(
                success=False,
                action_type=plan.action_type,
                message=safe_plan.confirmation_prompt,
                spoken_response=safe_plan.confirmation_prompt,
                error="Confirmation required for sensitive action",
                metadata={"requires_confirmation": True, "prompt": safe_plan.confirmation_prompt},
            )

        # 4. Handle Multi-Step Deep Web Research
        if plan.action_type == ActionType.RESEARCH_TOPIC:
            try:
                return self.planner.execute_research(
                    query=plan.query,
                    engine=self.engine,
                    sessions=self.sessions,
                    context_mgr=self.context_mgr,
                    stop_event=self._stop_requested,
                )
            except BrowserActionCancelled as exc:
                self._publish_event(NovaEvent.BROWSER_TASK_CANCELLED, reason=str(exc))
                return BrowserResult(
                    success=True,
                    action_type=plan.action_type,
                    message="Browser research was cancelled.",
                    spoken_response="I've cancelled the research.",
                )
            except Exception as exc:
                logger.error("Research execution failed: %s", exc, exc_info=True)
                return BrowserResult(
                    success=False,
                    action_type=plan.action_type,
                    message=f"Research failed: {exc}",
                    spoken_response="Sorry Boss, something went wrong while researching.",
                    error=str(exc),
                )

        from ui.health_checker import DashboardStatsManager

        # Record activity understanding and actions
        if plan.action_type == ActionType.SEARCH_CURRENT_TAB:
            DashboardStatsManager.record_understood("Browser Search", details={"Target": "Current Tab", "Task": "Search", "Query": plan.query})
            DashboardStatsManager.record_action(f'Searching for "{plan.query}" in current tab')
        elif plan.action_type == ActionType.OPEN_NEW_TAB:
            browser_name = plan.metadata.get("browser", "Chrome") if plan.metadata else "Chrome"
            DashboardStatsManager.record_understood("Open New Tab", details={"Browser": browser_name})
            DashboardStatsManager.record_action("Opening new browser tab")
        elif plan.action_type in (ActionType.SEARCH_WEB, ActionType.SEARCH_SITE):
            site_name = (plan.platform.value if plan.platform else "web").title()
            DashboardStatsManager.record_understood("Browser Task", details={"Website": site_name, "Task": "Search", "Query": plan.query})
            DashboardStatsManager.record_action(f"Opening {site_name}")
            DashboardStatsManager.record_action(f'Searching for "{plan.query}"')
        elif plan.action_type in (ActionType.PLAY_MEDIA, ActionType.WATCH_VIDEO):
            site_name = (plan.platform.value if plan.platform else "YouTube").title()
            DashboardStatsManager.record_understood("PLAY_MEDIA", details={"Query": plan.query, "Platform": site_name})
            DashboardStatsManager.record_action(f"Playing {plan.query} on {site_name}")
        elif plan.action_type == ActionType.OPEN_SITE:
            site_name = plan.target_url or (plan.platform.value.title() if plan.platform else "Browser")
            DashboardStatsManager.record_understood("Browser Task", details={"Website": site_name, "Task": "Open"})
            DashboardStatsManager.record_action(f"Opening {site_name}")

        # 5. Publish BROWSER_ACTION_STARTED on EventBus
        self._publish_event(
            NovaEvent.BROWSER_ACTION_STARTED,
            action=plan.action_type.value,
            platform=plan.platform.value,
            query=plan.query,
        )

        # 6. Route and execute through router
        result = self.router.route(safe_plan)

        # 7. Publish completion / failure / cancellation on EventBus & Record Activity Result
        if result.success:
            if plan.action_type in (ActionType.STOP_AUTO_SHORTS, ActionType.STOP_ACTION):
                self._publish_event(
                    NovaEvent.BROWSER_ACTION_CANCELLED,
                    action=plan.action_type.value,
                    message=result.message,
                )
                DashboardStatsManager.record_result("Browser task cancelled", success=True)
            else:
                self._publish_event(
                    NovaEvent.BROWSER_ACTION_COMPLETED,
                    action=plan.action_type.value,
                    url=result.url,
                    message=result.message,
                )
                res_msg = "Search completed" if "search" in plan.action_type.value.lower() else (result.message or "Browser task completed")
                DashboardStatsManager.record_result(f"✓ {res_msg}", success=True)
        else:
            self._publish_event(
                NovaEvent.BROWSER_ACTION_FAILED,
                action=plan.action_type.value,
                error=result.error or "Unknown error",
            )
            DashboardStatsManager.record_result(f"✗ {result.error or result.message or 'Browser action failed'}", success=False)

        return result

    def stop_active_task(self) -> bool:
        """Interrupt and cancel any running background browser loop or active research."""
        self._stop_requested.set()
        stopped_shorts = self.sessions.stop_active_task()
        self._publish_event(
            NovaEvent.BROWSER_ACTION_CANCELLED,
            action="stop_active_task",
            message="Active browser task cancelled.",
        )
        return True

    def _publish_event(self, event: NovaEvent, **payload: Any) -> None:
        """Helper to publish events on canonical EventBus."""
        try:
            if registry.exists("event_bus"):
                bus = registry.get("event_bus")
                bus.publish(event, **payload)
        except Exception as exc:
            logger.debug("Failed to publish event %s: %s", event.value, exc)

    def shutdown(self) -> None:
        """Tear down browser sessions, context, and engine."""
        with self._lock:
            self.stop_active_task()
            self.sessions.shutdown()
            self.context_mgr.reset()
            self.engine.shutdown()
            self._is_initialized = False
            logger.info("BrowserManager shut down.")
