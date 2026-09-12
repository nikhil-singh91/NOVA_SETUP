"""Comprehensive test suite for Real Music Intent, Short-term Music Context, and Context-Aware Non-Repeating YouTube Playback."""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch

from core.context import RecentInteractionContext, recent_interaction_context
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent
from media.models import (
    MediaRequest,
    MediaType,
    MusicIntent,
    MusicPreference,
    ShortTermMusicContext,
    VideoCandidate,
)
from media.parser import MediaRequestParser
from media.scorer import MediaMatchScorer
from media.service import MediaPlaybackService
from browser.models import ActionType, BrowserActionPlan, BrowserResult, Platform
from browser.sites.youtube import YouTubeSkill
from tests.test_browser_actions_v2 import MockBrowserEngineV2


class MockBrowserEngineForMusic(MockBrowserEngineV2):
    """Mock engine for testing YouTube playback verification."""

    def __init__(self) -> None:
        super().__init__()
        self.current_url = "https://www.youtube.com/watch?v=mock123"
        self.current_title = "Kesariya - Brahmāstra | Arijit Singh - YouTube"

    @property
    def browser_name(self) -> str:
        return "MockBrowserForMusic"

    def get_page_info(self) -> dict[str, str]:
        return {
            "url": self.current_url,
            "title": self.current_title,
        }


# ==============================================================================
# TEST 1: Intent Understanding & Natural Language Variations
# ==============================================================================

def test_music_intent_variations() -> None:
    engine = NaturalLanguageIntentEngine()
    ctx = RecentInteractionContext()

    # Generic music requests -> LISTEN_TO_MUSIC
    generic_phrases = [
        "Nova, I want to listen to some songs.",
        "I want to listen to some songs",
        "play me something",
        "play some music",
        "I feel like listening to music",
        "Can you put on some songs?",
        "Play something for me.",
        "Give me a song.",
        "Nova, let's listen to music.",
        "I want some music.",
        "Play a song.",
        "Put some music on.",
        "koi gaana sunao",
        "kuch baja do",
        "gaana bajao",
    ]
    for phrase in generic_phrases:
        action = engine.parse(phrase, context=ctx)
        assert action.intent == CanonicalIntent.LISTEN_TO_MUSIC, f"Failed for phrase: {phrase} (got {action.intent})"

    # Artist specific -> PLAY_ARTIST
    artist_action = engine.parse("Play some Arijit Singh songs", context=ctx)
    assert artist_action.intent == CanonicalIntent.PLAY_ARTIST
    assert "Arijit Singh" in artist_action.parameters.get("artist", "")

    # Genre / Mood specific -> PLAY_GENRE / PLAY_MOOD
    genre_action = engine.parse("Play romantic Hindi songs", context=ctx)
    assert genre_action.intent in (CanonicalIntent.PLAY_GENRE, CanonicalIntent.PLAY_MOOD)

    punjabi_action = engine.parse("Play Punjabi songs", context=ctx)
    assert punjabi_action.intent == CanonicalIntent.PLAY_GENRE

    # Specific song -> PLAY_SPECIFIC_SONG
    song_action = engine.parse("Play Tum Hi Ho", context=ctx)
    assert song_action.intent == CanonicalIntent.PLAY_SPECIFIC_SONG


# ==============================================================================
# TEST 2: Multi-Turn Follow-Up Resolution
# ==============================================================================

def test_music_followup_resolution() -> None:
    engine = NaturalLanguageIntentEngine()
    ctx = RecentInteractionContext()
    ctx.music_context.update_preference(artist="Arijit Singh")
    ctx.music_context.add_played_track(video_id="songA123", title="Tum Hi Ho - Arijit Singh")

    followups = [
        "Play another one.",
        "One more.",
        "Play another song",
        "Something else",
        "Play another",
        "ek aur sunao",
    ]
    for phrase in followups:
        action = engine.parse(phrase, context=ctx)
        assert action.intent == CanonicalIntent.LISTEN_TO_MUSIC, f"Failed for follow-up: {phrase}"
        assert action.parameters.get("action") == "next_song" or action.parameters.get("follow_up") is True


# ==============================================================================
# TEST 3: Short-Term Music Context & Preference Tracking
# ==============================================================================

def test_short_term_music_context_tracking() -> None:
    ctx = ShortTermMusicContext()
    assert ctx.active is False

    ctx.update_preference(artist="Arijit Singh", language="Hindi")
    assert ctx.active is True
    assert ctx.preference.artist == "Arijit Singh"
    assert ctx.preference.language == "Hindi"

    # Context query generation
    q1 = ctx.preference.to_search_query(variation_index=0)
    q2 = ctx.preference.to_search_query(variation_index=1)
    assert "Arijit Singh" in q1
    assert "Arijit Singh" in q2
    assert q1 != q2  # dynamic variations

    # Context override
    ctx.update_preference(language="Punjabi", override_all=True)
    assert ctx.preference.artist is None
    assert ctx.preference.language == "Punjabi"
    assert "Punjabi" in ctx.preference.to_search_query(0)


# ==============================================================================
# TEST 4: No-Repeat Guarantee & Candidate Ranking
# ==============================================================================

def test_no_repeat_candidate_selection() -> None:
    music_ctx = ShortTermMusicContext()
    service = MediaPlaybackService()

    candA = VideoCandidate(video_id="vidA", title="Song A - Arijit Singh", position=1)
    candB = VideoCandidate(video_id="vidB", title="Song B - Arijit Singh", position=2)
    candC = VideoCandidate(video_id="vidC", title="Song C - Arijit Singh", position=3)
    candD = VideoCandidate(video_id="vidD", title="Song D - Arijit Singh", position=4)
    candE = VideoCandidate(video_id="vidE", title="Song E - Arijit Singh", position=5)

    with patch.object(service.collector, "collect_candidates", return_value=[candA, candB, candC, candD, candE]):
        # Turn 1: Selects Song A
        sel1, _, _ = service.resolve_best_video("Play some Arijit Singh", music_context=music_ctx)
        assert sel1 is not None
        assert sel1.video_id == "vidA"
        music_ctx.add_played_track(video_id=sel1.video_id, title=sel1.title)

        # Turn 2: Follow-up request -> MUST NOT select Song A; selects Song B
        sel2, _, _ = service.resolve_best_video("another one", music_context=music_ctx, is_generic_listen=True)
        assert sel2 is not None
        assert sel2.video_id != "vidA"
        assert sel2.video_id == "vidB"
        music_ctx.add_played_track(video_id=sel2.video_id, title=sel2.title)

        # Turn 3: "One more" -> MUST NOT select Song A or B; selects Song C
        sel3, _, _ = service.resolve_best_video("one more", music_context=music_ctx, is_generic_listen=True)
        assert sel3 is not None
        assert sel3.video_id not in ("vidA", "vidB")
        assert sel3.video_id == "vidC"
        music_ctx.add_played_track(video_id=sel3.video_id, title=sel3.title)

        # Turn 4: "I want to listen to some songs" -> MUST NOT select A, B, or C; selects Song D
        sel4, _, _ = service.resolve_best_video("I want to listen to some songs", music_context=music_ctx, is_generic_listen=True)
        assert sel4 is not None
        assert sel4.video_id not in ("vidA", "vidB", "vidC")
        assert sel4.video_id == "vidD"


# ==============================================================================
# TEST 5: Duplicate Video ID & Title Match Detection
# ==============================================================================

def test_duplicate_detection() -> None:
    music_ctx = ShortTermMusicContext()
    music_ctx.add_played_track(video_id="xyz123", title="Kesariya - Brahmāstra | Pritam | Arijit Singh")

    # Same video ID is duplicate
    assert music_ctx.is_recently_played(video_id="xyz123") is True

    # Same song title is detected as duplicate
    assert music_ctx.is_recently_played(video_id="different_id", title="Kesariya - Brahmāstra | Pritam | Arijit Singh") is True

    # Completely different song is not a duplicate
    assert music_ctx.is_recently_played(video_id="abc999", title="Channa Mereya - Arijit Singh") is False


# ==============================================================================
# TEST 6: YouTube Skill Playback & Verification Flow
# ==============================================================================

def test_youtube_skill_playback_and_verification() -> None:
    skill = YouTubeSkill()
    engine = MockBrowserEngineForMusic()

    cand = VideoCandidate(video_id="mock123", title="Kesariya - Arijit Singh", position=1, score=0.90)
    with patch.object(skill.media_service, "resolve_best_video", return_value=(cand, MediaRequestParser.parse("Play Kesariya"), [cand])):
        plan = BrowserActionPlan(
            action_type=ActionType.PLAY_MEDIA,
            platform=Platform.YOUTUBE,
            query="Kesariya",
        )
        res = skill.execute(plan, engine, None)  # type: ignore
        assert res.success is True
        assert "Playing" in res.message
        assert res.metadata and res.metadata.get("video_id") == "mock123"


# ==============================================================================
# TEST 7: Playback Failure Truthful Reporting (No Fake Success)
# ==============================================================================

def test_youtube_skill_unverified_playback_reporting() -> None:
    skill = YouTubeSkill()
    engine = MockBrowserEngineForMusic()
    engine.current_url = "https://www.google.com"  # Wrong page / unverified
    engine.current_title = "Google Search"

    cand = VideoCandidate(video_id="targetVid", title="Target Song - Arijit Singh", position=1, score=0.90)
    with patch.object(skill.media_service, "resolve_best_video", return_value=(cand, MediaRequestParser.parse("Play Target Song"), [cand])):
        with patch.object(engine, "open_url", return_value=False):
            plan = BrowserActionPlan(
                action_type=ActionType.PLAY_MEDIA,
                platform=Platform.YOUTUBE,
                query="Target Song",
            )
            res = skill.execute(plan, engine, None)  # type: ignore
            assert res.success is False
            assert "could not verify" in res.message or "couldn't verify" in res.spoken_response


# ==============================================================================
# TEST 8: Dynamic Context Language Preference Switch
# ==============================================================================

def test_context_preference_switch() -> None:
    music_ctx = ShortTermMusicContext()
    service = MediaPlaybackService()

    # Step 1: User asks for Punjabi songs
    service.resolve_best_video("Play some Punjabi songs", music_context=music_ctx)
    assert music_ctx.preference.language == "Punjabi"
    assert "Punjabi" in music_ctx.preference.to_search_query(0)

    # Step 2: Generic request inherits Punjabi context
    with patch.object(service.collector, "collect_candidates", return_value=[VideoCandidate(video_id="punjabi1", title="Punjabi Hit Song", position=1)]):
        _, _, _ = service.resolve_best_video("I want to listen to some songs", music_context=music_ctx, is_generic_listen=True)
        assert music_ctx.preference.language == "Punjabi"

    # Step 3: User switches to English songs
    service.resolve_best_video("Actually play some English songs", music_context=music_ctx)
    assert music_ctx.preference.language == "English"
    assert "English" in music_ctx.preference.to_search_query(0)


# ==============================================================================
# TEST 9: Music Context Expiration & Task Switching Deactivation
# ==============================================================================

def test_music_context_expiration_and_task_switch() -> None:
    music_ctx = ShortTermMusicContext()
    music_ctx.update_preference(artist="Arijit Singh")
    music_ctx.last_action_time = time.time() - 700.0  # 700s ago (stale)

    assert music_ctx.is_fresh(max_age_seconds=600.0) is False

    # Deactivation on task switch
    music_ctx.update_preference(artist="Coldplay")
    assert music_ctx.active is True
    music_ctx.deactivate()
    assert music_ctx.active is False
    # History is retained for long-term avoiding repeats
    assert music_ctx.preference.artist == "Coldplay"


# ==============================================================================
# TEST 10: Provider Offline / Independence (Deterministic Execution)
# ==============================================================================

def test_deterministic_music_resolution_without_ai_provider() -> None:
    engine = NaturalLanguageIntentEngine()
    ctx = RecentInteractionContext()

    # Even with allow_ai_fallback=False or no LLM keys, intent & media match works 100% deterministically
    action = engine.parse("Play some Arijit Singh songs", context=ctx, allow_ai_fallback=False)
    assert action.intent == CanonicalIntent.PLAY_ARTIST

    followup_action = engine.parse("another one", context=ctx, allow_ai_fallback=False)
    assert followup_action.intent == CanonicalIntent.LISTEN_TO_MUSIC


# ==============================================================================
# TEST 11: ASR Error & Phonetic Tolerance
# ==============================================================================

def test_asr_phonetic_error_tolerance() -> None:
    service = MediaPlaybackService()
    cand = VideoCandidate(video_id="vidParvati", title="Parvati Song - Mahadev Bhajan", position=1)

    with patch.object(service.collector, "collect_candidates", return_value=[cand]):
        # "Parwati" phonetic variant
        sel, _, _ = service.resolve_best_video("play Parwati song")
        assert sel is not None
        assert sel.video_id == "vidParvati"
