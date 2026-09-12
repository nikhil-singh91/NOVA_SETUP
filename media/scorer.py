"""Deterministic candidate scoring and ranking engine for media matching."""

from __future__ import annotations

import re
from typing import Any
from core.logger import get_logger
from media.models import MediaRequest, MediaType, VideoCandidate, ShortTermMusicContext

logger = get_logger(__name__)


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if s1 == s2:
        return 0
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        cur_row = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            cur_row.append(min(cur_row[j] + 1, prev_row[j + 1] + 1, prev_row[j] + cost))
        prev_row = cur_row
    return prev_row[-1]


def _token_similarity(w1: str, w2: str) -> float:
    """Compute normalized token similarity (0.0 to 1.0) handling ASR phonetic variations."""
    w1, w2 = w1.lower().strip(), w2.lower().strip()
    if not w1 or not w2:
        return 0.0
    if w1 == w2:
        return 1.0

    # Common Indic / ASR transliteration tolerances (e.g. w/v, sh/s, ph/f, ee/i, oo/u, kh/k)
    phonetic_w1 = (
        w1.replace("ph", "f")
        .replace("w", "v")
        .replace("sh", "s")
        .replace("ee", "i")
        .replace("oo", "u")
        .replace("g", "k")
        .replace("kh", "k")
    )
    phonetic_w2 = (
        w2.replace("ph", "f")
        .replace("w", "v")
        .replace("sh", "s")
        .replace("ee", "i")
        .replace("oo", "u")
        .replace("g", "k")
        .replace("kh", "k")
    )
    if phonetic_w1 == phonetic_w2:
        return 1.0

    # Substring containment
    if len(w1) > 3 and w1 in w2:
        return 0.95
    if len(w2) > 3 and w2 in w1:
        return 0.95

    dist = _levenshtein_distance(w1, w2)
    max_len = max(len(w1), len(w2))
    sim = max(0.0, 1.0 - (dist / max_len))

    return sim


class MediaMatchScorer:
    """Computes a deterministic match score (0.0 to 1.0) between a user MediaRequest and a VideoCandidate."""

    UNWANTED_SONG_MODIFIERS = [
        "remix",
        "slowed",
        "reverb",
        "8d",
        "bass boosted",
        "mashup",
        "parody",
        "reaction",
        "cover",
        "karaoke",
        "instrumental",
    ]

    OFFICIAL_MUSIC_CHANNELS = [
        "vevo",
        "t-series",
        "sony music",
        "zee music",
        "tips",
        "yrf",
        "speed records",
        "saregama",
        "warner music",
        "universal music",
        "jiohotstar",
        "voot",
        "sonic gang",
    ]

    UNWANTED_TUTORIAL_PHRASES = [
        "search history",
        "delete kaise kare",
        "how to delete",
        "how to fix",
        "settings",
        "how to clear",
        "tutorial",
        "error fix",
        "problem solve",
    ]

    @classmethod
    def score_candidate(
        cls,
        req: MediaRequest,
        candidate: VideoCandidate,
        music_context: ShortTermMusicContext | None = None,
    ) -> float:
        """Calculate match score between request and candidate."""
        title_lower = candidate.title.lower()
        query_lower = req.query.lower().strip()
        channel_lower = candidate.channel.lower()
        reasons: list[str] = []
        score = 0.0

        # Penalize recently played tracks to guarantee no repeats
        if music_context and music_context.is_recently_played(candidate.video_id, candidate.title):
            score -= 0.70
            reasons.append("Penalized: Recently played in this session (no-repeat policy)")

        # Reject non-media queries
        if not query_lower or query_lower in ("youtube search", "youtube shorts", "shorts", "search", "youtube"):
            candidate.score = 0.0
            candidate.match_reasons = ["Rejected non-media query"]
            return 0.0

        # Penalize troubleshooting/tutorial content if user did not ask for tutorials
        if req.media_type in (MediaType.SONG, MediaType.SHORT) and any(p in title_lower for p in cls.UNWANTED_TUTORIAL_PHRASES):
            if not any(p in query_lower for p in cls.UNWANTED_TUTORIAL_PHRASES):
                candidate.score = 0.0
                candidate.match_reasons = ["Penalized: Unrelated tutorial/settings video"]
                return 0.0

        # Clean words from query
        req_words = [
            w
            for w in re.findall(r"\w+", query_lower)
            if len(w) > 1 and w not in ("song", "songs", "video", "videos", "music", "official", "episode", "ep", "best", "top", "hits", "popular", "latest", "trending", "mix", "playlist")
        ]
        if not req_words:
            req_words = [w for w in re.findall(r"\w+", query_lower) if len(w) > 1]

        # 1. Title Token Coverage with Generic Levenshtein & Phonetic Tolerance
        title_words = re.findall(r"\w+", title_lower)
        coverage = 0.0
        if req_words:
            token_scores = []
            for rw in req_words:
                best_match = 0.0
                for tw in title_words:
                    sim = _token_similarity(rw, tw)
                    if sim > best_match:
                        best_match = sim
                token_scores.append(best_match if best_match >= 0.70 else 0.0)

            coverage = sum(token_scores) / len(req_words)
            score += coverage * 0.45
            reasons.append(f"Token similarity coverage: {coverage:.2f} ({token_scores})")

        # Exact title substring or high phonetic match bonus
        if query_lower in title_lower:
            score += 0.20
            reasons.append("Exact query substring match")
        elif any(rw in title_lower for rw in req_words if len(rw) > 3):
            score += 0.10
        elif req_words and coverage >= 0.80:
            score += 0.15
            reasons.append("Phonetic/token match bonus")

        # 2. Episode Number Matching
        if req.episode_number is not None:
            ep_matches = re.findall(r"\b(?:episode|ep)\s*(\d+)\b", title_lower)
            cand_episodes = [int(n) for n in ep_matches]

            if req.episode_number in cand_episodes:
                score += 0.40
                reasons.append(f"Exact episode #{req.episode_number} matched")
            elif cand_episodes:
                score -= 0.60
                reasons.append(
                    f"Episode mismatch (Found: {cand_episodes}, Requested: {req.episode_number})"
                )
        elif req.series_name:
            if req.series_name.lower() in title_lower:
                score += 0.15

        # 3. Modifier Alignment
        for mod in req.modifiers:
            if mod in title_lower:
                score += 0.20
                reasons.append(f"Requested modifier '{mod}' found in candidate")
            else:
                score -= 0.10

        if not any(
            m in req.modifiers
            for m in ["remix", "slowed", "reverb", "cover", "mashup", "parody", "reaction"]
        ):
            found_unwanted = [
                u
                for u in cls.UNWANTED_SONG_MODIFIERS
                if re.search(rf"\b{re.escape(u)}\b", title_lower)
            ]
            if found_unwanted:
                score -= 0.35
                reasons.append(f"Penalized for unrequested modifiers: {found_unwanted}")

        # Official / Verified Channel Bonus
        if any(oc in channel_lower for oc in cls.OFFICIAL_MUSIC_CHANNELS) or any(
            "official" in b.lower() for b in candidate.badges
        ) or any(oc in title_lower for oc in cls.OFFICIAL_MUSIC_CHANNELS):
            score += 0.15
            reasons.append("Official/verified publisher channel bonus")

        # 4. Content Type & Duration Penalties
        if req.media_type != MediaType.SHORT:
            if candidate.is_short or (
                candidate.duration_seconds > 0 and candidate.duration_seconds <= 60
            ):
                score -= 0.60
                reasons.append("Penalized: Video is a Short when normal video was requested")
        else:
            if candidate.is_short:
                score += 0.30
                reasons.append("Short duration bonus")

        # 5. Search Position Tie-Breaker
        pos_bonus = max(0.0, 0.05 - (candidate.position * 0.005))
        score += pos_bonus

        final_score = max(0.0, min(1.0, score))
        candidate.score = round(final_score, 3)
        candidate.match_reasons = reasons
        return candidate.score
