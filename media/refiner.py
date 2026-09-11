"""Query refinement generator for bounded search retries when initial match scores are low."""

from __future__ import annotations

from media.models import MediaRequest, MediaType


class SearchQueryRefiner:
    """Generates targeted query refinements for media searches while preserving core request tokens."""

    @classmethod
    def get_refined_queries(cls, req: MediaRequest) -> list[str]:
        """Return 1-2 prioritized refined search queries for the request."""
        refined: list[str] = []

        if req.media_type == MediaType.EPISODE and req.series_name and req.episode_number:
            refined.append(f"{req.series_name} episode {req.episode_number} full episode")
            refined.append(f"{req.series_name} episode {req.episode_number} official")
        elif req.media_type == MediaType.SONG:
            if "remix" in req.modifiers:
                refined.append(f"{req.query} official remix")
            elif "lyrics" in req.modifiers:
                refined.append(f"{req.query} official lyrics")
            else:
                refined.append(f"{req.query} official song")
                refined.append(f"{req.query} full video song")
        elif req.media_type == MediaType.TUTORIAL:
            refined.append(f"{req.query} complete tutorial")
        elif req.media_type == MediaType.SHOW:
            refined.append(f"{req.query} full episode official")

        return refined
