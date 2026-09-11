"""Application management controls using AppleScript and macOS shell utilities."""

from __future__ import annotations

import subprocess
import time
from mac_control.models import ExecutionResult, ExecutionStatus, CommandCategory, MacCommand

from desktop.apps import AppLauncher

def execute_applications_command(cmd: MacCommand) -> ExecutionResult:
    """Execute application lifecycle actions (open, quit, force-quit, restart)."""
    action = cmd.action
    app_query = cmd.args.get("app_name", "").lower().strip()
    if not app_query:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="No application name specified",
            command_name="Application Control",
            category=CommandCategory.APPLICATIONS
        )
        
    # Redirect standard folder queries in case they bypass parser categorizations
    import os
    system_folders = ["desktop", "downloads", "documents", "project", "movies", "pictures", "finder"]
    matched_folder = None
    for folder in system_folders:
        if folder in app_query:
            matched_folder = folder
            break
            
    if matched_folder is not None and (action == "open" or action == "focus"):
        from mac_control.actions.finder import FOLDER_MAP
        path_str = FOLDER_MAP.get(matched_folder, "~/")
        expanded_path = os.path.expanduser(path_str)
        try:
            subprocess.run(["open", expanded_path], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Opened {matched_folder.title()} in Finder",
                command_name="Open Folder",
                category=CommandCategory.FINDER,
                details={"folder": matched_folder, "path": expanded_path}
            )
        except Exception as exc:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to open {matched_folder.title()}: {exc}",
                command_name="Open Folder",
                category=CommandCategory.FINDER
            )

    app_name = AppLauncher.resolve_app_name(app_query)
    
    try:
        if action == "open" or action == "focus":
            # For Finder, we open Finder path
            if app_name == "Finder":
                subprocess.run(["open", "-a", "Finder"], check=True)
            else:
                subprocess.run(["open", "-a", app_name], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Opened {app_name}",
                command_name="Open Application",
                category=CommandCategory.APPLICATIONS,
                details={"app_name": app_name}
            )
            
        elif action == "close":
            if app_name == "Finder":
                return ExecutionResult(
                    status=ExecutionStatus.NOT_SUPPORTED,
                    message="Closing Finder is not supported by macOS core architecture",
                    command_name="Close Application",
                    category=CommandCategory.APPLICATIONS
                )
            script = f'tell application "{app_name}" to quit'
            subprocess.run(["osascript", "-e", script], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Quit {app_name}",
                command_name="Close Application",
                category=CommandCategory.APPLICATIONS,
                details={"app_name": app_name}
            )
            
        elif action == "force_quit":
            if app_name == "Finder":
                subprocess.run(["killall", "Finder"], check=True)
            else:
                # pkill -x matches exact app process name, pkill -f matches full path/name
                # Note: macOS app process names sometimes differ from the app bundle name.
                # We try both killall and pkill
                try:
                    subprocess.run(["killall", app_name], check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    subprocess.run(["pkill", "-f", app_name], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Force quit {app_name}",
                command_name="Force Quit Application",
                category=CommandCategory.APPLICATIONS,
                details={"app_name": app_name}
            )
            
        elif action == "restart":
            # Quit the application, wait, then open it again
            script = f'tell application "{app_name}" to quit'
            subprocess.run(["osascript", "-e", script], check=False)
            time.sleep(1.0)
            subprocess.run(["open", "-a", app_name], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Restarted {app_name}",
                command_name="Restart Application",
                category=CommandCategory.APPLICATIONS,
                details={"app_name": app_name}
            )
            
    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Failed to perform application operation: {exc}",
            command_name="Application Control",
            category=CommandCategory.APPLICATIONS
        )
        
    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown application action: {action}",
        command_name="Application Control",
        category=CommandCategory.APPLICATIONS
    )
