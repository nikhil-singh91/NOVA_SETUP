"""Browser action site-specific automation skills package."""

from __future__ import annotations

from browser.sites.amazon import AmazonSkill
from browser.sites.base import BaseSiteSkill
from browser.sites.generic import GenericSiteSkill, TRUSTED_SITES
from browser.sites.github import GitHubSkill
from browser.sites.google import GoogleSkill
from browser.sites.youtube import YouTubeSkill

__all__ = [
    "BaseSiteSkill",
    "YouTubeSkill",
    "GoogleSkill",
    "GenericSiteSkill",
    "AmazonSkill",
    "GitHubSkill",
    "TRUSTED_SITES",
]
