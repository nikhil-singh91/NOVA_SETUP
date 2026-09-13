"""Transient short-term interaction context and semantic reference resolver for NOVA.

Maintains bounded recent interaction history across turns (not long-term memory)
and deterministically resolves deictic references ('this', 'that', 'this new tab',
'that window', 'the second result', 'here') by combining recent actions, real OS state,
and real-time screen perception (NOVA Eyes).
"""

from __future__ import annotations

import collections
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logger import get_logger
from intent.models import CanonicalIntent
from media.models import ShortTermMusicContext

logger = get_logger(__name__)


@dataclass
class ResolvedEntity:
    """Outcome of resolving a natural reference against context and screen state."""

    resolved: bool
    reference_term: str
    target_type: str  # "browser_tab", "browser_window", "application", "file", "directory", "ui_element", "search_result", "unknown"
    target_value: Any = None  # e.g., dict of tab info, app name, Path, or element
    source: str = "unresolved"  # "screen_state", "real_os_state", "recent_context", "unresolved"
    description: str = ""
    confidence: float = 0.0

    @property
    def entity_type(self) -> str:
        if "tab" in self.target_type:
            return "tab"
        if "app" in self.target_type:
            return "app"
        return self.target_type

    @property
    def app_name(self) -> str | None:
        if isinstance(self.target_value, dict):
            return self.target_value.get("browser") or self.target_value.get("app")
        if isinstance(self.target_value, str) and self.target_type == "application":
            return self.target_value
        return None

    @property
    def title(self) -> str | None:
        if isinstance(self.target_value, dict):
            return self.target_value.get("title")
        return None

    @property
    def url(self) -> str | None:
        if isinstance(self.target_value, dict):
            return self.target_value.get("url")
        return None


@dataclass
class InteractionTurn:
    """Structured record of a single completed or active user interaction turn."""

    turn_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_text: str = ""
    intent: CanonicalIntent = CanonicalIntent.GENERAL_CONVERSATION
    domain: str = "conversation"
    target: str | None = None
    action: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    result_status: str = "PLANNED"  # "PLANNED", "EXECUTED", "VERIFIED", "FAILED"
    result_message: str = ""
    resulting_state: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()

    @property
    def user_input(self) -> str:
        return self.user_text


class RecentInteractionContext:
    """Bounded, thread-safe short-term interaction context spanning recent turns.

    Retains transient state such as:
    - Active and last created browser tabs
    - Active application and window
    - Last executed action and verified outcome
    - Last search query and search results
    - Last referenced or selected elements

    Ensures that real verified computer state takes precedence over stale assumptions.
    """

    MAX_HISTORY: int = 10

    def __init__(self, max_turns: int = 10) -> None:
        self.MAX_HISTORY: int = max_turns
        self._lock = threading.RLock()
        self._history: collections.deque[InteractionTurn] = collections.deque(maxlen=self.MAX_HISTORY)

        # Current Observed Reality (kept fresh by Eyes and OS observers)
        self.current_application: str | None = None
        self.current_window: str | None = None
        self.current_browser: str | None = None
        self.current_tab: dict[str, Any] | None = None  # {"index": int, "title": str, "url": str, "browser": str}
        self.current_url: str | None = None
        self.current_page_title: str | None = None

        # Most Recent Verified Actions & Artifacts
        self.last_action: str | None = None
        self.last_action_target: str | None = None
        self.last_action_status: str | None = None  # "VERIFIED", "SUCCESS", "FAILED"
        self.last_opened_tab: dict[str, Any] | None = None
        self.last_search_query: str | None = None
        self.last_search_results: list[dict[str, Any]] = []
        self.last_created_path: Path | None = None
        self.last_opened_app: str | None = None
        self.last_clicked_element: str | None = None
        self.is_shorts_active: bool = False
        self.is_auto_scroll_active: bool = False
        self.music_context: ShortTermMusicContext = ShortTermMusicContext()
        self.last_update_time: float = datetime.now(timezone.utc).timestamp()

    @property
    def is_current_page_shorts(self) -> bool:
        url = (self.current_url or "").lower()
        title = (self.current_page_title or "").lower()
        last_act = (self.last_action or "").lower()
        return "/shorts" in url or "shorts" in title or "shorts" in last_act

    @property
    def turns(self) -> list[InteractionTurn]:
        with self._lock:
            return list(self._history)

    @property
    def active_browser(self) -> str | None:
        return self.current_browser

    @property
    def active_tab_id(self) -> int | None:
        if self.current_tab:
            return self.current_tab.get("index")
        return None

    @property
    def last_opened_url(self) -> str | None:
        return self.current_url

    @property
    def is_current_tab_new(self) -> bool:
        if self.last_opened_tab and self.current_tab:
            return (
                self.current_tab.get("index") == self.last_opened_tab.get("index")
                or "newtab" in (self.current_url or "")
            )
        return "newtab" in (self.current_url or "")

    def add_turn(
        self,
        user_input: str,
        intent: str | CanonicalIntent,
        action: str | None = None,
        action_result: str = "",
        success: bool = True,
        target_app: str | None = None,
        target_browser: str | None = None,
        current_url: str | None = None,
        current_title: str | None = None,
        last_search_query: str | None = None,
        turn_id: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> InteractionTurn:
        """Convenience method to append a completed turn and update current state."""
        canonical_intent = (
            intent
            if isinstance(intent, CanonicalIntent)
            else (
                CanonicalIntent(intent)
                if intent in [ci.value for ci in CanonicalIntent]
                else CanonicalIntent.GENERAL_CONVERSATION
            )
        )
        status = "VERIFIED" if success else "FAILED"
        res_state: dict[str, Any] = {}
        if target_app:
            res_state["app"] = target_app
            self.current_application = target_app
        if target_browser:
            self.current_browser = target_browser
        if current_url:
            res_state["url"] = current_url
            self.current_url = current_url
        if current_title:
            res_state["title"] = current_title
            self.current_page_title = current_title
        if last_search_query:
            res_state["query"] = last_search_query
            self.last_search_query = last_search_query

        tid = turn_id or f"turn_{int(time.time() * 1000)}"
        return self.record_turn(
            turn_id=tid,
            user_text=user_input,
            intent=canonical_intent,
            action=action,
            result_status=status,
            result_message=action_result,
            resulting_state=res_state,
            parameters=parameters,
        )

    def update_browser_state(
        self,
        browser_name: str | None = None,
        tab_id: int | None = None,
        window_id: int | str | None = None,
        url: str | None = None,
        title: str | None = None,
        is_new_tab: bool = False,
    ) -> None:
        """Update active browser state with explicit tab or navigation details."""
        with self._lock:
            if browser_name:
                self.current_browser = browser_name
                self.current_application = browser_name
            if url:
                self.current_url = url
            if title:
                self.current_page_title = title
            if tab_id is not None or url is not None or title is not None:
                tab_info = {
                    "browser": self.current_browser or "Google Chrome",
                    "index": tab_id if tab_id is not None else (self.current_tab or {}).get("index", 1),
                    "title": title or (self.current_tab or {}).get("title", ""),
                    "url": url or (self.current_tab or {}).get("url", ""),
                    "window": str(window_id or ""),
                }
                self.current_tab = tab_info
                if is_new_tab:
                    self.last_opened_tab = tab_info
            self.last_update_time = datetime.now(timezone.utc).timestamp()

    def resolve_reference(
        self,
        reference_text: str,
        screen_state: Any | None = None,
    ) -> ResolvedEntity:
        """Resolve a natural reference text using this context and optional screen state."""
        return ContextualReferenceResolver.resolve_reference(
            reference_text, self, screen_state=screen_state
        )

    def record_turn(
        self,
        turn_id: str,
        user_text: str,
        intent: CanonicalIntent,
        domain: str = "general",
        target: str | None = None,
        action: str | None = None,
        parameters: dict[str, Any] | None = None,
        result_status: str = "VERIFIED",
        result_message: str = "",
        resulting_state: dict[str, Any] | None = None,
    ) -> InteractionTurn:
        """Record a completed interaction turn into the bounded history."""
        with self._lock:
            turn = InteractionTurn(
                turn_id=turn_id,
                timestamp=datetime.now(timezone.utc),
                user_text=user_text,
                intent=intent,
                domain=domain,
                target=target,
                action=action,
                parameters=parameters or {},
                result_status=result_status,
                result_message=result_message,
                resulting_state=resulting_state or {},
            )
            self._history.append(turn)

            self.last_action = action or intent.value
            self.last_action_target = target
            self.last_action_status = result_status
            self.last_update_time = datetime.now(timezone.utc).timestamp()

            if resulting_state:
                if "tab" in resulting_state:
                    self.last_opened_tab = dict(resulting_state["tab"])
                    self.current_tab = dict(resulting_state["tab"])
                if "app" in resulting_state:
                    self.current_application = resulting_state["app"]
                    self.last_opened_app = resulting_state["app"]
                if "url" in resulting_state:
                    self.current_url = resulting_state["url"]
                if "title" in resulting_state:
                    self.current_page_title = resulting_state["title"]
                if "query" in resulting_state:
                    self.last_search_query = resulting_state["query"]

            logger.debug(
                "Recorded interaction turn '%s': intent=%s, action=%s, status=%s",
                turn_id,
                intent.value,
                action,
                result_status,
            )
            return turn

    def update_from_observation(
        self,
        app: str | None = None,
        win: str | None = None,
        browser: str | None = None,
        tab_index: int | None = None,
        tab_title: str | None = None,
        url: str | None = None,
    ) -> None:
        """Update current computer reality from real-time OS or Eyes observation."""
        with self._lock:
            if app:
                self.current_application = app
                if any(b in app.lower() for b in ["chrome", "safari", "brave", "edge", "arc", "firefox"]):
                    self.current_browser = app
            if win is not None:
                self.current_window = win
            if browser:
                self.current_browser = browser
            if url is not None:
                self.current_url = url
            if tab_title is not None:
                self.current_page_title = tab_title

            if tab_index is not None or url is not None or tab_title is not None:
                cur = self.current_tab or {}
                self.current_tab = {
                    "index": tab_index if tab_index is not None else cur.get("index", 1),
                    "title": tab_title if tab_title is not None else cur.get("title", ""),
                    "url": url if url is not None else cur.get("url", ""),
                    "browser": self.current_browser or cur.get("browser", "Google Chrome"),
                }
            self.last_update_time = datetime.now(timezone.utc).timestamp()

    def record_tab_opened(
        self,
        browser: str,
        index: int,
        title: str = "New Tab",
        url: str = "chrome://newtab/",
        window: str = "",
    ) -> None:
        """Explicitly record a verified browser tab creation."""
        with self._lock:
            tab_info = {
                "browser": browser,
                "index": index,
                "title": title,
                "url": url,
                "window": window,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.last_opened_tab = tab_info
            self.current_tab = tab_info
            self.current_browser = browser
            self.current_application = browser
            self.current_url = url
            self.current_page_title = title
            self.last_action = "OPEN_NEW_TAB"
            self.last_action_status = "VERIFIED"
            self.last_update_time = datetime.now(timezone.utc).timestamp()
            logger.info("RecentInteractionContext: Recorded newly opened tab: %s", tab_info)

    def record_web_research(
        self,
        query: str,
        sources: list[dict[str, Any]],
        summary: str = "",
        mode: str = "search",
    ) -> None:
        """Record live web intelligence outcome into transient task context.

        Stores structured research items so subsequent queries (e.g.
        'which one has the best camera?', 'compare the first and third',
        'open the second one') can resolve against the current task context.
        """
        with self._lock:
            self.last_search_query = query
            self.last_search_results = list(sources)
            self.last_action = "LIVE_WEB_RESEARCH"
            self.last_action_target = query
            self.last_action_status = "VERIFIED"
            self.last_update_time = datetime.now(timezone.utc).timestamp()
            logger.info(
                "RecentInteractionContext: Recorded %d live web sources for '%s' (mode=%s)",
                len(sources),
                query,
                mode,
            )

    def is_fresh(self, max_age_seconds: float = 120.0) -> bool:
        """Check whether recent action state is sufficiently fresh."""
        with self._lock:
            elapsed = datetime.now(timezone.utc).timestamp() - self.last_update_time
            return elapsed <= max_age_seconds

    def get_last_turn(self) -> InteractionTurn | None:
        """Retrieve the most recently completed interaction turn."""
        with self._lock:
            return self._history[-1] if self._history else None

    def get_turns(self) -> list[InteractionTurn]:
        """Return shallow copy of all turns in bounded history."""
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        """Clear transient interaction context."""
        with self._lock:
            self._history.clear()
            self.current_tab = None
            self.last_opened_tab = None
            self.last_action = None
            self.last_action_target = None
            self.last_action_status = None
            self.last_search_query = None
            self.last_search_results.clear()


class ContextualReferenceResolver:
    """Generic semantic reference resolver for natural multi-turn commands.

    Resolves:
    - 'this', 'that', 'it', 'there', 'here'
    - 'this tab', 'that tab', 'this new tab', 'the new tab', 'the tab i just opened', 'current tab'
    - 'this window', 'that window', 'the chrome window'
    - 'this app', 'that app', 'the app'
    - 'the second result', 'the first one', 'the last result', 'open that one'
    """

    def __init__(self, context: RecentInteractionContext | None = None) -> None:
        self.context = context

    def resolve(
        self,
        reference_text: str,
        screen_state: Any | None = None,
    ) -> ResolvedEntity:
        """Instance resolution helper defaulting to bound interaction context."""
        return self.resolve_reference(reference_text, self.context, screen_state=screen_state)

    @classmethod
    def resolve_reference(
        cls,
        reference_text: str,
        context: RecentInteractionContext | None,
        screen_state: Any | None = None,  # ScreenState from core.eyes.state
    ) -> ResolvedEntity:
        """Resolve a natural reference text to a concrete system or browser entity."""
        raw_ref = reference_text.lower().strip()
        ref = re.sub(r"^(?:in|on|at|to)\s+", "", raw_ref).replace("_", " ").strip()

        active_app = getattr(screen_state, "active_application", None) or getattr(screen_state, "active_app", None)
        active_win = getattr(screen_state, "active_window", None) or getattr(screen_state, "active_window_title", None)

        # ---------------------------------------------------------------------
        # 1. BROWSER TAB REFERENCES:
        # 'this new tab', 'the new tab', 'this tab', 'that tab', 'current tab',
        # 'the tab i just opened', 'what i just opened'
        # ---------------------------------------------------------------------
        tab_indicators = [
            "this new tab", "that new tab", "the new tab", "new tab",
            "this tab", "that tab", "the tab", "current tab",
            "the tab i just opened", "tab i just opened", "the one i just opened",
            "what i just opened", "newly opened tab",
        ]
        if any(ref == t or ref.startswith(f"{t} ") or ref.endswith(f" {t}") for t in tab_indicators) or ref in ("here", "this page", "current page"):
            # Priority 1: Current Screen Reality (frontmost browser & tab)
            if screen_state and active_app:
                app_l = active_app.lower()
                if any(b in app_l for b in ["chrome", "safari", "brave", "edge", "arc"]):
                    # Screen state shows browser is currently active
                    tab_val = {
                        "browser": active_app,
                        "window": active_win or "",
                        "index": context.current_tab.get("index", 1) if context and context.current_tab else 1,
                        "title": active_win or (context.current_page_title if context else ""),
                        "url": context.current_url or "chrome://newtab/" if context else "chrome://newtab/",
                    }
                    return ResolvedEntity(
                        resolved=True,
                        reference_term=raw_ref,
                        target_type="browser_tab",
                        target_value=tab_val,
                        source="screen_state",
                        description=f"Active browser tab in {active_app}",
                        confidence=0.98,
                    )

            # Priority 2: Recent Verified Interaction Context
            if context and context.is_fresh(max_age_seconds=180):
                if context.last_opened_tab:
                    return ResolvedEntity(
                        resolved=True,
                        reference_term=raw_ref,
                        target_type="browser_tab",
                        target_value=dict(context.last_opened_tab),
                        source="recent_context",
                        description=f"Recently opened tab #{context.last_opened_tab.get('index', 1)} in {context.last_opened_tab.get('browser', 'Browser')}",
                        confidence=0.95,
                    )
                if context.current_tab:
                    return ResolvedEntity(
                        resolved=True,
                        reference_term=raw_ref,
                        target_type="browser_tab",
                        target_value=dict(context.current_tab),
                        source="recent_context",
                        description=f"Current tab #{context.current_tab.get('index', 1)} in {context.current_tab.get('browser', 'Browser')}",
                        confidence=0.90,
                    )
                if context.current_browser:
                    return ResolvedEntity(
                        resolved=True,
                        reference_term=raw_ref,
                        target_type="browser_tab",
                        target_value={"browser": context.current_browser, "index": 1, "url": context.current_url or "chrome://newtab/"},
                        source="recent_context",
                        description=f"Active tab in {context.current_browser}",
                        confidence=0.85,
                    )

        # ---------------------------------------------------------------------
        # 2. APPLICATION REFERENCES:
        # 'this app', 'that app', 'the app', 'this window', 'that window'
        # ---------------------------------------------------------------------
        if ref in ("this app", "that app", "the app", "this window", "that window", "the window", "here", "it"):
            # Priority 1: Screen State
            if screen_state and active_app:
                return ResolvedEntity(
                    resolved=True,
                    reference_term=raw_ref,
                    target_type="application",
                    target_value={"app": active_app, "window": active_win},
                    source="screen_state",
                    description=f"Frontmost application '{active_app}'",
                    confidence=0.95,
                )
            # Priority 2: Context
            if context and context.current_application:
                return ResolvedEntity(
                    resolved=True,
                    reference_term=raw_ref,
                    target_type="application",
                    target_value={"app": context.current_application, "window": context.current_window},
                    source="recent_context",
                    description=f"Recent active application '{context.current_application}'",
                    confidence=0.90,
                )

        # ---------------------------------------------------------------------
        # 3. SEARCH RESULT & ORDINAL REFERENCES:
        # 'the second result', 'the first one', 'open that one', 'the last result'
        # ---------------------------------------------------------------------
        m_ordinal = re.search(
            r"(?:the\s+)?(first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)(?:\s+(?:one|result|link|item|phone|laptop|product|article|source|website|option|recommendation|model))?",
            ref,
        )
        if m_ordinal:
            ord_word = m_ordinal.group(1).lower()
            ord_map = {
                "first": 1, "1st": 1,
                "second": 2, "2nd": 2,
                "third": 3, "3rd": 3,
                "fourth": 4, "4th": 4,
                "fifth": 5, "5th": 5,
                "last": -1,
            }
            target_idx = ord_map.get(ord_word, 1)
            # Check context search results
            if context and context.last_search_results:
                idx = len(context.last_search_results) if target_idx == -1 else target_idx
                if 1 <= idx <= len(context.last_search_results):
                    res_item = context.last_search_results[idx - 1]
                    return ResolvedEntity(
                        resolved=True,
                        reference_term=raw_ref,
                        target_type="search_result",
                        target_value={"index": idx, "url": res_item.get("url"), "title": res_item.get("title")},
                        source="recent_context",
                        description=f"Search result #{idx}: {res_item.get('title', '')}",
                        confidence=0.95,
                    )
            # Also fallback to screen state links if available
            if screen_state and hasattr(screen_state, "links") and screen_state.links:
                idx = len(screen_state.links) if target_idx == -1 else target_idx
                if 1 <= idx <= len(screen_state.links):
                    elem = screen_state.links[idx - 1]
                    return ResolvedEntity(
                        resolved=True,
                        reference_term=raw_ref,
                        target_type="ui_element",
                        target_value={"index": idx, "element": elem, "label": elem.label},
                        source="screen_state",
                        description=f"On-screen link #{idx}: {elem.label}",
                        confidence=0.90,
                    )

        # ---------------------------------------------------------------------
        # 3B. MUSIC FOLLOW-UP REFERENCES:
        # 'another one', 'another song', 'one more', 'something else', 'play another', 'same type', 'something similar'
        # ---------------------------------------------------------------------
        if ref in (
            "another one", "another song", "one more", "something else", "play another",
            "same type", "something similar", "this artist", "that artist", "this song",
            "another song like that", "next song", "next one",
        ):
            if context and (context.music_context.is_fresh() or (context.current_url and "youtube.com/watch" in context.current_url)):
                pref = context.music_context.preference
                pref_desc = f"Artist: {pref.artist}" if pref.artist else (f"Genre: {pref.genre}" if pref.genre else "Recent music preference")
                return ResolvedEntity(
                    resolved=True,
                    reference_term=raw_ref,
                    target_type="music_track",
                    target_value={"preference": pref.model_dump(), "last_track": context.music_context.current_track.model_dump() if context.music_context.current_track else None},
                    source="recent_context",
                    description=f"Follow-up music request for {pref_desc}",
                    confidence=0.95,
                )

        # ---------------------------------------------------------------------
        # 4. PRONOUNS 'it', 'that', 'there'
        # ---------------------------------------------------------------------
        if ref in ("it", "that", "there", "that one", "this one"):
            # If recent action created a file/folder
            if context and context.last_created_path and context.last_created_path.exists():
                return ResolvedEntity(
                    resolved=True,
                    reference_term=raw_ref,
                    target_type="directory" if context.last_created_path.is_dir() else "file",
                    target_value=context.last_created_path,
                    source="recent_context",
                    description=f"Recently created item '{context.last_created_path.name}'",
                    confidence=0.88,
                )
            # If a browser tab was just opened
            if context and context.last_opened_tab and context.is_fresh(60):
                return ResolvedEntity(
                    resolved=True,
                    reference_term=raw_ref,
                    target_type="browser_tab",
                    target_value=dict(context.last_opened_tab),
                    source="recent_context",
                    description=f"Recently opened tab #{context.last_opened_tab.get('index', 1)}",
                    confidence=0.85,
                )
            # Frontmost window / app
            if screen_state and screen_state.active_application:
                return ResolvedEntity(
                    resolved=True,
                    reference_term=raw_ref,
                    target_type="application",
                    target_value={"app": screen_state.active_application, "window": screen_state.active_window},
                    source="screen_state",
                    description=f"Frontmost application '{screen_state.active_application}'",
                    confidence=0.80,
                )

        return ResolvedEntity(
            resolved=False,
            reference_term=raw_ref,
            target_type="unknown",
            target_value=None,
            source="unresolved",
            description=f"Could not resolve reference '{reference_text}'.",
            confidence=0.0,
        )


# Global singleton instance of RecentInteractionContext
recent_interaction_context = RecentInteractionContext()
