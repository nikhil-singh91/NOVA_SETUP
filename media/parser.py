"""Structured media request parser extracting media types, episode numbers, and modifiers."""

from __future__ import annotations

import re

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

    NON_MEDIA_QUERIES = frozenset({
        "youtube search",
        "youtube shorts",
        "shorts",
        "search",
        "youtube",
        "video",
        "song",
        "songs",
        "music",
        "audio",
        "google",
    })

    @classmethod
    def parse(cls, text: str) -> MediaRequest:
        """Parse raw text or normalized query into a structured MediaRequest."""
        raw = text.strip()
        working = raw

        # 0. Strip wake-word prefix
        working = re.sub(
            r"^(?:hey\s+|ok\s+|okay\s+)?nova\s*[,:]*\s*",
            "",
            working,
            flags=re.IGNORECASE,
        ).strip()

        # 1. Detect and strip command prefixes (English + Hindi/Hinglish)
        working = re.sub(
            r"^(?:can\s+you\s+please\s+|please\s+)?(?:play|watch|listen\s+to|i\s+want\s+to\s+(?:watch|listen\s+to|hear)|show\s+me)\s+(?:the\s+|an?\s+)?(?:song\s+by\s+|track\s+by\s+)?(?:song\s+|video\s+|track\s+|episode\s+)?",
            "",
            working,
            flags=re.IGNORECASE,
        ).strip()
        working = re.sub(
            r"^(?:baja\s+do|bajao|bhajao|chala\s+do|chalao|chalu\s+karo|chalu\s+kar\s+do|sunao|suna\s+do|lagao|laga\s+do)\s+(?:koi\s+)?(?:accha\s+sa\s+|ek\s+)?(?:gaana|song|songs|music|track)?\s*",
            "",
            working,
            flags=re.IGNORECASE,
        ).strip()

        # Strip platform prefix/postfix
        working = re.sub(
            r"^(?:youtube\s+(?:pe|par|me|mein)|on\s+youtube)\s+",
            "",
            working,
            flags=re.IGNORECASE,
        ).strip()
        working = re.sub(r"\s+on\s+youtube\s*$", "", working, flags=re.IGNORECASE).strip()

        # Strip Hindi/Hinglish command postfixes
        working = re.sub(
            r"\s+(?:ke\s+|ka\s+|wala\s+|wali\s+)?(?:gaana|gaane|geet|song|songs|music|track)?\s*(?:bhajao|bajao|baja\s+do|baja\s+dijiye|bajana|chala\s+do|chalao|chalu\s+karo|chalu\s+kar\s+do|sunao|suna\s+do|lagao|laga\s+do|play\s+karo)\s*$",
            "",
            working,
            flags=re.IGNORECASE,
        ).strip()

        # Clean trailing auxiliary particles
        working = re.sub(
            r"\s+(?:ke|ka|wala|wali|song|songs|gaana)\s*$",
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
        media_type = MediaType.SONG  # Default for media playback
        episode_number = None
        season_number = None
        series_name = None

        # Check Episode patterns
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
            k in lower_working
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
        elif any(k in lower_working for k in ["shorts", "short"]):
            media_type = MediaType.SHORT
        elif any(k in lower_working for k in ["cartoon", "show", "anime", "series"]):
            media_type = MediaType.SHOW
        else:
            media_type = MediaType.SONG

        clean_query = working.strip()

        # Disallow non-media queries from pretending to be song queries
        if clean_query.lower() in cls.NON_MEDIA_QUERIES:
            clean_query = ""

        return MediaRequest(
            original_text=raw,
            query=clean_query or raw,
            media_type=media_type,
            series_name=series_name,
            episode_number=episode_number,
            season_number=season_number,
            modifiers=found_modifiers,
            requested_platform="youtube",
            confidence=1.0 if clean_query else 0.0,
        )
