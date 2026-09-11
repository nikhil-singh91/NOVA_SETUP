"""Canonical Environment Context, Real-Time macOS Observer, and Context Resolver for NOVA.

Provides the single source of truth for NOVA's environment awareness (EYES),
observing frontmost applications, browser tabs, Finder selections, and recent actions,
and deterministically resolving natural references ("this", "that", "it", "here").
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EnvironmentContext:
    """Canonical representation of the user's current computing environment."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Real macOS State
    active_application: str | None = None
    active_window: str | None = None
    active_browser: str | None = None
    active_tab_index: int | None = None
    active_tab_count: int | None = None
    current_url: str | None = None
    current_domain: str | None = None
    current_page_title: str | None = None

    # Filesystem State
    current_folder: Path | None = None
    selected_file_or_folder: Path | None = None
    selected_files: list[Path] = field(default_factory=list)
    selected_text_if_available: str | None = None

    # Tasks and Media
    active_task: str | None = None
    active_screen_recording: bool = False
    recording_file_path: str | None = None

    # Action Tracking & History
    last_action: str | None = None
    last_action_result: Any = None
    last_created_path: Path | None = None
    last_opened_target: str | None = None

    # Pending Confirmation (e.g., delete confirmation, dangerous actions)
    pending_confirmation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert context snapshot into serializable dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "active_application": self.active_application,
            "active_window": self.active_window,
            "active_browser": self.active_browser,
            "active_tab_index": self.active_tab_index,
            "current_url": self.current_url,
            "current_domain": self.current_domain,
            "current_page_title": self.current_page_title,
            "current_folder": str(self.current_folder) if self.current_folder else None,
            "selected_file_or_folder": str(self.selected_file_or_folder) if self.selected_file_or_folder else None,
            "selected_files": [str(p) for p in self.selected_files],
            "active_task": self.active_task,
            "active_screen_recording": self.active_screen_recording,
            "recording_file_path": self.recording_file_path,
            "last_action": self.last_action,
            "last_created_path": str(self.last_created_path) if self.last_created_path else None,
            "last_opened_target": self.last_opened_target,
            "has_pending_confirmation": self.pending_confirmation is not None,
        }


def log_environment_debug(stage: str, **kwargs: Any) -> None:
    """Log structured environment diagnostic data when debug mode is enabled."""
    is_debug = bool(
        getattr(settings, "nova_environment_debug", False)
        or os.getenv("NOVA_ENVIRONMENT_DEBUG", "").lower() in ("true", "1")
    )
    if not is_debug:
        return

    print("\n🌐 ========================================")
    print(f"🔍 [ENVIRONMENT DEBUG] :: {stage.upper()}")
    for k, v in kwargs.items():
        # Mask sensitive keys if any
        if any(s in k.lower() for s in ["key", "token", "password", "auth"]):
            v = "[REDACTED]"
        print(f"  {k.upper():<20} {v}")
    print("🌐 ========================================\n")


class EnvironmentObserver:
    """Observes the real macOS environment state on-demand via structured system APIs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_context: EnvironmentContext = EnvironmentContext()
        self._last_refresh_time: float = 0.0
        self._cache_ttl_seconds: float = 0.5

    def _run_applescript(self, script: str, timeout: float = 2.0) -> tuple[bool, str]:
        """Execute an AppleScript snippet with strict timeout."""
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode == 0:
                return True, proc.stdout.strip()
            return False, proc.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "AppleScript execution timed out"
        except Exception as exc:
            return False, str(exc)

    def refresh(self, force: bool = False) -> EnvironmentContext:
        """Capture real-time OS state: active application, window title, browser tab, Finder selection."""
        now = datetime.now(timezone.utc)
        with self._lock:
            # Check cache TTL unless force requested
            if not force and (datetime.now().timestamp() - self._last_refresh_time) < self._cache_ttl_seconds:
                return self._last_context

            ctx = EnvironmentContext(
                timestamp=now,
                active_screen_recording=self._last_context.active_screen_recording,
                recording_file_path=self._last_context.recording_file_path,
                active_task=self._last_context.active_task,
                last_action=self._last_context.last_action,
                last_action_result=self._last_context.last_action_result,
                last_created_path=self._last_context.last_created_path,
                last_opened_target=self._last_context.last_opened_target,
                pending_confirmation=self._last_context.pending_confirmation,
            )

            # 1. Query Frontmost Application & Window Title
            app_script = """
            tell application "System Events"
                try
                    set frontApp to first application process whose frontmost is true
                    set appName to name of frontApp
                    set winTitle to ""
                    try
                        set winTitle to name of front window of frontApp
                    end try
                    return appName & "|||" & winTitle
                on error
                    return "UNKNOWN|||"
                end try
            end tell
            """
            success, out = self._run_applescript(app_script, timeout=1.5)
            if success and "|||" in out:
                parts = out.split("|||", 1)
                ctx.active_application = parts[0].strip() or None
                ctx.active_window = parts[1].strip() or None

            # 2. If Active Application is a Web Browser (Chrome, Safari, Brave, Edge, Arc)
            app_lower = (ctx.active_application or "").lower()
            if any(b in app_lower for b in ["chrome", "safari", "brave", "edge", "arc"]):
                ctx.active_browser = ctx.active_application
                self._populate_browser_state(ctx)

            # 3. If Active Application is Finder or File Manager
            if "finder" in app_lower:
                self._populate_finder_state(ctx)

            self._last_context = ctx
            self._last_refresh_time = datetime.now().timestamp()

            log_environment_debug(
                "REFRESH",
                app=ctx.active_application,
                window=ctx.active_window,
                browser_url=ctx.current_url,
                domain=ctx.current_domain,
                folder=str(ctx.current_folder) if ctx.current_folder else None,
                selection=str(ctx.selected_file_or_folder) if ctx.selected_file_or_folder else None,
                recording=ctx.active_screen_recording,
            )

            return ctx

    def _populate_browser_state(self, ctx: EnvironmentContext) -> None:
        """Query active tab URL and title from the frontmost browser window."""
        browser_name = ctx.active_browser or "Google Chrome"
        if "safari" in browser_name.lower():
            script = """
            tell application "Safari"
                try
                    if (count of windows) > 0 then
                        set curIdx to index of current tab of front window
                        set totalTabs to count of tabs of front window
                        set curTitle to name of current tab of front window
                        set curURL to URL of current tab of front window
                        return (curIdx as text) & "|||" & (totalTabs as text) & "|||" & curTitle & "|||" & curURL
                    end if
                end try
                return "NO_WINDOW"
            end tell
            """
        else:
            script = f"""
            tell application "{browser_name}"
                try
                    if (count of windows) > 0 then
                        set curIdx to active tab index of front window
                        set totalTabs to count of tabs of front window
                        set curTitle to title of active tab of front window
                        set curURL to URL of active tab of front window
                        return (curIdx as text) & "|||" & (totalTabs as text) & "|||" & curTitle & "|||" & curURL
                    end if
                end try
                return "NO_WINDOW"
            end tell
            """

        success, out = self._run_applescript(script, timeout=1.5)
        if success and "|||" in out:
            parts = out.split("|||", 3)
            try:
                ctx.active_tab_index = int(parts[0])
            except ValueError:
                ctx.active_tab_index = 1
            try:
                ctx.active_tab_count = int(parts[1])
            except ValueError:
                ctx.active_tab_count = 1

            ctx.current_page_title = parts[2].strip() if len(parts) > 2 else None
            raw_url = parts[3].strip() if len(parts) > 3 else None
            ctx.current_url = raw_url

            if raw_url:
                try:
                    parsed = urllib.parse.urlparse(raw_url)
                    ctx.current_domain = parsed.netloc.lower()
                except Exception:
                    ctx.current_domain = None

    def _populate_finder_state(self, ctx: EnvironmentContext) -> None:
        """Query selected files or active directory in Finder."""
        script = """
        tell application "Finder"
            try
                set sel to selection
                if (count of sel) > 0 then
                    set posixList to {}
                    repeat with itemRef in sel
                        set end of posixList to POSIX path of (itemRef as alias)
                    end repeat
                    set AppleScript's text item delimiters to ":::"
                    return "SELECTED:::" & (posixList as text)
                end if
            end try
            try
                set curFolder to (target of front window as alias)
                return "FOLDER:::" & POSIX path of curFolder
            end try
            return "NONE"
        end tell
        """
        success, out = self._run_applescript(script, timeout=1.5)
        if success and out:
            if out.startswith("SELECTED:::"):
                raw_paths = out[len("SELECTED:::"):].split(":::")
                file_paths = [Path(p.strip()) for p in raw_paths if p.strip()]
                ctx.selected_files = file_paths
                if file_paths:
                    ctx.selected_file_or_folder = file_paths[0]
                    ctx.current_folder = file_paths[0].parent
            elif out.startswith("FOLDER:::"):
                raw_folder = out[len("FOLDER:::"):].strip()
                if raw_folder:
                    ctx.current_folder = Path(raw_folder)
                    ctx.selected_file_or_folder = None
                    ctx.selected_files = []

    def get_context(self) -> EnvironmentContext:
        """Get the current environment context."""
        return self._last_context

    def update_action_context(
        self,
        action: str,
        result: Any = None,
        created_path: Path | None = None,
        opened_target: str | None = None,
    ) -> None:
        """Record the outcome of the most recent NOVA action."""
        with self._lock:
            self._last_context.last_action = action
            self._last_context.last_action_result = result
            if created_path:
                self._last_context.last_created_path = created_path
            if opened_target:
                self._last_context.last_opened_target = opened_target


class ContextResolver:
    """Deterministically resolves natural pronouns and deictic references.

    Priority:
      1. REAL CURRENT STATE (active Finder selection, active browser URL/tab, frontmost window)
      2. CURRENT APP/BROWSER CONTEXT (active project directory, current open website)
      3. RECENT NOVA CONTEXT (last created path, last opened target, last action result)
    """

    @classmethod
    def resolve_target(
        cls,
        reference_term: str,
        context: EnvironmentContext,
        target_type: str = "any",  # "file", "folder", "page", "site", "item", "any"
    ) -> dict[str, Any]:
        """Resolve a natural reference like 'this', 'that', 'it', 'here', 'current page'.

        Returns a dictionary containing:
          - resolved: bool
          - target: Any (Path, str URL, domain, or name)
          - source: str ("real_current_state", "app_context", "recent_nova_context", "unresolved")
          - description: str
        """
        ref = reference_term.lower().strip()

        log_environment_debug(
            "RESOLVE_TARGET",
            reference=ref,
            target_type=target_type,
            app=context.active_application,
            url=context.current_url,
            selected=str(context.selected_file_or_folder) if context.selected_file_or_folder else None,
            last_created=str(context.last_created_path) if context.last_created_path else None,
        )

        # -------------------------------------------------------------
        # 1. BROWSER & WEBPAGE REFERENCES ("here", "this page", "this site", "on this page")
        # -------------------------------------------------------------
        if ref in ("here", "this page", "current page", "this site", "current site", "the page", "the site"):
            if context.current_url:
                domain = context.current_domain or ""
                # Extract clean site key (e.g. flipkart from flipkart.com)
                site_key = domain.replace("www.", "").split(".")[0] if domain else ""
                return {
                    "resolved": True,
                    "target": context.current_url,
                    "site_key": site_key,
                    "domain": domain,
                    "title": context.current_page_title or "Current Page",
                    "source": "real_current_state",
                    "type": "browser_page",
                    "description": f"Current webpage ({context.current_page_title or domain})",
                }

        # -------------------------------------------------------------
        # 2. FILE & FOLDER REFERENCES ("this", "that", "it", "this file", "this folder", "selected item")
        # -------------------------------------------------------------
        # Tier 1: Real Current State (Finder selection)
        if context.selected_file_or_folder and context.selected_file_or_folder.exists():
            target_path = context.selected_file_or_folder
            is_dir = target_path.is_dir()
            if target_type == "folder" and not is_dir:
                # If folder explicitly asked, check parent
                target_path = target_path.parent
                is_dir = True

            return {
                "resolved": True,
                "target": target_path,
                "source": "real_current_state",
                "type": "directory" if is_dir else "file",
                "description": f"{'Folder' if is_dir else 'File'} '{target_path.name}' at {target_path}",
            }

        # Tier 1B: Real Current State (Finder open directory)
        if context.current_folder and context.current_folder.exists():
            if target_type in ("folder", "directory", "any") or ref in ("here", "this folder", "current folder"):
                return {
                    "resolved": True,
                    "target": context.current_folder,
                    "source": "real_current_state",
                    "type": "directory",
                    "description": f"Current directory '{context.current_folder.name}' at {context.current_folder}",
                }

        # Tier 2: Real Current State (Active Browser if asking for "this" / "that")
        if context.current_url and target_type in ("page", "site", "any"):
            domain = context.current_domain or ""
            site_key = domain.replace("www.", "").split(".")[0] if domain else ""
            return {
                "resolved": True,
                "target": context.current_url,
                "site_key": site_key,
                "domain": domain,
                "title": context.current_page_title or domain,
                "source": "real_current_state",
                "type": "browser_page",
                "description": f"Current webpage '{context.current_page_title or domain}'",
            }

        # Tier 3: Recent NOVA Context (last created folder or file)
        if ref in ("it", "that", "the folder i just created", "the file i just created", "created item"):
            if context.last_created_path and context.last_created_path.exists():
                is_dir = context.last_created_path.is_dir()
                return {
                    "resolved": True,
                    "target": context.last_created_path,
                    "source": "recent_nova_context",
                    "type": "directory" if is_dir else "file",
                    "description": f"Recently created {'folder' if is_dir else 'file'} '{context.last_created_path.name}'",
                }

        # Unresolved
        return {
            "resolved": False,
            "target": None,
            "source": "unresolved",
            "type": target_type,
            "description": f"Could not resolve reference '{reference_term}' to an active environment object.",
        }


# Global singleton observer
environment_observer = EnvironmentObserver()
