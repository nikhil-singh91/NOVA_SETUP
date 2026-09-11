"""Canonical intent models and structured action representations for NOVA."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class CanonicalIntent(str, Enum):
    """Universal canonical intents across NOVA subsystems."""

    # Tab Management
    OPEN_NEW_TAB = "open_new_tab"
    NEXT_TAB = "next_tab"
    PREVIOUS_TAB = "previous_tab"
    SWITCH_TAB = "switch_tab"
    SWITCH_TO_SITE = "switch_to_site"
    CLOSE_CURRENT_TAB = "close_current_tab"
    CLOSE_NOVA_TABS = "close_nova_tabs"

    # Page Understanding & Extraction
    READ_CURRENT_PAGE = "read_current_page"
    SUMMARIZE_CURRENT_PAGE = "summarize_current_page"
    GET_PAGE_TEXT = "get_page_text"
    EXPLAIN_PAGE = "explain_page"

    # Scrolling & History
    SCROLL_DOWN = "scroll_down"
    SCROLL_UP = "scroll_up"
    SCROLL_TO_TOP = "scroll_to_top"
    SCROLL_TO_BOTTOM = "scroll_to_bottom"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"

    # Web, Media & Site Navigation
    OPEN_WEBSITE = "open_website"
    SEARCH_CURRENT_SITE = "search_current_site"
    SEARCH_WEBSITE = "search_website"
    SEARCH_WEB = "search_web"
    RESEARCH_TOPIC = "research_topic"
    PLAY_MEDIA = "play_media"
    WATCH_SHORTS = "watch_shorts"
    START_AUTO_SHORTS = "start_auto_shorts"
    STOP_AUTO_SHORTS = "stop_auto_shorts"
    OPEN_RESULT = "open_result"
    COMPARE_PRODUCTS = "compare_products"

    # Desktop & Filesystem Control
    # Desktop, Camera & Filesystem Control
    LAUNCH_APP = "launch_app"
    CLOSE_APP = "close_app"
    OPEN_FOLDER = "open_folder"
    FIND_ITEM = "find_item"
    OPEN_FILE = "open_file"
    RENAME_ITEM = "rename_item"
    CREATE_DESKTOP_FOLDER = "create_desktop_folder"
    CREATE_DESKTOP_FILE = "create_desktop_file"
    CREATE_PROJECT_STRUCTURE = "create_project_structure"
    WRITE_CODE_FILE = "write_code_file"
    CREATE_CODE_PROJECT = "create_code_project"
    GENERATE_AND_WRITE_DOCUMENT = "generate_and_write_document"
    DELETE_ITEM = "delete_item"
    OPEN_CAMERA = "open_camera"
    TAKE_PHOTO = "take_photo"

    # macOS System, Hardware & Clipboard Control
    CONTROL_VOLUME = "control_volume"
    CONTROL_BRIGHTNESS = "control_brightness"
    CONTROL_WIFI = "control_wifi"
    CONTROL_BLUETOOTH = "control_bluetooth"
    GET_CLIPBOARD = "get_clipboard"
    SET_CLIPBOARD = "set_clipboard"
    CLEAR_CLIPBOARD = "clear_clipboard"
    LOCK_SCREEN = "lock_screen"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CANCEL_ACTION = "cancel_action"
    CONFIRM_ACTION = "confirm_action"
    DENY_ACTION = "deny_action"

    # Screen & Visual Awareness & Smart UI Control
    SCREEN_CAPTURE = "screen.capture"
    WHAT_AM_I_LOOKING_AT = "what_am_i_looking_at"
    START_SCREEN_RECORDING = "start_screen_recording"
    STOP_SCREEN_RECORDING = "stop_screen_recording"
    CLICK_UI_ELEMENT = "click_ui_element"
    TYPE_UI_TEXT = "type_ui_text"
    CLOSE_POPUP = "close_popup"
    SCROLL_UNTIL_VISIBLE = "scroll_until_visible"
    EXPLAIN_SCREEN_ERROR = "explain_screen_error"

    # Reminders & Scheduling
    REMINDER_REQUEST = "reminder_request"
    CALENDAR_REQUEST = "calendar_request"

    # Multi-Step Autonomous Goal Planning (Task Agent V3)
    AUTONOMOUS_TASK = "autonomous_task"

    # General Conversation (Fallback to LLM chat turn)
    GENERAL_CONVERSATION = "general_conversation"


class IntentConfidence(str, Enum):
    """Categorical confidence scores."""
    HIGH = "high"        # >= 0.85 (Direct execution)
    MEDIUM = "medium"    # 0.50 - 0.84 (AI Fallback / verification)
    LOW = "low"          # < 0.50 (Clarification)


class StructuredAction(BaseModel):
    """Standardized structured action object produced by the intent engine."""

    intent: CanonicalIntent
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    raw_input: str = ""
    normalized_input: str = ""
    requires_clarification: bool = False
    clarification_prompt: str | None = None

    @property
    def confidence_level(self) -> IntentConfidence:
        if self.confidence >= 0.85:
            return IntentConfidence.HIGH
        if self.confidence >= 0.50:
            return IntentConfidence.MEDIUM
        return IntentConfidence.LOW
