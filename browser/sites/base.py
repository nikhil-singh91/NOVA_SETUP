"""Base specification for site-specific browser automation skills."""

from __future__ import annotations

from abc import ABC, abstractmethod

from browser.engine import BaseBrowserEngine
from browser.models import BrowserActionPlan, BrowserResult
from browser.sessions import BrowserSessionManager


class BaseSiteSkill(ABC):
    """Abstract contract for website-specific automation skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique identifier for this skill."""

    @abstractmethod
    def can_handle(self, plan: BrowserActionPlan) -> bool:
        """Return True if this skill is capable of handling the action plan."""

    @abstractmethod
    def execute(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
    ) -> BrowserResult:
        """Execute the browser action plan and return a structured BrowserResult."""
