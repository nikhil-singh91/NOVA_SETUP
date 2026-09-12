"""Universal action router dispatching structured actions to Browser, Desktop, Filesystem, and System tools."""

from __future__ import annotations

import os
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any

from core.environment import environment_observer, log_environment_debug
from core.logger import get_logger
from intent.models import CanonicalIntent, StructuredAction

logger = get_logger(__name__)


class RoutingDomain(str, Enum):
    """Subsystem domain responsible for handling an action."""
    BROWSER = "browser"
    DESKTOP_APP = "desktop_app"
    FILESYSTEM = "filesystem"
    DOCUMENT_WRITING = "document_writing"
    SCREEN_RECORDING = "screen_recording"
    REMINDER = "reminder"
    CALENDAR = "calendar"
    CONFIRMATION = "confirmation"
    VISUAL = "visual"
    TASK_AGENT = "task_agent"
    MEDIA = "media"
    SYSTEM = "system"
    GENERAL_CONVERSATION = "general_conversation"


def get_routing_domain(intent: CanonicalIntent) -> RoutingDomain:
    """Classify a canonical intent into its responsible execution subsystem."""
    if intent in (CanonicalIntent.AUTONOMOUS_TASK,):
        return RoutingDomain.TASK_AGENT
    if intent in (
        CanonicalIntent.OPEN_WEBSITE,
        CanonicalIntent.SEARCH_CURRENT_TAB,
        CanonicalIntent.SEARCH_CURRENT_SITE,
        CanonicalIntent.SEARCH_WEBSITE,
        CanonicalIntent.SEARCH_WEB,
        CanonicalIntent.RESEARCH_TOPIC,
        CanonicalIntent.READ_CURRENT_PAGE,
        CanonicalIntent.SUMMARIZE_CURRENT_PAGE,
        CanonicalIntent.GET_PAGE_TEXT,
        CanonicalIntent.EXPLAIN_PAGE,
        CanonicalIntent.SCROLL_DOWN,
        CanonicalIntent.SCROLL_UP,
        CanonicalIntent.SCROLL_TO_TOP,
        CanonicalIntent.SCROLL_TO_BOTTOM,
        CanonicalIntent.GO_BACK,
        CanonicalIntent.GO_FORWARD,
        CanonicalIntent.OPEN_NEW_TAB,
        CanonicalIntent.NEXT_TAB,
        CanonicalIntent.PREVIOUS_TAB,
        CanonicalIntent.SWITCH_TAB,
        CanonicalIntent.SWITCH_TO_SITE,
        CanonicalIntent.CLOSE_CURRENT_TAB,
        CanonicalIntent.CLOSE_NOVA_TABS,
        CanonicalIntent.OPEN_RESULT,
        CanonicalIntent.COMPARE_PRODUCTS,
        CanonicalIntent.WATCH_SHORTS,
        CanonicalIntent.START_AUTO_SHORTS,
        CanonicalIntent.STOP_AUTO_SHORTS,
    ):
        return RoutingDomain.BROWSER

    if intent in (CanonicalIntent.PLAY_MEDIA,):
        return RoutingDomain.BROWSER

    if intent in (CanonicalIntent.LAUNCH_APP, CanonicalIntent.CLOSE_APP, CanonicalIntent.OPEN_CAMERA, CanonicalIntent.TAKE_PHOTO):
        return RoutingDomain.DESKTOP_APP

    if intent in (
        CanonicalIntent.OPEN_FOLDER,
        CanonicalIntent.FIND_ITEM,
        CanonicalIntent.OPEN_FILE,
        CanonicalIntent.RENAME_ITEM,
        CanonicalIntent.CREATE_DESKTOP_FOLDER,
        CanonicalIntent.CREATE_DESKTOP_FILE,
        CanonicalIntent.CREATE_PROJECT_STRUCTURE,
        CanonicalIntent.WRITE_CODE_FILE,
        CanonicalIntent.CREATE_CODE_PROJECT,
        CanonicalIntent.DELETE_ITEM,
    ):
        return RoutingDomain.FILESYSTEM

    if intent in (CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT,):
        return RoutingDomain.DOCUMENT_WRITING

    if intent in (CanonicalIntent.START_SCREEN_RECORDING, CanonicalIntent.STOP_SCREEN_RECORDING):
        return RoutingDomain.SCREEN_RECORDING

    if intent in (CanonicalIntent.REMINDER_REQUEST,):
        return RoutingDomain.REMINDER

    if intent in (CanonicalIntent.CALENDAR_REQUEST,):
        return RoutingDomain.CALENDAR

    if intent in (CanonicalIntent.CONFIRM_ACTION, CanonicalIntent.DENY_ACTION):
        return RoutingDomain.CONFIRMATION

    if intent in (
        CanonicalIntent.WHAT_AM_I_LOOKING_AT,
        CanonicalIntent.CLICK_UI_ELEMENT,
        CanonicalIntent.TYPE_UI_TEXT,
        CanonicalIntent.CLOSE_POPUP,
        CanonicalIntent.SCROLL_UNTIL_VISIBLE,
        CanonicalIntent.EXPLAIN_SCREEN_ERROR,
    ):
        return RoutingDomain.VISUAL

    if intent in (
        CanonicalIntent.SCREEN_CAPTURE,
        CanonicalIntent.SYSTEM_SHUTDOWN,
        CanonicalIntent.CONTROL_VOLUME,
        CanonicalIntent.CONTROL_BRIGHTNESS,
        CanonicalIntent.CONTROL_WIFI,
        CanonicalIntent.CONTROL_BLUETOOTH,
        CanonicalIntent.GET_CLIPBOARD,
        CanonicalIntent.SET_CLIPBOARD,
        CanonicalIntent.CLEAR_CLIPBOARD,
        CanonicalIntent.LOCK_SCREEN,
        CanonicalIntent.CANCEL_ACTION,
    ):
        return RoutingDomain.SYSTEM

    return RoutingDomain.GENERAL_CONVERSATION


def structured_action_to_browser_plan(action: StructuredAction) -> Any:
    """Translate a StructuredAction into a BrowserActionPlan for BrowserManager."""
    from browser.models import ActionType, BrowserActionPlan, Platform
    raw = action.raw_input
    params = action.parameters

    if action.intent == CanonicalIntent.NEXT_TAB:
        return BrowserActionPlan(action_type=ActionType.SWITCH_TAB, query="next", raw_prompt=raw)

    if action.intent == CanonicalIntent.PREVIOUS_TAB:
        return BrowserActionPlan(action_type=ActionType.SWITCH_TAB, query="previous", raw_prompt=raw)

    if action.intent == CanonicalIntent.OPEN_NEW_TAB:
        browser = params.get("browser")
        meta = {"new_tab": True}
        if browser:
            meta["browser"] = browser
        return BrowserActionPlan(
            action_type=ActionType.OPEN_NEW_TAB,
            target_url="chrome://newtab/",
            metadata=meta,
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.CLOSE_CURRENT_TAB:
        return BrowserActionPlan(action_type=ActionType.CLOSE_TAB, raw_prompt=raw)

    if action.intent == CanonicalIntent.CLOSE_NOVA_TABS:
        return BrowserActionPlan(action_type=ActionType.CLOSE_RESEARCH_TABS, raw_prompt=raw)

    if action.intent == CanonicalIntent.SWITCH_TAB:
        idx = params.get("index", 1)
        return BrowserActionPlan(action_type=ActionType.SWITCH_TAB, query="index", target_index=idx, raw_prompt=raw)

    if action.intent == CanonicalIntent.SWITCH_TO_SITE:
        target = params.get("target", "")
        return BrowserActionPlan(action_type=ActionType.SWITCH_TAB, query=target, raw_prompt=raw)

    if action.intent == CanonicalIntent.READ_CURRENT_PAGE:
        return BrowserActionPlan(action_type=ActionType.READ_PAGE, raw_prompt=raw)

    if action.intent == CanonicalIntent.SUMMARIZE_CURRENT_PAGE:
        return BrowserActionPlan(action_type=ActionType.SUMMARIZE_PAGE, raw_prompt=raw)

    if action.intent == CanonicalIntent.EXPLAIN_PAGE:
        return BrowserActionPlan(action_type=ActionType.EXPLAIN_PAGE, raw_prompt=raw)

    if action.intent == CanonicalIntent.SCROLL_DOWN:
        return BrowserActionPlan(action_type=ActionType.SCROLL_PAGE, query="down", raw_prompt=raw)

    if action.intent == CanonicalIntent.SCROLL_UP:
        return BrowserActionPlan(action_type=ActionType.SCROLL_PAGE, query="up", raw_prompt=raw)

    if action.intent == CanonicalIntent.SCROLL_TO_TOP:
        return BrowserActionPlan(action_type=ActionType.SCROLL_PAGE, query="top", raw_prompt=raw)

    if action.intent == CanonicalIntent.SCROLL_TO_BOTTOM:
        return BrowserActionPlan(action_type=ActionType.SCROLL_PAGE, query="bottom", raw_prompt=raw)

    if action.intent == CanonicalIntent.GO_BACK:
        return BrowserActionPlan(action_type=ActionType.NAVIGATE_BACK, raw_prompt=raw)

    if action.intent == CanonicalIntent.GO_FORWARD:
        return BrowserActionPlan(action_type=ActionType.NAVIGATE_FORWARD, raw_prompt=raw)

    if action.intent == CanonicalIntent.OPEN_WEBSITE:
        entity = params.get("entity", "")
        url = params.get("target_url")
        return BrowserActionPlan(
            action_type=ActionType.OPEN_SITE,
            platform=Platform.GENERIC,
            target_url=url,
            metadata={"site_key": entity},
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.SEARCH_CURRENT_TAB:
        q = params.get("query", "")
        return BrowserActionPlan(
            action_type=ActionType.SEARCH_CURRENT_TAB,
            platform=Platform.GENERIC,
            query=q,
            metadata={"target": "current_tab", "reference": params.get("reference", "this_tab")},
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.SEARCH_CURRENT_SITE:
        q = params.get("query", "")
        ctx = environment_observer.get_context()
        domain = ctx.current_domain or "google.com"
        site_key = domain.replace("www.", "").split(".")[0]
        platform_enum = getattr(Platform, site_key.upper(), Platform.GENERIC)
        return BrowserActionPlan(
            action_type=ActionType.SEARCH_SITE,
            platform=platform_enum,
            query=q,
            metadata={"site_key": site_key, "is_current_site": True},
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.SEARCH_WEBSITE:
        site = params.get("site", "google")
        q = params.get("query", "")
        platform_enum = getattr(Platform, site.upper(), Platform.GENERIC)
        return BrowserActionPlan(
            action_type=ActionType.SEARCH_SITE,
            platform=platform_enum,
            query=q,
            metadata={"site_key": site},
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.SEARCH_WEB:
        q = params.get("query", "")
        return BrowserActionPlan(
            action_type=ActionType.SEARCH_WEB,
            platform=Platform.GOOGLE,
            query=q,
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.RESEARCH_TOPIC:
        q = params.get("query", "")
        return BrowserActionPlan(
            action_type=ActionType.RESEARCH_TOPIC,
            query=q,
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.PLAY_MEDIA:
        q = params.get("query", "")
        return BrowserActionPlan(
            action_type=ActionType.PLAY_MEDIA,
            platform=Platform.YOUTUBE,
            query=q,
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.WATCH_SHORTS:
        q = params.get("query", "")
        return BrowserActionPlan(
            action_type=ActionType.WATCH_SHORTS,
            platform=Platform.YOUTUBE,
            query=q,
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.START_AUTO_SHORTS:
        return BrowserActionPlan(
            action_type=ActionType.START_AUTO_SHORTS,
            platform=Platform.YOUTUBE,
            auto_navigation=True,
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.OPEN_RESULT:
        idx = params.get("target_index", 1)
        return BrowserActionPlan(
            action_type=ActionType.OPEN_RESULT,
            target_index=idx,
            raw_prompt=raw,
        )

    if action.intent == CanonicalIntent.CANCEL_ACTION:
        return BrowserActionPlan(action_type=ActionType.STOP_ACTION, raw_prompt=raw)

    return None


class UniversalActionRouter:
    """Routes structured actions to macOS native application launches or other local tools."""

    @classmethod
    def execute_app_launch(cls, app_name: str) -> bool:
        """Launch a desktop application on macOS using AppLauncher."""
        logger.info("UniversalActionRouter launching app: '%s'", app_name)
        try:
            from desktop.apps import AppLauncher
            success, msg, spoken = AppLauncher.launch(app_name)
            return success
        except Exception as exc:
            logger.error("Failed to launch application '%s': %s", app_name, exc)
            return False
