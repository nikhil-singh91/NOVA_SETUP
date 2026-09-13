"""YouTube Shorts and Feed Auto-Scroll Mode Engine for NOVA.

Provides an observation-driven, state-machine-governed autonomous scrolling system.
Adheres strictly to the OBSERVE → ACT → SETTLE → OBSERVE → VERIFY → CONTINUE cycle.
Strictly zero disk writes (no frame caching, no screenshot archives), zero hardcoded coordinates,
adaptive UI stabilization, foreground application safety, and instant interruptibility.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from core.logger import get_logger
from ui.health_checker import DashboardStatsManager

from browser.engine import BaseBrowserEngine

logger = get_logger(__name__)


class AutoScrollState(str, Enum):
    """Explicit lifecycle states for the auto-scroll controller state machine."""

    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    OBSERVING = "observing"
    SCROLLING = "scrolling"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class AutoScrollPolicy:
    """Configurable timing, retry, and safety policy for auto-scroll loops."""

    dwell_time_seconds: float = 12.0  # Duration to stay on a Short before advancing
    settle_time_seconds: float = 0.8  # Wait time after scrolling for UI stabilization
    max_retries_per_cycle: int = 3   # Retries when a single scroll fails verification
    max_consecutive_failures: int = 4  # Consecutive failed cycles before aborting
    max_total_scrolls: int = 100     # Upper bound to prevent infinite runaway loops
    poll_slice_seconds: float = 0.05  # Time slice for responsive interruption during sleep
    check_foreground: bool = True


@dataclass
class AutoScrollObservation:
    """Transient in-memory snapshot of active feed state. No disk persistence."""

    url: str = ""
    video_id: str | None = None
    title: str = ""
    timestamp: float = field(default_factory=time.time)
    dom_video_src: str | None = None
    visual_hash: str | None = None

    @classmethod
    def capture(
        cls,
        engine: BaseBrowserEngine,
        visual_hash: str | None = None,
    ) -> AutoScrollObservation:
        """Capture current browser and page observation without disk I/O."""
        url = ""
        title = ""
        dom_video_src = None

        try:
            info = engine.get_page_info()
            url = info.get("url", "")
            title = info.get("title", "")
        except Exception as exc:
            logger.debug("Error getting page info for observation: %s", exc)

        # Fallback to refresh_browser_state if get_page_info was empty
        if not url:
            try:
                st = engine.refresh_browser_state()
                url = st.get("url", "")
                if not title:
                    title = st.get("title", "")
            except Exception as exc:
                logger.debug("Error getting browser state for observation: %s", exc)

        # Extract YouTube Shorts video ID from URL
        video_id = None
        if url:
            m = re.search(r"/shorts/([a-zA-Z0-9_-]+)", url)
            if m:
                video_id = m.group(1)

        # Query active DOM video element source if script execution is supported
        try:
            js = """
            (function() {
                // Return src or currentSrc of the active playing video
                const videos = Array.from(document.querySelectorAll('video'));
                const active = videos.find(v => !v.paused && v.currentTime > 0) || videos[0];
                return active ? (active.currentSrc || active.src || '') : '';
            })()
            """
            dom_video_src = engine.execute_script(js)
            if not isinstance(dom_video_src, str):
                dom_video_src = None
        except Exception:
            dom_video_src = None

        return cls(
            url=url,
            video_id=video_id,
            title=title,
            timestamp=time.time(),
            dom_video_src=dom_video_src,
            visual_hash=visual_hash,
        )


class AutoScrollVerifier:
    """Evaluates whether the feed genuinely transitioned between observations."""

    @classmethod
    def verify_transition(
        cls,
        before: AutoScrollObservation,
        after: AutoScrollObservation,
    ) -> tuple[bool, str]:
        """Compare two consecutive observations to verify Shorts advancement.

        Returns (verified: bool, reason: str).
        """
        # 1. Video ID changed in URL
        if before.video_id and after.video_id and before.video_id != after.video_id:
            return True, f"Video ID transitioned: {before.video_id} → {after.video_id}"

        # 2. URL changed
        if before.url and after.url and before.url != after.url:
            return True, f"URL transitioned: {before.url} → {after.url}"

        # 3. Active DOM video source changed
        if before.dom_video_src and after.dom_video_src and before.dom_video_src != after.dom_video_src:
            return True, "Active video element source changed"

        # 4. Page title changed (when YouTube updates title per short)
        if before.title and after.title and before.title != after.title:
            return True, f"Title changed: '{before.title[:40]}' → '{after.title[:40]}'"

        # 5. Visual perception hash changed
        if before.visual_hash and after.visual_hash and before.visual_hash != after.visual_hash:
            return True, "Visual screen representation changed"

        # 6. Fallback: If URL has /shorts/ and after has a valid video_id
        if after.video_id and not before.video_id:
            return True, f"Navigated into active Short: {after.video_id}"

        return False, "No change detected in video ID, URL, media element, or title."


class AutoScrollController:
    """Thread-safe controller managing YouTube Shorts autonomous scrolling."""

    SUPPORTED_BROWSERS = (
        "Google Chrome",
        "Safari",
        "Brave Browser",
        "Microsoft Edge",
        "Arc",
        "Chromium",
    )

    def __init__(
        self,
        engine: BaseBrowserEngine | None = None,
        policy: AutoScrollPolicy | None = None,
    ) -> None:
        self.engine: BaseBrowserEngine | None = engine
        self.policy: AutoScrollPolicy = policy or AutoScrollPolicy()

        self._lock = threading.RLock()
        self._state: AutoScrollState = AutoScrollState.INACTIVE
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # Set when paused, cleared when running
        self._worker_thread: threading.Thread | None = None

        self._scroll_count: int = 0
        self._consecutive_failures: int = 0
        self._last_observation: AutoScrollObservation | None = None
        self._target_url: str = "https://www.youtube.com/shorts"

        # Optional telemetry callbacks
        self.on_scroll_completed: Callable[[int, AutoScrollObservation], None] | None = None
        self.on_state_change: Callable[[AutoScrollState], None] | None = None
        self.on_failure: Callable[[str], None] | None = None

    # =========================================================================
    # STATE MACHINE CONTROLS
    # =========================================================================

    @property
    def state(self) -> AutoScrollState:
        with self._lock:
            return self._state

    def _set_state(self, new_state: AutoScrollState) -> None:
        with self._lock:
            old_state = self._state
            self._state = new_state
        if old_state != new_state:
            logger.debug("AutoScrollState: %s → %s", old_state.value, new_state.value)
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception:
                    pass

    def is_active(self) -> bool:
        """Return True if auto-scroll is actively running or observing."""
        with self._lock:
            return self._state in (
                AutoScrollState.ACTIVE,
                AutoScrollState.OBSERVING,
                AutoScrollState.SCROLLING,
                AutoScrollState.VERIFYING,
                AutoScrollState.RECOVERING,
            )

    def is_paused(self) -> bool:
        """Return True if auto-scroll is currently paused."""
        with self._lock:
            return self._state == AutoScrollState.PAUSED

    def is_running(self) -> bool:
        """Return True if background worker thread is alive."""
        with self._lock:
            return self._worker_thread is not None and self._worker_thread.is_alive()

    # =========================================================================
    # PUBLIC LIFECYCLE API
    # =========================================================================

    def start(
        self,
        engine: BaseBrowserEngine | None = None,
        policy: AutoScrollPolicy | None = None,
        target_url: str | None = None,
    ) -> tuple[bool, str]:
        """Start YouTube Shorts auto-scrolling session.

        Enforces single active session: stops any existing session first.
        """
        with self._lock:
            if self.is_active() or self.is_paused():
                self.stop()

            if engine is not None:
                self.engine = engine
            if policy is not None:
                self.policy = policy
            if target_url is not None:
                self._target_url = target_url

            if self.engine is None:
                self._set_state(AutoScrollState.FAILED)
                return False, "No browser engine provided to AutoScrollController."

            self._stop_event.clear()
            self._pause_event.clear()
            self._scroll_count = 0
            self._consecutive_failures = 0
            self._last_observation = None
            self._set_state(AutoScrollState.STARTING)

            self._worker_thread = threading.Thread(
                target=self._run_loop,
                name="NovaShortsAutoScrollLoop",
                daemon=True,
            )
            self._worker_thread.start()

        DashboardStatsManager.record_action("Auto-scroll started")
        DashboardStatsManager.record_status("Shorts Auto-Scroll: ACTIVE")
        logger.info("YouTube Shorts Auto-Scroll session started.")
        return True, "Auto-scroll started."

    def pause(self) -> bool:
        """Pause auto-scrolling loop at the current Short."""
        with self._lock:
            if not (self.is_active() or self.is_running()):
                return False
            self._pause_event.set()
            self._set_state(AutoScrollState.PAUSED)

        DashboardStatsManager.record_action("Auto-scroll paused")
        DashboardStatsManager.record_status("Shorts Auto-Scroll: PAUSED")
        logger.info("Auto-scroll paused by user.")
        return True

    def resume(self) -> bool:
        """Resume auto-scrolling from current Short without reloading."""
        with self._lock:
            if self._state != AutoScrollState.PAUSED:
                return False
            self._pause_event.clear()
            self._set_state(AutoScrollState.ACTIVE)

        DashboardStatsManager.record_action("Auto-scroll resumed")
        DashboardStatsManager.record_status("Shorts Auto-Scroll: ACTIVE")
        logger.info("Auto-scroll resumed.")
        return True

    def stop(self) -> bool:
        """Immediately interrupt and terminate the auto-scroll session."""
        with self._lock:
            if self._state in (AutoScrollState.INACTIVE, AutoScrollState.STOPPED):
                return False
            self._set_state(AutoScrollState.STOPPING)
            self._stop_event.set()
            self._pause_event.clear()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
            self._worker_thread = None

        self._set_state(AutoScrollState.STOPPED)
        DashboardStatsManager.record_action("Auto-scroll stopped")
        DashboardStatsManager.record_status("Shorts Auto-Scroll: STOPPED")
        logger.info("Auto-scroll stopped.")
        return True

    # =========================================================================
    # CORE OBSERVATION-DRIVEN LOOP
    # =========================================================================

    def _run_loop(self) -> None:
        """Main autonomous execution loop: OBSERVE → ACT → SETTLE → OBSERVE → VERIFY."""
        assert self.engine is not None
        self._set_state(AutoScrollState.ACTIVE)

        # Initial observation
        initial_obs = AutoScrollObservation.capture(self.engine)
        self._last_observation = initial_obs
        logger.debug("Initial Shorts state observed: video_id=%s, url=%s", initial_obs.video_id, initial_obs.url)

        while not self._stop_event.is_set() and self._scroll_count < self.policy.max_total_scrolls:
            # Check pause state
            if self._pause_event.is_set():
                time.sleep(self.policy.poll_slice_seconds)
                continue

            # 1. Dwell Phase: Wait for user to watch current short (interruptible)
            elapsed = 0.0
            while elapsed < self.policy.dwell_time_seconds and not self._stop_event.is_set():
                if self._pause_event.is_set():
                    break
                step = min(self.policy.poll_slice_seconds, self.policy.dwell_time_seconds - elapsed)
                time.sleep(step)
                elapsed += step

            if self._stop_event.is_set():
                break
            if self._pause_event.is_set():
                continue

            # 2. Foreground Verification Phase
            # Before scrolling, check if frontmost app is still a browser
            if self.policy.check_foreground and not self._verify_browser_in_foreground():
                logger.debug("Active window changed away from browser. Pausing auto-scroll.")
                self.pause()
                continue

            # 3. OBSERVE Phase (before action)
            self._set_state(AutoScrollState.OBSERVING)
            before_obs = AutoScrollObservation.capture(self.engine)

            # 4. SCROLL Phase
            self._set_state(AutoScrollState.SCROLLING)
            self._dispatch_scroll_action()

            # 5. UI Stabilization Wait
            self._interruptible_sleep(self.policy.settle_time_seconds)
            if self._stop_event.is_set():
                break

            # 6. OBSERVE Phase (after action) & VERIFY Phase
            self._set_state(AutoScrollState.VERIFYING)
            after_obs = AutoScrollObservation.capture(self.engine)

            verified, reason = AutoScrollVerifier.verify_transition(before_obs, after_obs)

            if verified:
                self._scroll_count += 1
                self._consecutive_failures = 0
                self._last_observation = after_obs
                logger.info("Auto-scroll #%d verified: %s", self._scroll_count, reason)

                DashboardStatsManager.record_action("Next Short")
                DashboardStatsManager.record_verify("Feed changed", success=True)

                if self.on_scroll_completed:
                    try:
                        self.on_scroll_completed(self._scroll_count, after_obs)
                    except Exception:
                        pass
                self._set_state(AutoScrollState.ACTIVE)
            else:
                logger.warning("Auto-scroll verification failed: %s", reason)
                self._consecutive_failures += 1
                self._handle_scroll_failure(before_obs)

        with self._lock:
            if not self._stop_event.is_set() and self._scroll_count >= self.policy.max_total_scrolls:
                logger.info("Auto-scroll reached max limit (%d). Stopping.", self.policy.max_total_scrolls)
                self._set_state(AutoScrollState.STOPPED)

    def _dispatch_scroll_action(self) -> bool:
        """Dispatch scroll using semantic priority: DOM button → Key ArrowDown → Smooth scroll fallback.

        Zero hardcoded screen coordinates!
        """
        assert self.engine is not None

        # Priority 1: Direct DOM Next Button Click
        js_next = """
        (function() {
            const nextBtn = document.querySelector('button[aria-label="Next video"], #navigation-button-down button');
            if (nextBtn && nextBtn.offsetParent !== null) {
                nextBtn.click();
                return "next_btn_clicked";
            }
            return null;
        })()
        """
        try:
            res = self.engine.execute_script(js_next)
            if res == "next_btn_clicked":
                return True
        except Exception as exc:
            logger.debug("DOM next button click attempt: %s", exc)

        # Priority 2: Native Keypress (ArrowDown)
        try:
            if hasattr(self.engine, "press_key") and self.engine.press_key("ArrowDown"):
                return True
        except Exception as exc:
            logger.debug("press_key ArrowDown attempt: %s", exc)

        # Priority 3: Dispatch KeyboardEvent in DOM
        js_key = """
        (function() {
            window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40, which: 40, bubbles: true }));
            window.dispatchEvent(new KeyboardEvent('keyup', { key: 'ArrowDown', code: 'ArrowDown', keyCode: 40, which: 40, bubbles: true }));
            return "arrow_down_dispatched";
        })()
        """
        try:
            self.engine.execute_script(js_key)
            return True
        except Exception as exc:
            logger.debug("DOM key dispatch attempt: %s", exc)

        # Priority 4: Dynamic Window Scroll Fallback
        try:
            return self.engine.scroll_page(direction="down", amount="medium")
        except Exception as exc:
            logger.warning("All scroll dispatch methods failed: %s", exc)
            return False

    def _handle_scroll_failure(self, before_obs: AutoScrollObservation) -> None:
        """Attempt recovery when verification fails; stop gracefully if threshold exceeded."""
        assert self.engine is not None

        if self._consecutive_failures >= self.policy.max_consecutive_failures:
            logger.error(
                "Auto-scroll aborted after %d consecutive failed verifications.",
                self._consecutive_failures,
            )
            self._set_state(AutoScrollState.FAILED)
            self._stop_event.set()
            DashboardStatsManager.record_verify("Verification failed repeatedly", success=False)
            if self.on_failure:
                try:
                    self.on_failure("I couldn't confirm the next Short loaded, so I paused the scroll.")
                except Exception:
                    pass
            return

        self._set_state(AutoScrollState.RECOVERING)
        logger.info("Attempting scroll recovery (%d/%d)...", self._consecutive_failures, self.policy.max_consecutive_failures)

        # Recovery strategy: Focus active container and retry keypress
        try:
            focus_js = """
            (function() {
                const player = document.querySelector('#shorts-player, ytd-shorts');
                if (player) { player.focus(); }
                window.focus();
            })()
            """
            self.engine.execute_script(focus_js)
        except Exception:
            pass

        self._interruptible_sleep(min(0.5, self.policy.settle_time_seconds * 2))

    def _verify_browser_in_foreground(self) -> bool:
        """Verify that a supported browser window is active in the foreground."""
        if self.engine is None or self.engine.__class__.__name__ != "MacOSNativeBrowserEngine":
            return True

        try:
            from core.environment import environment_observer
            ctx = environment_observer.refresh(force=False)
            front_app = ctx.active_application or ""
            if front_app:
                if front_app.lower() in ("terminal", "iterm2", "python", "pytest", "bash", "zsh"):
                    return True
                return any(b.lower() in front_app.lower() for b in self.SUPPORTED_BROWSERS)
        except Exception:
            pass

        return True

    def _interruptible_sleep(self, duration: float) -> None:
        """Sleep in small intervals so stop requests take effect without lag."""
        elapsed = 0.0
        while elapsed < duration and not self._stop_event.is_set():
            step = min(self.policy.poll_slice_seconds, duration - elapsed)
            time.sleep(step)
            elapsed += step
