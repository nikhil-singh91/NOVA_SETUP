"""YouTube skill for media playback, structured candidate ranking, video discovery, and Shorts automation."""

from __future__ import annotations

import re
import ssl
import time
import urllib.parse
import urllib.request
from typing import Any

import certifi

from browser.engine import BaseBrowserEngine, log_browser_diagnostics
from browser.models import ActionType, BrowserActionPlan, BrowserResult, Platform
from browser.sessions import BrowserSessionManager
from browser.sites.base import BaseSiteSkill
from core.logger import get_logger
from media.models import MediaRequest, VideoCandidate
from media.service import MediaPlaybackService

logger = get_logger(__name__)


def _get_ssl_context() -> ssl.SSLContext:
    """Return SSL context configured with certifi bundle."""
    try:
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl._create_unverified_context()


class YouTubeSkill(BaseSiteSkill):
    """Specialized skill for YouTube automation, deterministic media scoring, and Shorts interaction."""

    BASE_URL = "https://www.youtube.com"
    SHORTS_URL = "https://www.youtube.com/shorts"

    def __init__(self) -> None:
        self.media_service: MediaPlaybackService = MediaPlaybackService()

    @property
    def name(self) -> str:
        return "youtube_skill"

    def can_handle(self, plan: BrowserActionPlan) -> bool:
        """Return True if this skill can handle the given browser action plan."""
        if plan.platform == Platform.YOUTUBE:
            return True
        if plan.action_type in (
            ActionType.PLAY_MEDIA,
            ActionType.WATCH_VIDEO,
            ActionType.WATCH_SHORTS,
            ActionType.START_AUTO_SHORTS,
            ActionType.STOP_AUTO_SHORTS,
            ActionType.NEXT_ITEM,
            ActionType.PREVIOUS_ITEM,
        ):
            return True
        return False

    def execute(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
    ) -> BrowserResult:
        """Execute YouTube-specific action plans."""
        # 1. Stop auto Shorts loop
        if plan.action_type == ActionType.STOP_AUTO_SHORTS:
            sessions.stop_active_task()
            return BrowserResult(
                success=True,
                action_type=plan.action_type,
                message="Stopped YouTube Shorts auto-scroll.",
                spoken_response="Stopped Shorts auto-scroll.",
            )

        # 2. Next Short
        if plan.action_type == ActionType.NEXT_ITEM:
            success = engine.press_key("ArrowDown")
            return BrowserResult(
                success=success,
                action_type=plan.action_type,
                message="Navigated to next Short.",
                spoken_response="Next Short.",
            )

        # 3. Previous Short
        if plan.action_type == ActionType.PREVIOUS_ITEM:
            success = engine.press_key("ArrowUp")
            return BrowserResult(
                success=success,
                action_type=plan.action_type,
                message="Navigated to previous Short.",
                spoken_response="Previous Short.",
            )

        # 4. Start / Watch Shorts
        if plan.action_type in (ActionType.WATCH_SHORTS, ActionType.START_AUTO_SHORTS):
            return self._handle_shorts(plan, engine, sessions)

        # 5. Play Media / Watch Video
        if plan.action_type in (ActionType.PLAY_MEDIA, ActionType.WATCH_VIDEO):
            return self._handle_play_media(plan, engine)

        # 6. Default YouTube Search / Open Site
        return self._handle_search(plan, engine)

    def _handle_play_media(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
    ) -> BrowserResult:
        """Search for a video, score multiple candidates, and open the verified top YouTube watch page."""
        query = (plan.query or "").strip()
        if not query:
            query = "Trending Music"

        logger.info("Resolving YouTube video candidates for media request: '%s'", query)
        selected_candidate, req, candidates = self.media_service.resolve_best_video(query)

        if selected_candidate:
            watch_url = selected_candidate.url
            success = engine.open_url(watch_url)
            time.sleep(0.5)

            # Post-Playback Verification
            display_name = selected_candidate.title
            spoken = f"Playing {query} on YouTube."
            log_browser_diagnostics(
                "PLAY_YOUTUBE_VIDEO",
                "SUCCESS" if success else "FAILED",
                url=watch_url,
                title=display_name,
            )
            return BrowserResult(
                success=success,
                action_type=plan.action_type,
                message=f"Playing '{display_name}' on YouTube (Score: {selected_candidate.score:.2f}).",
                spoken_response=spoken,
                url=watch_url,
                metadata={
                    "video_title": display_name,
                    "watch_url": watch_url,
                    "match_score": selected_candidate.score,
                    "channel": selected_candidate.channel,
                    "duration": selected_candidate.duration_str,
                },
            )

        # Fallback to search results page if no candidate passed threshold
        encoded = urllib.parse.quote_plus(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        success = engine.open_url(search_url)
        spoken = f"Searching YouTube for {query}."
        log_browser_diagnostics("PLAY_YOUTUBE_FALLBACK", "SEARCH_PAGE", url=search_url)
        return BrowserResult(
            success=success,
            action_type=plan.action_type,
            message=f"Searching YouTube for '{query}'.",
            spoken_response=spoken,
            url=search_url,
        )

    def _handle_shorts(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
    ) -> BrowserResult:
        """Handle watching YouTube Shorts and optional background auto-scroll loop."""
        success = engine.open_url(self.SHORTS_URL)
        if not success:
            return BrowserResult(
                success=False,
                action_type=plan.action_type,
                error="Failed to open YouTube Shorts URL.",
                spoken_response="Sorry Boss, I couldn't open YouTube Shorts.",
            )

        if plan.auto_navigation:
            logger.info("Starting background YouTube Shorts auto-scroll loop...")
            sessions.start_auto_shorts_loop()
            return BrowserResult(
                success=True,
                action_type=plan.action_type,
                message="Watching YouTube Shorts automatically.",
                spoken_response="Watching YouTube Shorts with auto-scrolling. Say 'Nova stop' when you want to stop.",
                url=self.SHORTS_URL,
            )

        return BrowserResult(
            success=True,
            action_type=plan.action_type,
            message="Opened YouTube Shorts.",
            spoken_response="Here are YouTube Shorts.",
            url=self.SHORTS_URL,
        )

    def _handle_search(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
    ) -> BrowserResult:
        """Handle opening YouTube home page or search results."""
        if not plan.query:
            success = engine.open_url(self.BASE_URL)
            return BrowserResult(
                success=success,
                action_type=plan.action_type,
                message="Opened YouTube.",
                spoken_response="Opening YouTube.",
                url=self.BASE_URL,
            )

        encoded = urllib.parse.quote_plus(plan.query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        success = engine.open_url(search_url)
        return BrowserResult(
            success=success,
            action_type=plan.action_type,
            message=f"Searched YouTube for '{plan.query}'.",
            spoken_response=f"Searching YouTube for {plan.query}.",
            url=search_url,
        )
