"""Extended data models, enums, results, page content, and task plans for NOVA Browser Actions V2."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    """Canonical browser interaction intent types."""

    # V1 Base Actions
    OPEN_SITE = "open_site"
    OPEN_NEW_TAB = "open_new_tab"
    SEARCH_CURRENT_TAB = "search_current_tab"
    SEARCH_WEB = "search_web"
    SEARCH_SITE = "search_site"
    PLAY_MEDIA = "play_media"
    LISTEN_TO_MUSIC = "listen_to_music"
    WATCH_VIDEO = "watch_video"
    WATCH_SHORTS = "watch_shorts"
    START_AUTO_SHORTS = "start_auto_shorts"
    STOP_AUTO_SHORTS = "stop_auto_shorts"
    PAUSE_AUTO_SHORTS = "pause_auto_shorts"
    RESUME_AUTO_SHORTS = "resume_auto_shorts"
    NEXT_ITEM = "next_item"
    PREVIOUS_ITEM = "previous_item"
    OPEN_RESULT = "open_result"
    CLOSE_TAB = "close_tab"
    STOP_ACTION = "stop_action"

    # V2 Web Understanding & Multi-Step Actions
    READ_PAGE = "read_page"
    SUMMARIZE_PAGE = "summarize_page"
    EXPLAIN_PAGE = "explain_page"
    RESEARCH_TOPIC = "research_topic"
    COMPARE_PRODUCTS = "compare_products"
    NAVIGATE_BACK = "navigate_back"
    NAVIGATE_FORWARD = "navigate_forward"
    SCROLL_PAGE = "scroll_page"
    CLOSE_RESEARCH_TABS = "close_research_tabs"
    SWITCH_TAB = "switch_tab"


class Platform(str, Enum):
    """Supported target web platforms."""

    YOUTUBE = "youtube"
    GOOGLE = "google"
    AMAZON = "amazon"
    GITHUB = "github"
    WIKIPEDIA = "wikipedia"
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    NETFLIX = "netflix"
    SPOTIFY = "spotify"
    REDDIT = "reddit"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    GENERIC = "generic"


@dataclass
class PageContent:
    """Structured extraction of readable content from an active webpage."""

    url: str
    title: str
    text: str
    headings: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_empty(self) -> bool:
        """Return True if no meaningful text was extracted."""
        return not bool(self.text and self.text.strip())


@dataclass
class SearchResultItem:
    """A single structured organic search result item."""

    index: int
    title: str
    url: str
    snippet: str = ""


@dataclass
class TaskStep:
    """A single executable step within a multi-step browser task plan."""

    step_number: int
    action: str
    target: str
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # "pending", "in_progress", "completed", "failed", "cancelled"
    result: Any | None = None


@dataclass
class BrowserTaskPlan:
    """Structured plan for multi-step browser research or automation execution."""

    goal: str
    steps: list[TaskStep] = field(default_factory=list)
    task_id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:6]}")
    status: str = "pending"  # "pending", "in_progress", "completed", "failed", "cancelled"
    max_steps: int = 6
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BrowserActionPlan:
    """Structured plan produced by intent parser for execution."""

    action_type: ActionType
    platform: Platform = Platform.GENERIC
    query: str = ""
    target_url: str = ""
    raw_prompt: str = ""
    target_index: int | None = None  # For ordinal references like "open the second one" (2)
    is_sensitive: bool = False
    requires_confirmation: bool = False
    confirmation_prompt: str = ""
    auto_navigation: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> ActionType:
        return self.action_type


@dataclass
class BrowserResult:
    """Structured output returned from browser action execution."""

    success: bool
    action_type: ActionType
    message: str
    spoken_response: str = ""
    url: str = ""
    error: str | None = None
    page_content: PageContent | None = None
    task_plan: BrowserTaskPlan | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.spoken_response and self.message:
            self.spoken_response = self.message

    @property
    def details(self) -> dict[str, Any]:
        return self.metadata


@dataclass
class BrowserContext:
    """Short-term browser state and history for reference resolution."""

    last_search_query: str | None = None
    last_search_results: list[SearchResultItem] = field(default_factory=list)
    active_page: PageContent | None = None
    research_tabs: list[str] = field(default_factory=list)
    recent_pages: list[PageContent] = field(default_factory=list)
    current_task: BrowserTaskPlan | None = None


# ==============================================================================
# Custom Browser Exceptions
# ==============================================================================

class BrowserError(Exception):
    """Base exception for all browser automation failures."""


class BrowserNotFoundError(BrowserError):
    """Raised when the configured browser executable or application is not found."""


class BrowserLaunchError(BrowserError):
    """Raised when the browser cannot be launched or connected to."""


class NavigationError(BrowserError):
    """Raised when opening a URL or page navigation fails."""


class WebsiteUnsupportedError(BrowserError):
    """Raised when an requested website or operation is not supported."""


class BrowserActionCancelled(BrowserError):
    """Raised when a running browser action or auto-navigation loop is cancelled by the user."""


class BrowserTaskCancelled(BrowserActionCancelled):
    """Raised when a multi-step browser task or research operation is cancelled by the user."""


class SensitiveActionBlockedError(BrowserError):
    """Raised when a sensitive action requires user confirmation before proceeding."""


class PageExtractionError(BrowserError):
    """Raised when extracting readable content from a webpage fails."""


class BrowserTaskPlanningError(BrowserError):
    """Raised when generating a multi-step browser plan fails."""


class BrowserTaskTimeout(BrowserError):
    """Raised when a multi-step task exceeds configured time limits."""


class TabNotFoundError(BrowserError):
    """Raised when attempting to operate on a closed or non-existent tab."""


class UnsupportedPageAction(BrowserError):
    """Raised when a requested DOM or interaction action is unsupported on current page."""
