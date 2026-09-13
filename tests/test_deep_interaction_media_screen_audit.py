"""Comprehensive verification test suite for NOVA root-cause audit.

Covers:
- Media request parsing (English, Hindi, Hinglish with various verbs)
- Generic ASR phonetic / Levenshtein tolerance without hardcoded songs
- YouTube Shorts intent distinguishing destination from query
- Screen questions invoking Eyes perception without conversational fallback
- Response Orchestrator output formatting (Dashboard vs TTS, English vs Hinglish, no Boss spam)
- Zero hardcoded song aliases in production code
"""

from __future__ import annotations

from datetime import UTC
from unittest.mock import MagicMock

import pytest
from browser.models import ActionType, BrowserActionPlan, BrowserResult, Platform
from browser.sites.youtube import YouTubeSkill
from core.eyes.capture import DisplayMetrics
from core.eyes.state import ScreenState
from intent.engine import NaturalLanguageIntentEngine
from intent.matcher import LinguisticIntentMatcher
from intent.models import CanonicalIntent, StructuredAction
from media.models import MediaRequest, MediaType, VideoCandidate
from media.parser import MediaRequestParser
from media.scorer import MediaMatchScorer
from personality.response_orchestrator import ResponseOrchestrator


class TestIntentClassificationPrecedence:
    """Test that action, media, and screen requests have priority over conversation."""

    def setup_method(self) -> None:
        self.engine = NaturalLanguageIntentEngine()
        self.matcher = LinguisticIntentMatcher()

    @pytest.mark.parametrize(
        "phrase, expected_intent, expected_query",
        [
            ("Nova kalang songs bhajao", CanonicalIntent.PLAY_MEDIA, "kalang"),
            ("kalang songs bhajao", CanonicalIntent.PLAY_MEDIA, "kalang"),
            ("kalank wala gaana chala do", CanonicalIntent.PLAY_MEDIA, "kalank"),
            ("Arijit Singh ke gaane bajao", CanonicalIntent.PLAY_MEDIA, "arijit singh"),
            ("play an arijit singh song", CanonicalIntent.PLAY_MEDIA, "arijit singh"),
            ("YouTube pe Kesariya chala do", CanonicalIntent.PLAY_MEDIA, "kesariya"),
            ("Play Kesariya on YouTube", CanonicalIntent.PLAY_MEDIA, "kesariya"),
            ("Chala do Tum Hi Ho", CanonicalIntent.PLAY_MEDIA, "tum hi ho"),
            ("gaana sunao Believer", CanonicalIntent.PLAY_MEDIA, "believer"),
        ],
    )
    def test_media_playback_intents(self, phrase: str, expected_intent: CanonicalIntent, expected_query: str) -> None:
        action = self.engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent in (
            CanonicalIntent.PLAY_MEDIA,
            CanonicalIntent.PLAY_SPECIFIC_SONG,
            CanonicalIntent.PLAY_ARTIST,
            CanonicalIntent.PLAY_GENRE,
            CanonicalIntent.PLAY_MOOD,
            CanonicalIntent.LISTEN_TO_MUSIC,
        ), f"{phrase}: expected media intent, got {action.intent}"
        assert action.confidence >= 0.85
        q = (action.parameters.get("query", "") or action.parameters.get("artist", "")).lower()
        assert expected_query.lower() in q

    @pytest.mark.parametrize(
        "phrase, expected_query",
        [
            ("play youtube shorts", ""),
            ("open shorts", ""),
            ("show me shorts", ""),
            ("open youtube shorts", ""),
            ("shorts kholo", ""),
            ("shorts dikhao", ""),
            ("show me coding shorts", "coding"),
            ("cricket shorts dikhao", "cricket"),
            ("play python shorts", "python"),
        ],
    )
    def test_youtube_shorts_intents(self, phrase: str, expected_query: str) -> None:
        action = self.engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.WATCH_SHORTS, f"{phrase}: expected WATCH_SHORTS, got {action.intent}"
        q = action.parameters.get("query", "").lower()
        assert q == expected_query.lower()

    @pytest.mark.parametrize(
        "phrase",
        [
            "Nova, what are you seeing on my screen?",
            "what are you seeing on my screen?",
            "what are you seeing?",
            "what do you see on my screen",
            "what do you see",
            "what can you see",
            "what is on my screen",
            "what's on my screen",
            "read this",
            "summarize this page",
            "what is written here",
            "screen pe kya hai",
            "screen pe kya dikh raha hai",
            "screen dekho",
        ],
    )
    def test_screen_awareness_intents(self, phrase: str) -> None:
        action = self.engine.parse(phrase, allow_ai_fallback=False)
        assert action.intent == CanonicalIntent.WHAT_AM_I_LOOKING_AT, f"{phrase}: expected WHAT_AM_I_LOOKING_AT, got {action.intent}"
        assert action.confidence >= 0.85


class TestGenericMediaResolutionAndScoring:
    """Verify that ASR mishearings are resolved generically without hardcoded song aliases."""

    def test_asr_phonetic_tolerance_kalang_to_kalank(self) -> None:
        req = MediaRequestParser.parse("Nova kalang songs bhajao")
        assert req.query == "kalang"

        candidate = VideoCandidate(
            video_id="vid_kalank_123",
            title="Kalank Title Track - Lyrical | Alia Bhatt , Varun Dhawan | Arijit Singh | Zee Music Company",
            channel="Zee Music Company",
            duration_str="5:14",
            duration_seconds=314,
            url="https://www.youtube.com/watch?v=vid_kalank_123",
            position=1,
            is_short=False,
        )

        score = MediaMatchScorer.score_candidate(req, candidate)
        assert score >= 0.50, f"Expected score >= 0.50 for phonetic match, got {score}"

    def test_rejection_of_unrelated_search_results(self) -> None:
        req = MediaRequest(
            original_text="play youtube search",
            query="youtube search",
            media_type=MediaType.SONG,
        )
        candidate = VideoCandidate(
            video_id="vid_tutorial_999",
            title="YouTube Search History Delete Kaise Kare | How To Clear Search History",
            channel="Tech Guru",
            duration_str="3:20",
            duration_seconds=200,
            url="https://www.youtube.com/watch?v=vid_tutorial_999",
            position=1,
            is_short=False,
        )
        score = MediaMatchScorer.score_candidate(req, candidate)
        assert score == 0.0, f"Expected 0.0 for unrelated tutorial, got {score}"

    def test_no_hardcoded_songs_in_media_parser(self) -> None:
        with open("media/parser.py") as f:
            code = f.read().lower()
        for forbidden in ["kalank", "kaland", "kesariya", "mere liye", "believer"]:
            assert forbidden not in code, f"Forbidden hardcoded song '{forbidden}' found in media/parser.py"


class TestYouTubePlaybackVerification:
    """Test real verification in YouTubeSkill."""

    def test_verified_playback_generates_verified_result(self) -> None:
        skill = YouTubeSkill()
        engine_mock = MagicMock()
        engine_mock.open_url.return_value = True
        engine_mock.get_page_info.return_value = {
            "url": "https://www.youtube.com/watch?v=5PoptCZnS6A",
            "title": "Kalank Title Track - Arijit Singh - YouTube",
        }

        candidate = VideoCandidate(
            video_id="5PoptCZnS6A",
            title="Kalank Title Track - Arijit Singh | Alia Bhatt",
            channel="Zee Music Company",
            duration_str="5:14",
            duration_seconds=314,
            url="https://www.youtube.com/watch?v=5PoptCZnS6A",
            score=0.85,
        )
        skill.media_service.resolve_best_video = MagicMock(return_value=(candidate, None, [candidate]))

        plan = BrowserActionPlan(
            action_type=ActionType.PLAY_MEDIA,
            platform=Platform.YOUTUBE,
            query="kalank",
        )
        result = skill.execute(plan, engine_mock, MagicMock())

        assert result.success is True
        assert result.metadata.get("verified") is True
        assert "Kalank Title Track" in result.metadata.get("video_title", "")
        assert "Kalank" in result.spoken_response

    def test_shorts_navigation_distinct_from_media_search(self) -> None:
        skill = YouTubeSkill()
        engine_mock = MagicMock()
        engine_mock.open_url.return_value = True
        engine_mock.get_page_info.return_value = {"url": "https://www.youtube.com/shorts", "title": "YouTube Shorts"}

        plan = BrowserActionPlan(
            action_type=ActionType.WATCH_SHORTS,
            platform=Platform.YOUTUBE,
            query="",
        )
        result = skill.execute(plan, engine_mock, MagicMock())
        assert result.success is True
        engine_mock.open_url.assert_called_with("https://www.youtube.com/shorts")
        assert "shorts" in result.url.lower()


class TestScreenPerceptionWithNOVAEyes:
    """Test that screen questions produce human-friendly, context-aware descriptions."""

    def test_natural_screen_description_youtube(self) -> None:
        from datetime import datetime
        state = ScreenState(
            timestamp=datetime.now(UTC),
            active_application="Google Chrome",
            active_window="Kalank Title Track - YouTube",
            metrics=DisplayMetrics.get_primary_metrics(),
            visual_hash="hash123",
            visible_texts=["Kalank Title Track - Arijit Singh", "Subscribe", "34M views"],
        )
        desc_en = state.get_natural_screen_description(is_hinglish=False)
        assert "YouTube" in desc_en
        assert "Kalank Title Track" in desc_en
        assert "UI elements" not in desc_en

        desc_hi = state.get_natural_screen_description(is_hinglish=True)
        assert "YouTube" in desc_hi
        assert "dekh rahe ho" in desc_hi

    def test_natural_screen_description_vscode(self) -> None:
        from datetime import datetime
        state = ScreenState(
            timestamp=datetime.now(UTC),
            active_application="Visual Studio Code",
            active_window="NOVA_SETUP — main.py",
            metrics=DisplayMetrics.get_primary_metrics(),
            visual_hash="hash456",
            visible_texts=["def main():", "import os"],
        )
        desc_en = state.get_natural_screen_description(is_hinglish=False)
        assert "Visual Studio Code" in desc_en
        assert "NOVA_SETUP" in desc_en


class TestResponseOrchestrator:
    """Test friend-like conversation, English/Hinglish adaptation, and TTS safety."""

    def test_media_playback_response_english(self) -> None:
        action = StructuredAction(
            intent=CanonicalIntent.PLAY_MEDIA,
            confidence=0.98,
            parameters={"query": "kalank"},
            raw_input="play kalank",
            normalized_input="play kalank",
        )
        result = BrowserResult(
            success=True,
            action_type=ActionType.PLAY_MEDIA,
            message="Playing Kalank",
            spoken_response="Playing Kalank",
            metadata={"clean_title": "Kalank", "verified": True},
        )
        orch = ResponseOrchestrator.format_action_response(action, result, "play kalank")
        assert orch.success is True
        assert "playing Kalank now" in orch.display_text
        assert "🎵" in orch.display_text
        assert "🎵" not in orch.spoken_text

    def test_media_playback_response_hinglish(self) -> None:
        action = StructuredAction(
            intent=CanonicalIntent.PLAY_MEDIA,
            confidence=0.98,
            parameters={"query": "kalang"},
            raw_input="kalang songs bhajao",
            normalized_input="kalang songs bhajao",
        )
        result = BrowserResult(
            success=True,
            action_type=ActionType.PLAY_MEDIA,
            message="Playing Kalank",
            spoken_response="Playing Kalank",
            metadata={"clean_title": "Kalank", "verified": True},
        )
        orch = ResponseOrchestrator.format_action_response(action, result, "kalang songs bhajao")
        assert orch.success is True
        assert "play kar raha hoon" in orch.display_text or "mil gaya" in orch.display_text

    def test_media_verification_failure_honest_response(self) -> None:
        action = StructuredAction(
            intent=CanonicalIntent.PLAY_MEDIA,
            confidence=0.98,
            parameters={"query": "kalank"},
            raw_input="play kalank",
            normalized_input="play kalank",
        )
        result = BrowserResult(
            success=False,
            action_type=ActionType.PLAY_MEDIA,
            message="Playback unverified",
            spoken_response="Playback unverified",
            metadata={"clean_title": "Kalank", "verified": False},
        )
        orch = ResponseOrchestrator.format_action_response(action, result, "play kalank")
        assert orch.success is False
        assert "couldn't verify" in orch.display_text

    def test_banned_support_filler_and_no_boss_spam(self) -> None:
        raw_model = "Boss, how may I assist you today? Boss, certainly Boss, here is the answer."
        clean = ResponseOrchestrator.clean_for_display(raw_model)
        assert "how may i assist you" not in clean.lower()
        assert "certainly" not in clean.lower()
        assert clean.count("Boss") <= 1
