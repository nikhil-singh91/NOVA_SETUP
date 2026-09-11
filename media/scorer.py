"""Deterministic candidate scoring and ranking engine for media matching."""

from __future__ import annotations

import re
from typing import Any
from core.logger import get_logger
from media.models import MediaRequest, MediaType, VideoCandidate

logger = get_logger(__name__)


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

    @classmethod
    def score_candidate(cls, req: MediaRequest, candidate: VideoCandidate) -> float:
        """Calculate match score between request and candidate."""
        title_lower = candidate.title.lower()
        query_lower = req.query.lower()
        channel_lower = candidate.channel.lower()
        reasons: list[str] = []
        score = 0.0

        # Clean words from query
        req_words = [
            w
            for w in re.findall(r"\w+", query_lower)
            if len(w) > 1 and w not in ("song", "video", "official", "episode", "ep")
        ]
        if not req_words:
            req_words = [w for w in re.findall(r"\w+", query_lower) if len(w) > 1]

        # 1. Title Token Coverage
        if req_words:
            matched_words = [
                w for w in req_words if re.search(rf"\b{re.escape(w)}\b", title_lower)
            ]
            coverage = len(matched_words) / len(req_words)
            score += coverage * 0.40
            reasons.append(
                f"Token coverage: {coverage:.2f} ({len(matched_words)}/{len(req_words)})"
            )

        # Exact title substring bonus
        if query_lower in title_lower:
            score += 0.20
            reasons.append("Exact query substring match")

        # 2. Episode Number Matching (Strict episode markers, excluding sub-parts)
        if req.episode_number is not None:
            # Extract candidate episode numbers strictly following 'episode' or 'ep'
            ep_matches = re.findall(r"\b(?:episode|ep)\s*(\d+)\b", title_lower)
            cand_episodes = [int(n) for n in ep_matches]

            if req.episode_number in cand_episodes:
                score += 0.40
                reasons.append(f"Exact episode #{req.episode_number} matched")
            elif cand_episodes:
                # Different episode found -> severe penalty
                score -= 0.60
                reasons.append(
                    f"Episode mismatch (Found: {cand_episodes}, Requested: {req.episode_number})"
                )
        elif req.series_name:
            if req.series_name.lower() in title_lower:
                score += 0.15

        # 3. Modifier Alignment
        # A. Modifiers explicitly requested by the user
        for mod in req.modifiers:
            if mod in title_lower:
                score += 0.20
                reasons.append(f"Requested modifier '{mod}' found in candidate")
            else:
                score -= 0.10

        # B. Unwanted modifiers (if user did NOT request them)
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

        # C. Official / Verified Channel Bonus for Songs, Shows, Episodes
        if any(oc in channel_lower for oc in cls.OFFICIAL_MUSIC_CHANNELS) or any(
            "official" in b.lower() for b in candidate.badges
        ):
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

        # 5. Search Position Tie-Breaker (small weight up to 0.05)
        pos_bonus = max(0.0, 0.05 - (candidate.position * 0.005))
        score += pos_bonus

        # Clamp between 0.0 and 1.0
        final_score = max(0.0, min(1.0, score))
        candidate.score = round(final_score, 3)
        candidate.match_reasons = reasons
        return candidate.score
