"""NOVA Browser Actions V1 & V2: Web understanding and multi-step task execution subsystem."""

from __future__ import annotations

from browser.context import BrowserContextManager
from browser.engine import BaseBrowserEngine, MacOSNativeBrowserEngine
from browser.extractor import PageContentExtractor
from browser.manager import BrowserManager
from browser.models import (
    ActionType,
    BrowserActionCancelled,
    BrowserActionPlan,
    BrowserContext,
    BrowserError,
    BrowserLaunchError,
    BrowserNotFoundError,
    BrowserResult,
    BrowserTaskCancelled,
    BrowserTaskPlan,
    BrowserTaskPlanningError,
    BrowserTaskTimeout,
    NavigationError,
    PageContent,
    PageExtractionError,
    Platform,
    SearchResultItem,
    SensitiveActionBlockedError,
    TabNotFoundError,
    TaskStep,
    UnsupportedPageAction,
    WebsiteUnsupportedError,
)
from browser.parser import BrowserIntentParser
from browser.planner import BrowserTaskPlanner
from browser.router import BrowserActionRouter
from browser.safety import BrowserSafetyPolicy
from browser.sessions import BrowserSessionManager
from browser.sites import (
    AmazonSkill,
    BaseSiteSkill,
    GenericSiteSkill,
    GitHubSkill,
    GoogleSkill,
    YouTubeSkill,
)

__all__ = [
    "BrowserManager",
    "BrowserActionPlan",
    "BrowserResult",
    "ActionType",
    "Platform",
    "PageContent",
    "SearchResultItem",
    "TaskStep",
    "BrowserTaskPlan",
    "BrowserContext",
    "BrowserIntentParser",
    "BrowserActionRouter",
    "BrowserTaskPlanner",
    "BrowserContextManager",
    "PageContentExtractor",
    "BrowserSafetyPolicy",
    "BaseBrowserEngine",
    "MacOSNativeBrowserEngine",
    "BrowserSessionManager",
    "BaseSiteSkill",
    "YouTubeSkill",
    "GoogleSkill",
    "AmazonSkill",
    "GitHubSkill",
    "GenericSiteSkill",
    "BrowserError",
    "BrowserNotFoundError",
    "BrowserLaunchError",
    "NavigationError",
    "WebsiteUnsupportedError",
    "BrowserActionCancelled",
    "SensitiveActionBlockedError",
    "PageExtractionError",
    "BrowserTaskPlanningError",
    "BrowserTaskTimeout",
    "BrowserTaskCancelled",
    "TabNotFoundError",
    "UnsupportedPageAction",
]
