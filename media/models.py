"""Data models for structured media requests, video candidate collection, and matching scores."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class MediaType(str, Enum):
    """Categorical media types."""
    SONG = "song"
    MUSIC_VIDEO = "music_video"
    SHOW = "show"
    EPISODE = "episode"
    TUTORIAL = "tutorial"
    SHORT = "short"
    GENERAL_VIDEO = "general_video"


class MusicIntent(str, Enum):
    """Specific semantic intent categories for music listening."""
    PLAY_SPECIFIC_SONG = "play_specific_song"
    PLAY_ARTIST = "play_artist"
    PLAY_GENRE = "play_genre"
    PLAY_MOOD = "play_mood"
    LISTEN_TO_MUSIC = "listen_to_music"
    SEARCH_MUSIC = "search_music"


class MediaRequest(BaseModel):
    """Structured representation of a user's media playback request."""

    original_text: str
    query: str
    media_type: MediaType = MediaType.GENERAL_VIDEO
    series_name: str | None = None
    episode_number: int | None = None
    season_number: int | None = None
    modifiers: list[str] = Field(default_factory=list)  # e.g. ["remix", "official", "live", "lyrics", "cover"]
    requested_platform: str = "youtube"
    language: str | None = None
    confidence: float = 1.0


class VideoCandidate(BaseModel):
    """Structured video result extracted from YouTube search results."""

    video_id: str
    title: str
    channel: str = ""
    duration_str: str = ""
    duration_seconds: int = 0
    url: str = ""
    badges: list[str] = Field(default_factory=list)
    position: int = 0
    is_short: bool = False
    is_live: bool = False
    is_playlist: bool = False
    score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)


class MusicTrack(BaseModel):
    """Record of a verified played or selected track in recent music context."""

    video_id: str
    title: str
    clean_title: str = ""
    artist: str | None = None
    channel: str = ""
    url: str = ""
    played_at: float = Field(default_factory=lambda: datetime.now(UTC).timestamp())

    @property
    def normalized_title(self) -> str:
        t = self.clean_title or self.title
        # strip punctuation and extra spaces
        t = re.sub(r"[^\w\s]", " ", t.lower())
        return " ".join(t.split())


class MusicPreference(BaseModel):
    """Active conversational music preference."""

    artist: str | None = None
    genre: str | None = None
    mood: str | None = None
    language: str | None = None
    updated_at: float = Field(default_factory=lambda: datetime.now(UTC).timestamp())

    @property
    def is_empty(self) -> bool:
        return not any([self.artist, self.genre, self.mood, self.language])

    def to_search_query(self, variation_index: int = 0) -> str:
        """Construct a natural, dynamic search query from this active preference."""
        variations: list[str] = []
        if self.artist:
            if self.language and self.language.lower() not in self.artist.lower():
                variations = [
                    f"{self.artist} {self.language} songs",
                    f"{self.artist} best songs",
                    f"{self.artist} top hits",
                    f"{self.artist} live acoustic",
                    f"{self.artist} latest songs",
                ]
            else:
                variations = [
                    f"{self.artist} songs",
                    f"{self.artist} best songs",
                    f"{self.artist} top hits",
                    f"{self.artist} music",
                    f"{self.artist} latest songs",
                ]
        elif self.genre or self.mood:
            pref_part = f"{self.mood or ''} {self.genre or ''}".strip()
            lang_part = self.language or ""
            base = f"{lang_part} {pref_part} songs".strip()
            variations = [
                base,
                f"best {base}",
                f"popular {base}",
                f"top {base} playlist",
                f"{base} acoustic live",
            ]
        elif self.language:
            variations = [
                f"top {self.language} songs",
                f"popular {self.language} songs",
                f"best {self.language} hits",
                f"latest {self.language} songs",
            ]
        else:
            variations = [
                "trending songs",
                "popular music hits",
                "top songs today",
                "best music mix",
            ]

        idx = variation_index % len(variations)
        return variations[idx]


class ShortTermMusicContext(BaseModel):
    """Bounded, short-term music session context tracking recent preferences and played history."""

    active: bool = False
    preference: MusicPreference = Field(default_factory=MusicPreference)
    recently_played: list[MusicTrack] = Field(default_factory=list)
    current_track: MusicTrack | None = None
    last_action: str = ""
    last_action_time: float = Field(default_factory=lambda: datetime.now(UTC).timestamp())
    rejected_video_ids: set[str] = Field(default_factory=set)
    max_history_size: int = 20

    def update_preference(
        self,
        artist: str | None = None,
        genre: str | None = None,
        mood: str | None = None,
        language: str | None = None,
        override_all: bool = False,
    ) -> None:
        """Update active preference signals while maintaining session recency."""
        self.active = True
        self.last_action_time = datetime.now(UTC).timestamp()
        if override_all:
            self.preference = MusicPreference(
                artist=artist,
                genre=genre,
                mood=mood,
                language=language,
            )
        else:
            if artist is not None:
                self.preference.artist = artist
            if genre is not None:
                self.preference.genre = genre
            if mood is not None:
                self.preference.mood = mood
            if language is not None:
                self.preference.language = language
            self.preference.updated_at = self.last_action_time

    def add_played_track(
        self,
        video_id: str,
        title: str,
        channel: str = "",
        artist: str | None = None,
        url: str = "",
    ) -> MusicTrack:
        """Record a played track in bounded recent history to guarantee no repeats."""
        clean_title = re.sub(r"\s*-\s*(?:YouTube|Topic)$", "", title, flags=re.IGNORECASE).strip()
        short_title = clean_title.split("|")[0].split("-")[0].strip() or clean_title
        track = MusicTrack(
            video_id=video_id,
            title=title,
            clean_title=short_title,
            artist=artist or self.preference.artist,
            channel=channel,
            url=url or f"https://www.youtube.com/watch?v={video_id}",
            played_at=datetime.now(UTC).timestamp(),
        )
        self.current_track = track
        self.active = True
        self.last_action = "PLAY"
        self.last_action_time = track.played_at

        # Avoid duplicate video_id entries in history
        self.recently_played = [t for t in self.recently_played if t.video_id != video_id]
        self.recently_played.append(track)
        if len(self.recently_played) > self.max_history_size:
            self.recently_played = self.recently_played[-self.max_history_size:]
        return track

    def is_recently_played(self, video_id: str, title: str | None = None) -> bool:
        """Check if video_id or exact title was recently played."""
        # 1. Exact Video ID match
        if any(t.video_id == video_id for t in self.recently_played):
            return True

        # 2. Title matching after stripping artist and generic tokens
        if title:
            norm_q = re.sub(r"[^\w\s]", " ", title.lower()).strip()
            norm_q_clean = " ".join(norm_q.split())
            for t in self.recently_played:
                norm_full = re.sub(r"[^\w\s]", " ", t.title.lower()).strip()
                norm_full_clean = " ".join(norm_full.split())
                if norm_q_clean == norm_full_clean:
                    return True

                # Check short clean title exact match
                if t.clean_title:
                    norm_clean_t = re.sub(r"[^\w\s]", " ", t.clean_title.lower()).strip()
                    norm_clean_t = " ".join(norm_clean_t.split())
                    if norm_clean_t and norm_clean_t == norm_q_clean:
                        return True

                # Check core tokens excluding artist and boilerplate words
                stop_tokens = {"song", "songs", "video", "videos", "official", "audio", "lyrics", "full", "hd", "4k", "music", "lyrical"}
                if t.artist:
                    stop_tokens.update(re.findall(r"\w+", t.artist.lower()))
                if self.preference.artist:
                    stop_tokens.update(re.findall(r"\w+", self.preference.artist.lower()))

                q_tokens = [w for w in norm_q.split() if w not in stop_tokens and len(w) > 1]
                t_tokens = [w for w in norm_full.split() if w not in stop_tokens and len(w) > 1]

                if q_tokens and t_tokens:
                    q_set = set(q_tokens)
                    t_set = set(t_tokens)
                    if q_set == t_set:
                        return True
                    overlap = len(q_set & t_set) / max(len(q_set), len(t_set))
                    if overlap >= 0.85:
                        return True
        return False

    def is_fresh(self, max_age_seconds: float = 600.0) -> bool:
        """Check if music context is sufficiently fresh (default 10 minutes)."""
        elapsed = datetime.now(UTC).timestamp() - self.last_action_time
        return self.active and (elapsed <= max_age_seconds)

    def deactivate(self) -> None:
        """Deactivate music session without losing history."""
        self.active = False
