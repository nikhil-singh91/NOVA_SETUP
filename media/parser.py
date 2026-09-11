"""Structured media request parser extracting media types, episode numbers, and modifiers."""

from __future__ import annotations

import re
from typing import Any
from core.logger import get_logger
from media.models import MediaRequest, MediaType

logger = get_logger(__name__)


class MediaRequestParser:
    """Parses natural language media commands into structured MediaRequest objects."""

    KNOWN_MODIFIERS = [
        "remix",
        "slowed",
        "reverb",
        "cover",
        "live",
        "lyrics",
        "lyric",
        "original",
        "official",
        "unplugged",
        "acoustic",
        "karaoke",
        "instrumental",
        "dance mix",
        "mashup",
        "lofi",
        "lo-fi",
        "8k",
        "4k",
    ]

    @classmethod
    def parse(cls, text: str) -> MediaRequest:
        """Parse raw text or normalized query into a structured MediaRequest."""
        raw = text.strip()
        working = raw
        lower = working.lower()

        # 1. Detect and strip command prefixes (e.g. "play song", "watch", "i want to watch")
        working = re.sub(
            r"^(?:nova\s*[,:]*\s*)?(?:can\s+you\s+please\s+|please\s+)?(?:play|watch|i\s+want\s+to\s+watch|show\s+me)\s+(?:the\s+)?(?:song\s+|video\s+|track\s+|episode\s+)?",
            "",
            working,
            flags=re.IGNORECASE,
        ).strip()
        working = re.sub(r"\s+on\s+youtube\s*$", "", working, flags=re.IGNORECASE).strip()
        working = re.sub(
            r"\s+(?:gaana\s+chalao|song\s+play\s+karo|play\s+karo|youtube\s+par\s+chalao|chalao)\s*$",
            "",
            working,
            flags=re.IGNORECASE,
        ).strip()

        # 2. Detect Modifiers
        found_modifiers = []
        lower_working = working.lower()
        for mod in cls.KNOWN_MODIFIERS:
            if re.search(rf"\b{re.escape(mod)}\b", lower_working):
                found_modifiers.append(mod)

        # 3. Detect Media Type
        media_type = MediaType.SONG  # Default for "Play [Name]" queries
        episode_number = None
        season_number = None
        series_name = None

        # Check Episode patterns (e.g. "Motu Patlu episode 1", "episode 5", "season 1 episode 2")
        m_ep = re.search(
            r"^(.+?)\s+(?:season\s+(\d+)\s+)?(?:episode|ep)\s+(\d+)",
            working,
            re.IGNORECASE,
        )
        if m_ep:
            media_type = MediaType.EPISODE
            series_name = m_ep.group(1).strip()
            if m_ep.group(2):
                season_number = int(m_ep.group(2))
            episode_number = int(m_ep.group(3))
        elif any(
            k in lower
            for k in [
                "tutorial",
                "guide",
                "course",
                "lecture",
                "dsa",
                "coding",
                "how to",
                "explanation",
                "python",
                "javascript",
            ]
        ):
            media_type = MediaType.TUTORIAL
        elif any(k in lower for k in ["shorts", "short"]):
            media_type = MediaType.SHORT
        elif any(k in lower for k in ["cartoon", "show", "anime", "series"]):
            media_type = MediaType.SHOW
        elif any(
            k in lower
            for k in [
                "song",
                "gaana",
                "track",
                "music",
                "geet",
                "sing",
                "singer",
                "album",
                "kesariya",
                "mere liye",
                "believer",
            ]
        ) or any(
            m in found_modifiers
            for m in [
                "lyrics",
                "remix",
                "acoustic",
                "karaoke",
                "unplugged",
                "official",
                "original",
            ]
        ):
            media_type = MediaType.SONG

        clean_query = working.strip()

        return MediaRequest(
            original_text=raw,
            query=clean_query or raw,
            media_type=media_type,
            series_name=series_name,
            episode_number=episode_number,
            season_number=season_number,
            modifiers=found_modifiers,
            requested_platform="youtube",
            confidence=1.0,
        )
