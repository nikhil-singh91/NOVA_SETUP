"""Central media playback service coordinating parsing, collection, scoring, and playback verification."""

from __future__ import annotations

import os
from typing import Any

from config.settings import settings
from core.logger import get_logger
from media.collector import YouTubeCandidateCollector
from media.models import MediaRequest, MediaType, VideoCandidate
from media.parser import MediaRequestParser
from media.refiner import SearchQueryRefiner
from media.scorer import MediaMatchScorer

logger = get_logger(__name__)


def log_media_diagnostics(
    req: MediaRequest,
    candidates: list[VideoCandidate],
    selected: VideoCandidate | None,
    search_query: str,
) -> None:
    """Log structured media matching diagnostics when debug mode is enabled."""
    is_debug = bool(
        getattr(settings, "nova_media_debug", False)
        or os.getenv("NOVA_MEDIA_DEBUG", "").lower() in ("true", "1")
    )
    if not is_debug:
        return

    print("\n========================================")
    print("🎬 [MEDIA MATCHING DIAGNOSTICS]")
    print(f"RAW COMMAND:     \"{req.original_text}\"")
    print("INTENT:          PLAY_MEDIA")
    print(f"MEDIA TYPE:      {req.media_type.value.upper()}")
    print(f"ORIGINAL QUERY:  \"{req.query}\"")
    print(f"SEARCH QUERY:    \"{search_query}\"")
    if req.episode_number:
        print(f"EPISODE NUMBER:  {req.episode_number}")
    if req.modifiers:
        print(f"MODIFIERS:       {req.modifiers}")
    print("CANDIDATES:")
    for idx, c in enumerate(candidates[:5]):
        sel_marker = "  --> [SELECTED]" if selected and c.video_id == selected.video_id else ""
        print(f"  {idx+1}. [{c.score:.2f}] {c.title} ({c.channel}) [Dur: {c.duration_str}]{sel_marker}")

    if selected:
        print(f"SELECTED:        Candidate [{selected.score:.2f}] \"{selected.title}\"")
        print(f"WATCH URL:       {selected.url}")
        print("VERIFICATION:    PASS")
    else:
        print("SELECTED:        NONE (No candidate met confidence threshold)")
        print("VERIFICATION:    REJECTED")
    print("========================================\n")


class MediaPlaybackService:
    """Manages structured media requests, candidate retrieval, scoring, refinement, and user correction."""

    def __init__(self) -> None:
        self.collector = YouTubeCandidateCollector()
        self.last_request: MediaRequest | None = None
        self.last_candidate: VideoCandidate | None = None
        self.rejected_video_ids: set[str] = set()

    def handle_user_rejection(self) -> VideoCandidate | None:
        """Handle user feedback ('No, not this one') by rejecting current candidate and picking next best."""
        if not self.last_request or not self.last_candidate:
            return None

        self.rejected_video_ids.add(self.last_candidate.video_id)
        logger.info("User rejected video %s ('%s'). Selecting next best candidate...", self.last_candidate.video_id, self.last_candidate.title)
        best, _, _ = self.resolve_best_video(self.last_request.original_text, rejected_ids=self.rejected_video_ids)
        return best

    def resolve_best_video(
        self,
        query_or_text: str,
        rejected_ids: set[str] | None = None,
    ) -> tuple[VideoCandidate | None, MediaRequest, list[VideoCandidate]]:
        """Resolve the best matching video candidate for a media query."""
        req: MediaRequest = MediaRequestParser.parse(query_or_text)
        self.last_request = req
        active_rejected = rejected_ids or set()

        # 1. First search pass
        search_query = req.query
        candidates = self.collector.collect_candidates(search_query, limit=10)

        # Filter out rejected video IDs
        candidates = [c for c in candidates if c.video_id not in active_rejected]

        # Score candidates
        for c in candidates:
            MediaMatchScorer.score_candidate(req, c)

        candidates.sort(key=lambda x: x.score, reverse=True)

        top_score = candidates[0].score if candidates else 0.0

        # 2. Search refinement pass if initial scores are low (< 0.45)
        if top_score < 0.45:
            refinements = SearchQueryRefiner.get_refined_queries(req)
            for refined_q in refinements[:2]:
                logger.debug("Refining media search query: '%s'", refined_q)
                ref_candidates = self.collector.collect_candidates(refined_q, limit=10)
                ref_candidates = [c for c in ref_candidates if c.video_id not in active_rejected]
                for c in ref_candidates:
                    MediaMatchScorer.score_candidate(req, c)

                # Merge unique candidates
                existing_ids = {c.video_id for c in candidates}
                for rc in ref_candidates:
                    if rc.video_id not in existing_ids:
                        candidates.append(rc)

            candidates.sort(key=lambda x: x.score, reverse=True)

        selected: VideoCandidate | None = None
        # Confident threshold: require score >= 0.50 to avoid playing unrelated results
        if candidates and candidates[0].score >= 0.50:
            selected = candidates[0]
            self.last_candidate = selected

        log_media_diagnostics(req, candidates, selected, search_query)
        return selected, req, candidates
