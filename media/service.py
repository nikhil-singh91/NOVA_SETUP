"""Central media playback service coordinating parsing, collection, scoring, and playback verification."""

from __future__ import annotations

import os

from config.settings import settings
from core.logger import get_logger

from media.collector import YouTubeCandidateCollector
from media.models import (
    MediaRequest,
    ShortTermMusicContext,
    VideoCandidate,
)
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
    print("INTENT:          PLAY_MEDIA / LISTEN_TO_MUSIC")
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

    def handle_user_rejection(self, music_context: ShortTermMusicContext | None = None) -> VideoCandidate | None:
        """Handle user feedback ('No, not this one') by rejecting current candidate and picking next best."""
        if not self.last_request or not self.last_candidate:
            return None

        self.rejected_video_ids.add(self.last_candidate.video_id)
        if music_context:
            music_context.rejected_video_ids.add(self.last_candidate.video_id)

        logger.info(
            "User rejected video %s ('%s'). Selecting next best candidate...",
            self.last_candidate.video_id,
            self.last_candidate.title,
        )
        best, _, _ = self.resolve_best_video(
            self.last_request.original_text,
            rejected_ids=self.rejected_video_ids,
            music_context=music_context,
        )
        return best

    def resolve_best_video(
        self,
        query_or_text: str,
        rejected_ids: set[str] | None = None,
        music_context: ShortTermMusicContext | None = None,
        is_generic_listen: bool = False,
    ) -> tuple[VideoCandidate | None, MediaRequest, list[VideoCandidate]]:
        """Resolve the best matching video candidate for a media query, with no-repeat guarantees."""
        req: MediaRequest = MediaRequestParser.parse(query_or_text)
        self.last_request = req
        active_rejected = set(rejected_ids or set())
        if music_context:
            active_rejected.update(music_context.rejected_video_ids)

        # Update or infer music context preference from the request
        if music_context and not is_generic_listen:
            self._update_context_from_request(req, music_context)

        # 1. Determine Search Query
        search_query = req.query
        if is_generic_listen or not search_query or search_query.lower() in ("trending music", "music", "songs"):
            if music_context and music_context.is_fresh() and not music_context.preference.is_empty:
                # Use context preference with dynamic variation
                search_query = music_context.preference.to_search_query(
                    variation_index=len(music_context.recently_played)
                )
                logger.info(
                    "Resolved generic music request to context-derived query: '%s' (Pref: %s)",
                    search_query,
                    music_context.preference.model_dump(),
                )
            else:
                search_query = "Trending Music"

        # When resolving generic listen or follow-ups, score against the effective search query
        scoring_req = req
        if is_generic_listen or not req.query or req.query.lower() in ("trending music", "music", "songs", "another one", "one more", "something else", "next song"):
            scoring_req = MediaRequestParser.parse(search_query)

        candidates = self.collector.collect_candidates(search_query, limit=12)

        # Filter out rejected video IDs
        candidates = [c for c in candidates if c.video_id not in active_rejected]

        # Score candidates with repeat penalty
        for c in candidates:
            MediaMatchScorer.score_candidate(scoring_req, c, music_context=music_context)

        candidates.sort(key=lambda x: x.score, reverse=True)

        top_score = candidates[0].score if candidates else 0.0

        # 2. Search refinement or alternative candidate search if top score is low or all were repeats
        if top_score < 0.45 or (music_context and candidates and all(music_context.is_recently_played(c.video_id, c.title) for c in candidates)):
            refinements: list[str] = []
            if is_generic_listen and music_context and not music_context.preference.is_empty:
                refinements = [
                    music_context.preference.to_search_query(variation_index=len(music_context.recently_played) + 1),
                    music_context.preference.to_search_query(variation_index=len(music_context.recently_played) + 2),
                ]
            else:
                refinements = SearchQueryRefiner.get_refined_queries(req)

            existing_ids = {c.video_id for c in candidates}
            for refined_q in refinements[:3]:
                logger.debug("Refining media search query for candidate pool: '%s'", refined_q)
                ref_candidates = self.collector.collect_candidates(refined_q, limit=10)
                ref_candidates = [c for c in ref_candidates if c.video_id not in active_rejected and c.video_id not in existing_ids]
                refined_scoring_req = MediaRequestParser.parse(refined_q)
                for c in ref_candidates:
                    MediaMatchScorer.score_candidate(refined_scoring_req, c, music_context=music_context)
                    candidates.append(c)
                    existing_ids.add(c.video_id)

            candidates.sort(key=lambda x: x.score, reverse=True)

        # 3. Select non-repeated candidate
        selected: VideoCandidate | None = None
        min_threshold = 0.25 if is_generic_listen else 0.40
        for cand in candidates:
            if cand.score >= min_threshold:
                if music_context and music_context.is_recently_played(cand.video_id, cand.title):
                    continue  # strictly avoid recent duplicates if alternatives exist
                selected = cand
                break

        # Fallback: if all valid candidates have been played in this session, pick the highest scoring available one
        if selected is None and candidates and candidates[0].score >= max(0.20, min_threshold - 0.05):
            selected = candidates[0]

        if selected:
            self.last_candidate = selected

        log_media_diagnostics(req, candidates, selected, search_query)
        return selected, req, candidates

    def _update_context_from_request(self, req: MediaRequest, music_context: ShortTermMusicContext) -> None:
        """Infer and update music context preference from structured request parameters."""
        q_lower = req.query.lower()

        # Artist detection
        import re
        m_art = re.search(r"^(?:songs\s+by|music\s+by)\s+(.+)$", req.query, re.I)
        if m_art:
            music_context.update_preference(artist=m_art.group(1).strip())
            return

        # Check for explicit language/genre/mood keywords
        languages = {"hindi", "english", "punjabi", "bhojpuri", "tamil", "telugu", "spanish", "korean"}
        genres = {"pop", "rock", "classical", "jazz", "rap", "hip hop", "lofi", "lo-fi", "ghazal", "bhajan", "devotional"}
        moods = {"romantic", "sad", "party", "chill", "relaxing", "workout", "gym"}

        words = set(re.findall(r"\w+", q_lower))
        found_lang = next((w.title() for w in words if w in languages), None)
        found_genre = next((w.title() for w in words if w in genres), None)
        found_mood = next((w.title() for w in words if w in moods), None)

        # Detect artist pattern: "<Artist> songs" or "some <Artist>"
        m_artist_songs = re.search(r"^(.+?)\s+(?:songs|song|gaane|gaana|hits|music)$", req.query, re.I)
        m_some_art = re.search(r"^some\s+(.+)$", req.query, re.I)
        found_artist = None
        if m_artist_songs:
            cand_artist = m_artist_songs.group(1).strip()
            if cand_artist.lower().startswith("some "):
                cand_artist = cand_artist[5:].strip()
            cand_words = set(re.findall(r"\w+", cand_artist.lower()))
            if not (cand_words & (languages | genres | moods)):
                found_artist = cand_artist.title()
        elif m_some_art:
            cand_artist = m_some_art.group(1).strip()
            cand_words = set(re.findall(r"\w+", cand_artist.lower()))
            if not (cand_words & (languages | genres | moods)):
                found_artist = cand_artist.title()

        if found_artist or found_lang or found_genre or found_mood:
            music_context.update_preference(
                artist=found_artist,
                language=found_lang,
                genre=found_genre,
                mood=found_mood,
                override_all=bool(found_artist or (found_lang and not found_artist)),
            )
