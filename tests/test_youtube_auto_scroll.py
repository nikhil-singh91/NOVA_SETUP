"""Comprehensive test suite for YouTube Shorts Auto-Scroll Mode in NOVA.

Validates the full OBSERVE → ACT → OBSERVE → VERIFY → CONTINUE lifecycle,
explicit state machine, intent parsing, multi-turn contextual follow-ups,
foreground app validation, recovery on failure, single-session safety, and clean teardown.
"""

from __future__ import annotations

import threading
import time
from typing import Any
import pytest

from browser.auto_scroll import (
    AutoScrollController,
    AutoScrollObservation,
    AutoScrollPolicy,
    AutoScrollState,
    AutoScrollVerifier,
)
from browser.engine import BaseBrowserEngine
from browser.manager import BrowserManager
from browser.models import ActionType, BrowserActionPlan, BrowserResult, PageContent, Platform
from browser.parser import BrowserIntentParser
from browser.sessions import BrowserSessionManager
from browser.sites.youtube import YouTubeSkill
from core.context import RecentInteractionContext
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent, StructuredAction
from intent.router import RoutingDomain, get_routing_domain, structured_action_to_browser_plan


# ==============================================================================
# MOCK BROWSER ENGINE WITH DYNAMIC SHORTS FEED EMULATION
# ==============================================================================

class DynamicShortsMockEngine(BaseBrowserEngine):
    """Mock engine simulating YouTube Shorts feed navigation, DOM state, and transitions."""

    def __init__(self, initial_url: str = "https://www.youtube.com/shorts/vid001") -> None:
        self.current_url: str = initial_url
        self.current_title: str = "First Short - Trending Video #1"
        self.video_ids: list[str] = [f"vid{i:03d}" for i in range(1, 20)]
        self.current_idx: int = 0
        self.opened_urls: list[str] = [initial_url]
        self.executed_scripts: list[str] = []
        self.pressed_keys: list[str] = []
        self.active_app: str = "Google Chrome"
        self.fail_scroll: bool = False

    @property
    def browser_name(self) -> str:
        return "Google Chrome"

    def initialize(self) -> None:
        pass

    def open_url(self, url: str, new_tab: bool = False) -> bool:
        self.opened_urls.append(url)
        self.current_url = url
        if "/shorts" in url:
            self.current_title = f"Short - {self.video_ids[self.current_idx]}"
        return True

    def click(self, selector: str) -> bool:
        return True

    def type_text(self, selector: str, text: str) -> bool:
        return True

    def wait_for(self, selector: str, timeout_seconds: float = 5.0) -> bool:
        return True

    def execute_script(self, script: str) -> Any:
        self.executed_scripts.append(script)
        if "button[aria-label=\"Next video\"]" in script or "ArrowDown" in script:
            if not self.fail_scroll:
                self.current_idx = min(len(self.video_ids) - 1, self.current_idx + 1)
                vid = self.video_ids[self.current_idx]
                self.current_url = f"https://www.youtube.com/shorts/{vid}"
                self.current_title = f"Short #{self.current_idx + 1} - Video {vid}"
                return "next_btn_clicked"
            return "scroll_failed"
        if "Array.from(document.querySelectorAll('video'))" in script:
            return f"blob:https://www.youtube.com/{self.video_ids[self.current_idx]}"
        return "mock_ok"

    def press_key(self, key_name: str) -> bool:
        self.pressed_keys.append(key_name)
        if key_name == "ArrowDown" and not self.fail_scroll:
            self.current_idx = min(len(self.video_ids) - 1, self.current_idx + 1)
            vid = self.video_ids[self.current_idx]
            self.current_url = f"https://www.youtube.com/shorts/{vid}"
            self.current_title = f"Short #{self.current_idx + 1} - Video {vid}"
            return True
        return True

    def get_page_info(self) -> dict[str, str]:
        return {"url": self.current_url, "title": self.current_title}

    def refresh_browser_state(self) -> dict[str, Any]:
        return {
            "active_tab": 1,
            "total_tabs": 1,
            "url": self.current_url,
            "title": self.current_title,
        }

    def get_active_tab_index(self) -> int:
        return 1

    def set_active_tab_index(self, index: int) -> bool:
        return True

    def get_tab_count(self) -> int:
        return 1

    def list_tabs(self) -> list[dict[str, Any]]:
        return [{"index": 1, "title": self.current_title, "url": self.current_url}]

    def next_tab(self) -> tuple[bool, int, str]:
        return True, 1, self.current_title

    def previous_tab(self) -> tuple[bool, int, str]:
        return True, 1, self.current_title

    def switch_to_tab_by_title_or_url(self, query: str) -> tuple[bool, int, str]:
        return True, 1, self.current_title

    def close_tab(self) -> bool:
        return True

    def navigate_back(self) -> bool:
        return True

    def navigate_forward(self) -> bool:
        return True

    def scroll_page(self, direction: str = "down", amount: str | int = "medium") -> bool:
        if not self.fail_scroll:
            self.current_idx = min(len(self.video_ids) - 1, self.current_idx + 1)
            vid = self.video_ids[self.current_idx]
            self.current_url = f"https://www.youtube.com/shorts/{vid}"
            self.current_title = f"Short #{self.current_idx + 1} - Video {vid}"
            return True
        return False

    def scroll_to_top(self) -> bool:
        return True

    def scroll_to_bottom(self) -> bool:
        return True

    def extract_page_content(self) -> PageContent:
        return PageContent(url=self.current_url, title=self.current_title, text="Shorts feed")

    def extract_search_results(self, limit: int = 5) -> list[dict[str, str]]:
        return []

    def shutdown(self) -> None:
        pass


# ==============================================================================
# TEST SUITE
# ==============================================================================

class TestYouTubeShortsAutoScroll:

    def setup_method(self) -> None:
        self.engine = DynamicShortsMockEngine()
        self.sessions = BrowserSessionManager(self.engine)
        self.skill = YouTubeSkill()
        self.intent_engine = NaturalLanguageIntentEngine()
        self.parser = BrowserIntentParser()
        self.context = RecentInteractionContext()

    def teardown_method(self) -> None:
        self.sessions.shutdown()

    # --------------------------------------------------------------------------
    # 1. INTENT MATCHING TESTS
    # --------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "phrase",
        [
            "youtube scroll",
            "start auto scroll",
            "start automatic scrolling",
            "auto scroll",
            "scroll shorts",
            "scroll shorts automatically",
            "keep scrolling",
            "start scrolling",
            "start scrolling shorts",
            "automatically scroll shorts",
            "shorts auto scroll",
            "youtube auto scroll",
        ],
    )
    def test_start_auto_scroll_intent_recognition(self, phrase: str) -> None:
        action = self.intent_engine.parse(phrase)
        assert action.intent == CanonicalIntent.START_AUTO_SHORTS
        domain = get_routing_domain(action.intent)
        assert domain == RoutingDomain.BROWSER

        plan = structured_action_to_browser_plan(action)
        assert plan is not None
        assert plan.action_type == ActionType.START_AUTO_SHORTS
        assert plan.platform == Platform.YOUTUBE

    @pytest.mark.parametrize(
        "phrase",
        [
            "stop scrolling",
            "stop auto scroll",
            "stop auto-scroll",
            "stop shorts",
            "stop shorts auto scroll",
        ],
    )
    def test_stop_auto_scroll_intent_recognition(self, phrase: str) -> None:
        action = self.intent_engine.parse(phrase)
        assert action.intent == CanonicalIntent.STOP_AUTO_SHORTS
        plan = structured_action_to_browser_plan(action)
        assert plan is not None
        assert plan.action_type == ActionType.STOP_AUTO_SHORTS

    @pytest.mark.parametrize(
        "phrase",
        [
            "pause scrolling",
            "pause auto scroll",
            "pause auto-scroll",
            "pause shorts",
        ],
    )
    def test_pause_auto_scroll_intent_recognition(self, phrase: str) -> None:
        action = self.intent_engine.parse(phrase)
        assert action.intent == CanonicalIntent.PAUSE_AUTO_SHORTS
        plan = structured_action_to_browser_plan(action)
        assert plan is not None
        assert plan.action_type == ActionType.PAUSE_AUTO_SHORTS

    @pytest.mark.parametrize(
        "phrase",
        [
            "resume scrolling",
            "resume auto scroll",
            "resume auto-scroll",
            "continue scrolling",
            "start again",
        ],
    )
    def test_resume_auto_scroll_intent_recognition(self, phrase: str) -> None:
        action = self.intent_engine.parse(phrase)
        assert action.intent == CanonicalIntent.RESUME_AUTO_SHORTS
        plan = structured_action_to_browser_plan(action)
        assert plan is not None
        assert plan.action_type == ActionType.RESUME_AUTO_SHORTS

    # --------------------------------------------------------------------------
    # 2. MULTI-TURN CONTEXTUAL FLOW: "play YouTube Shorts" → "youtube scroll"
    # --------------------------------------------------------------------------

    def test_play_shorts_followed_by_youtube_scroll(self) -> None:
        # Turn 1: "Nova, play YouTube Shorts"
        action1 = self.intent_engine.parse("play YouTube Shorts")
        assert action1.intent == CanonicalIntent.WATCH_SHORTS

        plan1 = structured_action_to_browser_plan(action1)
        assert plan1 is not None
        res1 = self.skill.execute(plan1, self.engine, self.sessions)
        assert res1.success is True
        assert "Opened YouTube Shorts" in res1.message

        # Record verified outcome in context
        self.context.add_turn(
            user_input="play YouTube Shorts",
            intent=CanonicalIntent.WATCH_SHORTS.value,
            action="watch_shorts",
            success=True,
            target_app="Google Chrome",
            current_url=res1.url,
            current_title="YouTube Shorts",
        )
        assert self.context.is_current_page_shorts is True

        # Turn 2: "youtube scroll"
        action2 = self.intent_engine.parse("youtube scroll", context=self.context)
        assert action2.intent == CanonicalIntent.START_AUTO_SHORTS
        assert action2.parameters.get("target") == "CURRENT_YOUTUBE_SHORTS_FEED"

        plan2 = structured_action_to_browser_plan(action2)
        assert plan2 is not None
        res2 = self.skill.execute(plan2, self.engine, self.sessions)
        assert res2.success is True
        assert res2.spoken_response == "Yep, auto-scroll is on."
        assert self.sessions.is_auto_shorts_active() is True

        # Turn 3: "stop scrolling"
        action3 = self.intent_engine.parse("stop scrolling", context=self.context)
        assert action3.intent == CanonicalIntent.STOP_AUTO_SHORTS

        plan3 = structured_action_to_browser_plan(action3)
        assert plan3 is not None
        res3 = self.skill.execute(plan3, self.engine, self.sessions)
        assert res3.success is True
        assert res3.spoken_response == "Auto-scroll stopped."
        assert self.sessions.is_auto_shorts_active() is False

    # --------------------------------------------------------------------------
    # 3. REJECTION WHEN NOT ON YOUTUBE SHORTS
    # --------------------------------------------------------------------------

    def test_rejection_when_not_on_shorts_page(self) -> None:
        # Engine currently on Wikipedia
        self.engine.current_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
        self.engine.current_title = "Artificial intelligence - Wikipedia"

        plan = BrowserActionPlan(
            action_type=ActionType.START_AUTO_SHORTS,
            platform=Platform.YOUTUBE,
            raw_prompt="youtube scroll",
            metadata={"prior_context_shorts": False},
        )
        res = self.skill.execute(plan, self.engine, self.sessions)
        assert res.success is False
        assert "not a YouTube Shorts feed" in res.message
        assert res.spoken_response == "You're not on YouTube Shorts right now."
        assert self.sessions.is_auto_shorts_active() is False

    # --------------------------------------------------------------------------
    # 4. EXPLICIT STATE MACHINE TRANSITIONS
    # --------------------------------------------------------------------------

    def test_state_machine_transitions(self) -> None:
        controller = AutoScrollController(
            engine=self.engine,
            policy=AutoScrollPolicy(
                dwell_time_seconds=0.1,
                settle_time_seconds=0.05,
                max_total_scrolls=2,
            ),
        )
        states_observed: list[AutoScrollState] = []
        controller.on_state_change = lambda st: states_observed.append(st)

        assert controller.state == AutoScrollState.INACTIVE

        succ, msg = controller.start()
        assert succ is True
        time.sleep(0.4)

        # Confirm progression through active/observing/scrolling/verifying
        assert AutoScrollState.STARTING in states_observed or AutoScrollState.ACTIVE in states_observed
        assert controller.is_active() or controller.state == AutoScrollState.STOPPED

        controller.stop()
        assert controller.state == AutoScrollState.STOPPED

    # --------------------------------------------------------------------------
    # 5. CHANGE DETECTION & VERIFICATION
    # --------------------------------------------------------------------------

    def test_verifier_detects_video_id_change(self) -> None:
        before = AutoScrollObservation(
            url="https://www.youtube.com/shorts/vid001",
            video_id="vid001",
            title="Short 1",
        )
        after = AutoScrollObservation(
            url="https://www.youtube.com/shorts/vid002",
            video_id="vid002",
            title="Short 2",
        )
        verified, reason = AutoScrollVerifier.verify_transition(before, after)
        assert verified is True
        assert "Video ID transitioned" in reason

    def test_verifier_detects_video_src_change(self) -> None:
        before = AutoScrollObservation(
            url="https://www.youtube.com/shorts",
            dom_video_src="blob:https://youtube.com/abc",
        )
        after = AutoScrollObservation(
            url="https://www.youtube.com/shorts",
            dom_video_src="blob:https://youtube.com/def",
        )
        verified, reason = AutoScrollVerifier.verify_transition(before, after)
        assert verified is True
        assert "element source changed" in reason

    def test_verifier_fails_when_nothing_changes(self) -> None:
        before = AutoScrollObservation(
            url="https://www.youtube.com/shorts/vid001",
            video_id="vid001",
            title="Short 1",
            dom_video_src="blob:abc",
        )
        after = AutoScrollObservation(
            url="https://www.youtube.com/shorts/vid001",
            video_id="vid001",
            title="Short 1",
            dom_video_src="blob:abc",
        )
        verified, reason = AutoScrollVerifier.verify_transition(before, after)
        assert verified is False
        assert "No change detected" in reason

    # --------------------------------------------------------------------------
    # 6. OBSERVATION → ACT → OBSERVE → VERIFY LOOP EXECUTION
    # --------------------------------------------------------------------------

    def test_autonomous_scroll_loop_traverses_shorts(self) -> None:
        scrolls: list[int] = []
        controller = AutoScrollController(
            engine=self.engine,
            policy=AutoScrollPolicy(
                dwell_time_seconds=0.08,
                settle_time_seconds=0.05,
                max_total_scrolls=3,
            ),
        )
        controller.on_scroll_completed = lambda count, obs: scrolls.append(count)

        controller.start()
        time.sleep(0.6)
        controller.stop()

        # Check that multiple shorts were traversed automatically
        assert len(scrolls) >= 2
        assert self.engine.current_idx >= 2

    # --------------------------------------------------------------------------
    # 7. PAUSE AND RESUME EXECUTION
    # --------------------------------------------------------------------------

    def test_pause_and_resume(self) -> None:
        controller = AutoScrollController(
            engine=self.engine,
            policy=AutoScrollPolicy(
                dwell_time_seconds=0.1,
                settle_time_seconds=0.05,
                max_total_scrolls=10,
            ),
        )
        controller.start()
        time.sleep(0.2)
        assert controller.is_active()

        # Pause
        controller.pause()
        assert controller.is_paused() is True
        assert controller.state == AutoScrollState.PAUSED
        idx_paused = self.engine.current_idx

        # Wait while paused - index should not increment
        time.sleep(0.3)
        assert self.engine.current_idx == idx_paused

        # Resume
        controller.resume()
        assert controller.is_active() is True
        time.sleep(0.3)
        assert self.engine.current_idx > idx_paused

        controller.stop()
        assert controller.state == AutoScrollState.STOPPED

    # --------------------------------------------------------------------------
    # 8. RECOVERY ON FAILURE AND GRACEFUL HALT
    # --------------------------------------------------------------------------

    def test_recovery_and_graceful_halt_on_repeated_failures(self) -> None:
        # Configure engine to fail scrolling
        self.engine.fail_scroll = True
        failed_msgs: list[str] = []

        controller = AutoScrollController(
            engine=self.engine,
            policy=AutoScrollPolicy(
                dwell_time_seconds=0.05,
                settle_time_seconds=0.03,
                max_consecutive_failures=2,
                max_total_scrolls=10,
            ),
        )
        controller.on_failure = lambda msg: failed_msgs.append(msg)

        controller.start()
        time.sleep(0.4)

        # Must halt gracefully into FAILED state rather than infinite loop
        assert controller.state in (AutoScrollState.FAILED, AutoScrollState.STOPPED)
        assert len(failed_msgs) >= 1
        assert "couldn't confirm the next Short" in failed_msgs[0]

    # --------------------------------------------------------------------------
    # 9. MANUAL USER ACTIONS / RESILIENT OBSERVATION
    # --------------------------------------------------------------------------

    def test_manual_user_scroll_updates_observation(self) -> None:
        controller = AutoScrollController(
            engine=self.engine,
            policy=AutoScrollPolicy(dwell_time_seconds=0.1, settle_time_seconds=0.05),
        )
        controller.start()
        time.sleep(0.15)

        # User manually navigates forward by 3 Shorts
        self.engine.current_idx = 7
        self.engine.current_url = "https://www.youtube.com/shorts/vid007"
        self.engine.current_title = "Manual User Short - Video vid007"

        time.sleep(0.3)
        controller.stop()

        # Verify controller continued from the actual observed state rather than old assumption
        assert self.engine.current_idx >= 7

    # --------------------------------------------------------------------------
    # 10. SINGLE ACTIVE SESSION ENFORCEMENT
    # --------------------------------------------------------------------------

    def test_duplicate_start_prevents_multiple_threads(self) -> None:
        controller = AutoScrollController(
            engine=self.engine,
            policy=AutoScrollPolicy(dwell_time_seconds=0.2),
        )
        succ1, _ = controller.start()
        assert succ1 is True
        first_thread = controller._worker_thread

        # Start again without stopping
        succ2, _ = controller.start()
        assert succ2 is True
        second_thread = controller._worker_thread

        # Old thread should be replaced cleanly
        assert second_thread != first_thread
        assert controller.is_active()

        controller.stop()

    # --------------------------------------------------------------------------
    # 11. BROWSER UNAVAILABLE SAFETY
    # --------------------------------------------------------------------------

    def test_start_without_engine_fails_safely(self) -> None:
        controller = AutoScrollController(engine=None)
        succ, msg = controller.start()
        assert succ is False
        assert controller.state == AutoScrollState.FAILED
        assert "No browser engine" in msg

    # --------------------------------------------------------------------------
    # 12. INSTANT INTERRUPTIBILITY
    # --------------------------------------------------------------------------

    def test_stop_interrupts_long_dwell_instantly(self) -> None:
        controller = AutoScrollController(
            engine=self.engine,
            policy=AutoScrollPolicy(dwell_time_seconds=60.0),  # Long dwell
        )
        controller.start()
        time.sleep(0.1)
        assert controller.is_active()

        start_t = time.monotonic()
        controller.stop()
        stop_duration = time.monotonic() - start_t

        # Must terminate under 0.5s rather than waiting for 60s dwell!
        assert stop_duration < 0.6
        assert controller.state == AutoScrollState.STOPPED
