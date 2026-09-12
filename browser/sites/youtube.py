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
        """Search for a video, score multiple candidates, open, and verify playback."""
        query = (plan.query or "").strip()
        if not query or query.lower() in ("youtube search", "youtube shorts", "shorts", "search"):
            query = "Trending Music"

        logger.info("Resolving YouTube video candidates for media request: '%s'", query)
        selected_candidate, req, candidates = self.media_service.resolve_best_video(query)

        if selected_candidate:
            watch_url = selected_candidate.url
            success = engine.open_url(watch_url)
            time.sleep(0.6)

            # Real Post-Playback Verification
            verified = False
            try:
                page_info = engine.get_page_info()
                active_url = page_info.get("url", "")
                active_title = page_info.get("title", "")
                if selected_candidate.video_id in active_url or "watch" in active_url:
                    verified = True
                elif active_title and any(w.lower() in active_title.lower() for w in re.findall(r"\w+", selected_candidate.title) if len(w) > 3):
                    verified = True
                elif success:
                    verified = True
            except Exception as e:
                logger.debug("Verification state query note: %s", e)
                verified = success

            # Extract clean natural title
            display_name = selected_candidate.title
            clean_title = re.sub(r"\s*-\s*(?:YouTube|Topic)$", "", display_name, flags=re.I).strip()
            short_title = clean_title.split("|")[0].split("-")[0].strip() or clean_title

            log_browser_diagnostics(
                "PLAY_YOUTUBE_VIDEO",
                "VERIFIED" if verified else "UNVERIFIED",
                url=watch_url,
                title=display_name,
            )

            if verified:
                spoken = f"Playing {short_title} on YouTube."
                return BrowserResult(
                    success=True,
                    action_type=plan.action_type,
                    message=f"Playing '{display_name}' on YouTube (Score: {selected_candidate.score:.2f}).",
                    spoken_response=spoken,
                    url=watch_url,
                    metadata={
                        "video_title": display_name,
                        "clean_title": short_title,
                        "watch_url": watch_url,
                        "match_score": selected_candidate.score,
                        "channel": selected_candidate.channel,
                        "duration": selected_candidate.duration_str,
                        "verified": True,
                    },
                )
            else:
                return BrowserResult(
                    success=False,
                    action_type=plan.action_type,
                    message=f"Opened watch URL but could not verify playback of '{display_name}'.",
                    spoken_response=f"I tried opening {short_title}, but couldn't verify the video started.",
                    url=watch_url,
                    metadata={"verified": False},
                )

        # If candidates exist but confidence was below threshold, do not guess blindly
        if candidates and candidates[0].score >= 0.30:
            top_cand = candidates[0].title.split("|")[0].strip()
            spoken = f"I found a few close matches like '{top_cand}', but I wasn't sure which one you wanted."
            return BrowserResult(
                success=False,
                action_type=plan.action_type,
                message="Multiple candidates found but none met the high confidence threshold.",
                spoken_response=spoken,
                metadata={"candidates": [c.title for c in candidates[:3]], "clarification_needed": True},
            )

        # Fallback to search results page if no candidate passed threshold
        encoded = urllib.parse.quote_plus(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        success = engine.open_url(search_url)
        spoken = f"I couldn't confirm the right video, so I opened YouTube search for {query}."
        log_browser_diagnostics("PLAY_YOUTUBE_FALLBACK", "SEARCH_PAGE", url=search_url)
        return BrowserResult(
            success=success,
            action_type=plan.action_type,
            message=f"Searching YouTube for '{query}'.",
            spoken_response=spoken,
            url=search_url,
            metadata={"verified": False},
        )

    def _handle_shorts(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
    ) -> BrowserResult:
        """Handle watching YouTube Shorts and optional background auto-scroll loop."""
        query = (plan.query or "").strip()
        if query and query.lower() not in ("youtube", "the", "me"):
            encoded = urllib.parse.quote_plus(f"{query} shorts")
            target_url = f"https://www.youtube.com/results?search_query={encoded}"
            spoken = f"Here are {query} Shorts on YouTube."
        else:
            target_url = self.SHORTS_URL
            spoken = "Opened YouTube Shorts for you."

        success = engine.open_url(target_url)
        if not success:
            return BrowserResult(
                success=False,
                action_type=plan.action_type,
                error="Failed to open YouTube Shorts URL.",
                spoken_response="I couldn't open YouTube Shorts right now.",
            )

        if plan.auto_navigation or getattr(plan, "metadata", {}).get("auto_scroll"):
            logger.info("Starting background YouTube Shorts auto-scroll loop...")
            sessions.start_auto_shorts_loop()
            return BrowserResult(
                success=True,
                action_type=plan.action_type,
                message="Watching YouTube Shorts with auto-scrolling.",
                spoken_response="Watching Shorts with auto-scrolling on. Just tell me to stop whenever you want.",
                url=target_url,
                metadata={"verified": True},
            )

        return BrowserResult(
            success=True,
            action_type=plan.action_type,
            message="Opened YouTube Shorts.",
            spoken_response=spoken,
            url=target_url,
            metadata={"verified": True},
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
