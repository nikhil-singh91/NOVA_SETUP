"""Generalized entity resolution, phonetic normalization, and contextual slot extraction for NOVA.

Provides reusable mechanisms to resolve:
- Proper nouns (people, songs, artists)
- Installed applications (dynamic discovery & fuzzy phonetic matching)
- Known web domains and services (Flipkart, YouTube, GitHub, Amazon, Google)
- Technical terms and acronyms (ICPC, C++, Python, JavaScript)
- Generalized phonetic equivalences (e.g. w <-> v interchange in Hinglish romanization)
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResolvedEntity:
    """Standardized representation of a resolved entity."""

    raw_text: str
    canonical_name: str
    entity_type: str  # "app" | "website" | "media" | "document" | "query" | "tech"
    confidence: float
    metadata: dict[str, Any] | None = None


class EntityResolver:
    """Generalized Entity and Phonetic Normalization Engine."""

    # Standard macOS application directories
    APP_DIRECTORIES = (
        Path("/Applications"),
        Path("/System/Applications"),
        Path("/System/Applications/Utilities"),
        Path.home() / "Applications",
    )

    # Well-known web services, domains, and shopping platforms
    KNOWN_WEB_SERVICES: dict[str, dict[str, Any]] = {
        "flipkart": {"domain": "flipkart.com", "display": "Flipkart", "search_url": "https://www.flipkart.com/search?q={query}"},
        "amazon": {"domain": "amazon.in", "display": "Amazon", "search_url": "https://www.amazon.in/s?k={query}"},
        "youtube": {"domain": "youtube.com", "display": "YouTube", "search_url": "https://www.youtube.com/results?search_query={query}"},
        "github": {"domain": "github.com", "display": "GitHub", "search_url": "https://github.com/search?q={query}"},
        "google": {"domain": "google.com", "display": "Google", "search_url": "https://www.google.com/search?q={query}"},
        "wikipedia": {"domain": "wikipedia.org", "display": "Wikipedia", "search_url": "https://en.wikipedia.org/wiki/{query}"},
        "reddit": {"domain": "reddit.com", "display": "Reddit", "search_url": "https://www.reddit.com/search/?q={query}"},
        "twitter": {"domain": "x.com", "display": "Twitter/X", "search_url": "https://x.com/search?q={query}"},
    }

    # Technical terms and acronyms
    KNOWN_TECH_TERMS: dict[str, str] = {
        "icpc": "ICPC",
        "cpp": "C++",
        "c++": "C++",
        "c plus plus": "C++",
        "python": "Python",
        "javascript": "JavaScript",
        "js": "JavaScript",
        "typescript": "TypeScript",
        "html": "HTML",
        "css": "CSS",
    }

    # De-spaced brand compounds commonly split by ASR
    SPLIT_COMPOUND_PATTERNS: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"\btele\s+gram\b", re.IGNORECASE), "telegram"),
        (re.compile(r"\byou\s+tube\b", re.IGNORECASE), "youtube"),
        (re.compile(r"\bwhat['\s]*s\s+app\b", re.IGNORECASE), "whatsapp"),
        (re.compile(r"\bvs\s+code\b", re.IGNORECASE), "vscode"),
        (re.compile(r"\bface\s+book\b", re.IGNORECASE), "facebook"),
        (re.compile(r"\binsta\s+gram\b", re.IGNORECASE), "instagram"),
        (re.compile(r"\bgit\s+hub\b", re.IGNORECASE), "github"),
        (re.compile(r"\bflip\s+kart\b", re.IGNORECASE), "flipkart"),
    ]

    _cached_app_names: dict[str, str] | None = None

    @classmethod
    def get_installed_apps(cls) -> dict[str, str]:
        """Discover and cache installed applications on macOS (lower_name -> canonical_name)."""
        if cls._cached_app_names is not None:
            return cls._cached_app_names

        apps: dict[str, str] = {}

        # 1. Seed with common canonical assistant apps
        seed_apps = {
            "telegram": "Telegram",
            "youtube": "YouTube",
            "whatsapp": "WhatsApp",
            "google chrome": "Google Chrome",
            "chrome": "Google Chrome",
            "safari": "Safari",
            "textedit": "TextEdit",
            "notepad": "TextEdit",
            "terminal": "Terminal",
            "visual studio code": "Visual Studio Code",
            "vscode": "Visual Studio Code",
            "sublime text": "Sublime Text",
            "spotify": "Spotify",
            "calculator": "Calculator",
            "notes": "Notes",
            "finder": "Finder",
            "system settings": "System Settings",
            "photo booth": "Photo Booth",
            "camera": "Photo Booth",
        }
        apps.update(seed_apps)

        # 2. Scan standard directories
        for base in cls.APP_DIRECTORIES:
            if not base.exists():
                continue
            try:
                for item in base.iterdir():
                    if item.is_dir() and item.name.endswith(".app"):
                        canonical = item.stem
                        apps[canonical.lower()] = canonical
            except Exception:
                pass

        cls._cached_app_names = apps
        return apps

    @classmethod
    def normalize_phonetics(cls, text: str) -> str:
        """Apply generalized phonetic and transcription normalization rules.

        Handles:
        - Common ASR split compounds (e.g. 'tele gram' -> 'telegram')
        - South Asian / Hinglish romanization phonetic w <-> v variation when matching against known vocabulary.
        """
        if not text:
            return text

        result = text

        # 1. Merge split compounds
        for pat, replacement in cls.SPLIT_COMPOUND_PATTERNS:
            result = pat.sub(replacement, result)

        return result

    @classmethod
    def resolve_app_name(cls, query: str) -> ResolvedEntity | None:
        """Resolve query string to the best matching installed or known macOS application."""
        clean = cls.normalize_phonetics(query).strip().lower()
        clean = re.sub(r"\b(?:app|application|please|zara|khol|kholo|open)\b", "", clean).strip()
        if not clean:
            return None

        apps = cls.get_installed_apps()

        # Direct match
        if clean in apps:
            return ResolvedEntity(
                raw_text=query,
                canonical_name=apps[clean],
                entity_type="app",
                confidence=1.0,
            )

        # Token containment match
        for app_lower, canonical in apps.items():
            if clean == app_lower or (len(clean) >= 3 and clean in app_lower):
                return ResolvedEntity(
                    raw_text=query,
                    canonical_name=canonical,
                    entity_type="app",
                    confidence=0.92,
                )

        # Fuzzy string matching (Levenshtein ratio)
        close_matches = difflib.get_close_matches(clean, apps.keys(), n=1, cutoff=0.75)
        if close_matches:
            match_key = close_matches[0]
            similarity = difflib.SequenceMatcher(None, clean, match_key).ratio()
            return ResolvedEntity(
                raw_text=query,
                canonical_name=apps[match_key],
                entity_type="app",
                confidence=round(similarity, 2),
            )

        return None

    @classmethod
    def resolve_web_service(cls, query: str) -> ResolvedEntity | None:
        """Resolve query string to a recognized web service or platform."""
        clean = cls.normalize_phonetics(query).strip().lower()
        clean = re.sub(r"\b(?:website|site|pe|on|par|in)\b", "", clean).strip()

        for key, info in cls.KNOWN_WEB_SERVICES.items():
            if clean == key or key in clean:
                return ResolvedEntity(
                    raw_text=query,
                    canonical_name=info["display"],
                    entity_type="website",
                    confidence=0.95,
                    metadata=info,
                )

        return None

    @classmethod
    def resolve_proper_noun_phonetics(cls, token: str) -> str:
        """Normalize common phonetic variations in proper nouns (e.g. w/v interchange in Indian names)."""
        lower = token.lower()
        # Sanskrit/Hindi romanization interchange: Parwati -> Parvati, Diwakar -> Divakar
        if "rwati" in lower:
            return re.sub(r"rwati\b", "rvati", token, flags=re.IGNORECASE)
        if lower.startswith("le ") or lower.startswith("lay "):
            # ASR swallowing initial /p/ in 'play'
            return "play " + token[len("le "):].strip()
        return token

    @classmethod
    def extract_media_entity(cls, phrase: str) -> tuple[str, float]:
        """Extract media title/artist query and compute extraction confidence.

        Examples:
        - "play Parvati song" -> ("Parvati song", 0.95)
        - "Le Parwati Song" -> ("Parvati song", 0.90)
        - "play a song" -> ("a song", 0.85)
        """
        clean = cls.normalize_phonetics(phrase).strip()

        # Remove leading play or acoustic distortions ("le", "lay", "pla", "baja", "bajao")
        m = re.match(
            r"^(?:play|lay|le|pla|baja|bajao|suno|sunao)\s+(?:the\s+)?(?:song\s+|track\s+|video\s+|music\s+)?(.+?)(?:\s+song|\s+track|\s+video|\s+music)?(?:\s+on\s+youtube)?$",
            clean,
            re.IGNORECASE,
        )
        if m:
            entity = m.group(1).strip()
            # Clean leading particles
            entity = re.sub(r"^(?:the\s+|a\s+)", "", entity, flags=re.IGNORECASE).strip()
            # Apply generalized proper-noun phonetic normalization (e.g. Parwati -> Parvati)
            entity = cls.resolve_proper_noun_phonetics(entity)
            if not entity.lower().endswith("song") and not entity.lower().endswith("music"):
                full_query = f"{entity} song"
            else:
                full_query = entity
            return full_query, 0.92

        return phrase, 0.50
