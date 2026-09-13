"""Comprehensive unit and integration tests for NOVA Media Matching & Playback Reliability."""

from __future__ import annotations

from media.models import MediaType, VideoCandidate
from media.parser import MediaRequestParser
from media.refiner import SearchQueryRefiner
from media.scorer import MediaMatchScorer
from media.service import MediaPlaybackService

# ==============================================================================
# TEST 1: Structured Media Request Parsing
# ==============================================================================

def test_media_request_parsing_songs() -> None:
    req1 = MediaRequestParser.parse("Play Kesariya")
    assert req1.query.lower() == "kesariya"
    assert req1.media_type in (MediaType.SONG, MediaType.GENERAL_VIDEO)
    assert req1.modifiers == []

    req2 = MediaRequestParser.parse("Play Kesariya remix")
    assert "kesariya" in req2.query.lower()
    assert req2.media_type == MediaType.SONG
    assert "remix" in req2.modifiers

    req3 = MediaRequestParser.parse("Play song Mere Liye")
    assert "mere liye" in req3.query.lower()
    assert req3.media_type == MediaType.SONG


def test_media_request_parsing_episodes() -> None:
    req1 = MediaRequestParser.parse("Play Motu Patlu episode 1")
    assert req1.series_name == "Motu Patlu"
    assert req1.episode_number == 1
    assert req1.media_type == MediaType.EPISODE

    req2 = MediaRequestParser.parse("Play Motu Patlu episode 5")
    assert req2.series_name == "Motu Patlu"
    assert req2.episode_number == 5
    assert req2.media_type == MediaType.EPISODE


def test_media_request_parsing_tutorials() -> None:
    req1 = MediaRequestParser.parse("Play a Python tutorial")
    assert "python" in req1.query.lower()
    assert req1.media_type == MediaType.TUTORIAL

    req2 = MediaRequestParser.parse("Play DSA binary search tutorial")
    assert "binary search" in req2.query.lower()
    assert req2.media_type == MediaType.TUTORIAL


# ==============================================================================
# TEST 2: Song Matching & Modifier Scoring
# ==============================================================================

def test_kesariya_official_vs_remix_scoring() -> None:
    req = MediaRequestParser.parse("Play Kesariya")

    official_cand = VideoCandidate(
        video_id="BddP6PYo2gs",
        title="Kesariya - Brahmāstra | Ranbir Kapoor, Alia Bhatt | Pritam | Arijit Singh",
        channel="Sony Music India",
        duration_str="2:53",
        duration_seconds=173,
        position=1,
    )

    remix_cand = VideoCandidate(
        video_id="K3B8-klo5xc",
        title="Kesariya (Dance Mix) - Brahmāstra | Pritam | Shashwat | Antara",
        channel="Sony Music India",
        duration_str="3:18",
        duration_seconds=198,
        position=2,
    )

    short_cand = VideoCandidate(
        video_id="xyz12345",
        title="Kesariya Song Status #shorts #music",
        channel="Status Channel",
        duration_str="0:30",
        duration_seconds=30,
        is_short=True,
        position=3,
    )

    score_official = MediaMatchScorer.score_candidate(req, official_cand)
    score_remix = MediaMatchScorer.score_candidate(req, remix_cand)
    score_short = MediaMatchScorer.score_candidate(req, short_cand)

    assert score_official > score_remix
    assert score_official > score_short
    assert score_official >= 0.70


def test_kesariya_remix_explicit_preference() -> None:
    req = MediaRequestParser.parse("Play Kesariya remix")

    official_cand = VideoCandidate(
        video_id="BddP6PYo2gs",
        title="Kesariya - Brahmāstra | Ranbir Kapoor, Alia Bhatt | Pritam | Arijit Singh",
        channel="Sony Music India",
        duration_str="2:53",
        duration_seconds=173,
        position=1,
    )

    remix_cand = VideoCandidate(
        video_id="WU_m_JqwJaU",
        title="Kesariya Remix - Dj Aaditya (Clean Mix)",
        channel="AADITYA",
        duration_str="3:29",
        duration_seconds=209,
        position=2,
    )

    score_official = MediaMatchScorer.score_candidate(req, official_cand)
    score_remix = MediaMatchScorer.score_candidate(req, remix_cand)

    assert score_remix > score_official
    assert score_remix >= 0.70


# ==============================================================================
# TEST 3: Show / Episode Number Matching & Penalization
# ==============================================================================

def test_motu_patlu_episode_1_matching() -> None:
    req = MediaRequestParser.parse("Play Motu Patlu episode 1")

    ep1_cand = VideoCandidate(
        video_id="1oR10vUbHhY",
        title="Motu Patlu | Season 1 | Jon Banega Don | Episode 1 Part 1 | Voot Kids",
        channel="JioHotstar Kids",
        duration_str="11:28",
        duration_seconds=688,
        position=1,
    )

    ep34_cand = VideoCandidate(
        video_id="QEPJZ7VXwfA",
        title="Motu Patlu | The Game | Episode 34 Part 1 | Download Voot Kids App",
        channel="JioHotstar Kids",
        duration_str="11:34",
        duration_seconds=694,
        position=2,
    )

    score_ep1 = MediaMatchScorer.score_candidate(req, ep1_cand)
    score_ep34 = MediaMatchScorer.score_candidate(req, ep34_cand)

    assert score_ep1 > score_ep34
    assert score_ep1 >= 0.80
    assert score_ep34 < 0.40  # Heavily penalized for wrong episode


def test_motu_patlu_episode_5_matching() -> None:
    req = MediaRequestParser.parse("Play Motu Patlu episode 5")

    ep5_cand = VideoCandidate(
        video_id="0r3AoyrJ1-w",
        title="Motu Patlu | Diamond Robbery | Episode 5 Part 2 | Voot Kids",
        channel="JioHotstar Kids",
        duration_str="12:20",
        duration_seconds=740,
        position=1,
    )

    ep1_cand = VideoCandidate(
        video_id="1oR10vUbHhY",
        title="Motu Patlu | Season 1 | Jon Banega Don | Episode 1 Part 1 | Voot Kids",
        channel="JioHotstar Kids",
        duration_str="11:28",
        duration_seconds=688,
        position=2,
    )

    score_ep5 = MediaMatchScorer.score_candidate(req, ep5_cand)
    score_ep1 = MediaMatchScorer.score_candidate(req, ep1_cand)

    assert score_ep5 > score_ep1
    assert score_ep5 >= 0.80


# ==============================================================================
# TEST 4: Search Query Refinement
# ==============================================================================

def test_query_refinements() -> None:
    req_song = MediaRequestParser.parse("Play Kesariya")
    ref_song = SearchQueryRefiner.get_refined_queries(req_song)
    assert any("official song" in q for q in ref_song)

    req_ep = MediaRequestParser.parse("Play Motu Patlu episode 1")
    ref_ep = SearchQueryRefiner.get_refined_queries(req_ep)
    assert any("episode 1 full episode" in q for q in ref_ep)


# ==============================================================================
# TEST 5: User Rejection & Next Candidate Selection
# ==============================================================================

def test_user_rejection_flow() -> None:
    service = MediaPlaybackService()

    # Initial query
    best1, req, candidates = service.resolve_best_video("Play Kesariya")
    assert best1 is not None

    # User rejects current selection ("No, not this one")
    best2 = service.handle_user_rejection()
    assert best2 is not None
    assert best2.video_id != best1.video_id
    assert best1.video_id in service.rejected_video_ids
