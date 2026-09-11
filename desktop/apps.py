"""macOS application discovery, alias resolution, launching, and process termination."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from core.logger import get_logger

logger = get_logger(__name__)


class AppLauncher:
    """Discovers installed macOS applications, resolves common aliases, and manages app processes."""

    APP_DIRECTORIES = [
        Path("/Applications"),
        Path("/System/Applications"),
        Path("/System/Applications/Utilities"),
        Path("/System/Library/CoreServices"),
        Path.home() / "Applications",
    ]

    ALIAS_MAP: dict[str, str] = {
        "vs code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "visual studio code": "Visual Studio Code",
        "code editor": "Visual Studio Code",
        "notepad": "TextEdit",
        "text editor": "TextEdit",
        "textedit": "TextEdit",
        "camera": "Photo Booth",
        "webcam": "Photo Booth",
        "photo booth": "Photo Booth",
        "terminal": "Terminal",
        "console": "Terminal",
        "iterm": "iTerm",
        "iterm2": "iTerm",
        "finder": "Finder",
        "file manager": "Finder",
        "spotify": "Spotify",
        "chrome": "Google Chrome",
        "google chrome": "Google Chrome",
        "safari": "Safari",
        "calculator": "Calculator",
        "notes": "Notes",
        "slack": "Slack",
        "notion": "Notion",
        "discord": "Discord",
        "telegram": "Telegram",
        "telegram app": "Telegram",
        "whatsapp": "WhatsApp",
        "whatsapp app": "WhatsApp",
        "cursor": "Cursor",
        "brave": "Brave Browser",
        "brave browser": "Brave Browser",
        "youtube": "YouTube",
        "youtube app": "YouTube",
        "xcode": "Xcode",
        "music": "Music",
        "preview": "Preview",
        "sublime": "Sublime Text",
        "sublime text": "Sublime Text",
        "pycharm": "PyCharm",
        "settings": "System Settings",
        "system settings": "System Settings",
        "preferences": "System Settings",
        "activity monitor": "Activity Monitor",
    }

    @classmethod
    def resolve_app_name(cls, raw_name: str) -> str:
        """Resolve common natural language aliases to canonical macOS application name."""
        clean = raw_name.lower().strip()
        # Clean off trailing or leading "app" or "application"
        clean_no_app = re.sub(r"\b(?:app|application)\b", "", clean).strip()

        if clean in cls.ALIAS_MAP:
            return cls.ALIAS_MAP[clean]
        if clean_no_app in cls.ALIAS_MAP:
            return cls.ALIAS_MAP[clean_no_app]

        for alias, canonical in cls.ALIAS_MAP.items():
            if alias == clean or alias == clean_no_app:
                return canonical

        target = clean_no_app if clean_no_app else clean
        return target.strip().title()

    @classmethod
    def find_matching_apps(cls, app_name: str) -> list[Path]:
        """Search standard macOS application directories and return all matching app bundles."""
        canonical = cls.resolve_app_name(app_name)
        target_bundle = f"{canonical}.app".lower()
        clean_query = app_name.lower().strip()

        exact_matches: list[Path] = []
        partial_matches: list[Path] = []

        for base_dir in cls.APP_DIRECTORIES:
            if not base_dir.exists():
                continue

            try:
                for item in base_dir.iterdir():
                    if not item.is_dir():
                        continue

                    # Direct .app bundle match
                    if item.name.lower() == target_bundle:
                        if item not in exact_matches:
                            exact_matches.append(item)
                    elif item.name.lower().endswith(".app"):
                        item_stem = item.stem.lower()
                        if clean_query and (item_stem == clean_query or clean_query in item_stem):
                            if item not in partial_matches and item not in exact_matches:
                                partial_matches.append(item)
                    else:
                        # Scan immediate subdirectory (e.g. Utilities)
                        try:
                            for sub_item in item.iterdir():
                                if sub_item.is_dir() and sub_item.name.lower() == target_bundle:
                                    if sub_item not in exact_matches:
                                        exact_matches.append(sub_item)
                                elif sub_item.is_dir() and sub_item.name.lower().endswith(".app"):
                                    sub_stem = sub_item.stem.lower()
                                    if clean_query and (sub_stem == clean_query or clean_query in sub_stem):
                                        if sub_item not in partial_matches and sub_item not in exact_matches:
                                            partial_matches.append(sub_item)
                        except Exception:
                            pass
            except Exception:
                pass

        if exact_matches:
            return exact_matches
        return partial_matches

    @classmethod
    def find_installed_app(cls, app_name: str) -> Path | None:
        """Search standard macOS application directories for a single matching app bundle."""
        matches = cls.find_matching_apps(app_name)
        if matches:
            return matches[0]
        return None

    @classmethod
    def is_app_running(cls, canonical_name: str, poll_timeout: float = 1.5) -> bool:
        """Check if an application has an active running process on macOS via NSWorkspace and pgrep.

        Args:
            canonical_name: The resolved macOS application name (e.g. 'Telegram', 'TextEdit').
            poll_timeout: Maximum seconds to wait for application process emergence.

        Returns:
            True if process is verified running, False otherwise.
        """
        c_lower = canonical_name.lower().strip()
        start_t = time.monotonic()

        while True:
            # 1. Check Cocoa NSWorkspace running applications (fastest and most accurate)
            try:
                from AppKit import NSWorkspace
                running = [app.localizedName() for app in NSWorkspace.sharedWorkspace().runningApplications() if app.localizedName()]
                for name in running:
                    if name and (name.lower() == c_lower or c_lower in name.lower() or name.lower() in c_lower):
                        return True
            except Exception as e:
                logger.debug("NSWorkspace check exception: %s", e)

            # 2. Check pgrep / ps command line
            try:
                # Direct pgrep matching process name
                p_res = subprocess.run(["pgrep", "-if", canonical_name], capture_output=True, text=True)
                if p_res.returncode == 0 and p_res.stdout.strip():
                    return True
            except Exception:
                pass

            # 3. Check AppleScript System Events
            try:
                script = f'tell application "System Events" to return (name of processes) contains "{canonical_name}"'
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=1.0)
                if res.returncode == 0 and "true" in res.stdout.lower():
                    return True
            except Exception:
                pass

            if (time.monotonic() - start_t) >= poll_timeout:
                break
            time.sleep(0.3)

        return False

    @classmethod
    def launch(cls, raw_name: str, target_path: str | Path | None = None) -> tuple[bool, str, str]:
        """Launch application natively on macOS and verify."""
        canonical = cls.resolve_app_name(raw_name)
        matches = cls.find_matching_apps(raw_name)

        if len(matches) > 1:
            # Check if there are exact canonical matches
            exact = [m for m in matches if m.stem.lower() == canonical.lower()]
            if exact:
                matches = exact
            else:
                names = list({m.stem for m in matches})
                if len(names) > 1:
                    spoken = f"I found multiple applications matching '{raw_name}': {', '.join(names[:3])}. Which one would you like to open?"
                    return False, f"Ambiguous application name: {raw_name}", spoken

        # Check if CLI binary exists (e.g. code command for VS Code)
        if canonical == "Visual Studio Code" and shutil.which("code") and target_path:
            try:
                subprocess.Popen(["code", str(target_path)])
                time.sleep(0.3)
                return True, f"Opened '{target_path}' in Visual Studio Code.", "Opening in VS Code."
            except Exception as e:
                logger.debug("VS Code CLI launch note: %s", e)

        # Use discovered bundle path if available, or canonical name fallback
        if matches and matches[0].exists():
            cmd = ["open", str(matches[0])]
            if target_path:
                cmd.append(str(target_path))
        else:
            cmd = ["open", "-a", canonical]
            if target_path:
                cmd.append(str(target_path))

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                time.sleep(0.4)
                running = cls.is_app_running(canonical)
                if running:
                    spoken = f"{canonical} is open, Boss." if not target_path else f"Opened in {canonical}."
                    return True, f"{canonical} launched successfully.", spoken
                else:
                    return False, f"{canonical} was invoked but failed to initialize.", f"I attempted to open {canonical}, but it didn't start."
            else:
                logger.warning("Failed to open '%s': %s", canonical, res.stderr)
                err_clean = res.stderr.strip() or f"Application '{canonical}' not found"
                return False, f"Application not found: {canonical}", f"I couldn't open {canonical} because {err_clean}."
        except Exception as exc:
            logger.error("Error launching app '%s': %s", canonical, exc)
            return False, f"Error launching {canonical}: {exc}", f"I couldn't open {canonical} because: {exc}"

    @classmethod
    def close(cls, raw_name: str) -> tuple[bool, str, str]:
        """Close/quit a running macOS application via AppleScript."""
        canonical = cls.resolve_app_name(raw_name)
        script = f'tell application "{canonical}" to quit'
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0:
                return True, f"{canonical} closed successfully.", f"{canonical} is closed, Boss."
            else:
                return False, f"Could not close '{canonical}': {res.stderr.strip()}", f"I couldn't close {canonical}."
        except Exception as exc:
            return False, f"Error closing {canonical}: {exc}", f"I couldn't close {canonical} because: {exc}"
