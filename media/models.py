"""Data models for structured media requests, video candidate collection, and matching scores."""

from __future__ import annotations

from enum import Enum
from typing import Any
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
