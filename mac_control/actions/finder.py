"""Finder filesystem controls to open standard folders and reveal specific files."""

from __future__ import annotations

import os
import subprocess

from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand

FOLDER_MAP = {
    "desktop": "~/Desktop",
    "downloads": "~/Downloads",
    "documents": "~/Documents",
    "project": "~/Desktop/PROJECT",
    "movies": "~/Movies",
    "pictures": "~/Pictures",
    "finder": "~/"
}

def execute_finder_command(cmd: MacCommand) -> ExecutionResult:
    """Execute Finder navigation commands."""
    action = cmd.action
    args = cmd.args

    try:
        if action == "open_folder":
            folder_key = args.get("folder", "finder").lower().strip()
            for suffix in [" folder", " directory"]:
                if folder_key.endswith(suffix):
                    folder_key = folder_key[:-len(suffix)].strip()

            if folder_key in FOLDER_MAP:
                path_str = FOLDER_MAP[folder_key]
                expanded_path = os.path.expanduser(path_str)
            else:
                from desktop.files import FileSystemManager
                matches = FileSystemManager.find_folders_by_name(folder_key)
                if len(matches) == 1:
                    expanded_path = str(matches[0])
                elif len(matches) > 1:
                    match_str = ", ".join(f"'{m.parent.name}/{m.name}'" for m in matches[:3])
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        message=f"Found multiple folders named '{folder_key}': {match_str}. Please specify which one.",
                        command_name="Open Folder",
                        category=CommandCategory.FINDER,
                    )
                else:
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        message=f"Could not find folder '{folder_key}' in Desktop, Documents, or your workspace.",
                        command_name="Open Folder",
                        category=CommandCategory.FINDER,
                    )

            subprocess.run(["open", expanded_path], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Opened {folder_key.title()} in Finder",
                command_name="Open Folder",
                category=CommandCategory.FINDER,
                details={"folder": folder_key, "path": expanded_path}
            )

        elif action == "reveal_file":
            file_path = args.get("path", "").strip()
            if not file_path:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message="No file path specified to reveal",
                    command_name="Reveal File",
                    category=CommandCategory.FINDER
                )
            expanded_path = os.path.expanduser(file_path)
            if not os.path.exists(expanded_path):
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message=f"File path does not exist: {expanded_path}",
                    command_name="Reveal File",
                    category=CommandCategory.FINDER
                )

            subprocess.run(["open", "-R", expanded_path], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Revealed file in Finder: {expanded_path}",
                command_name="Reveal File",
                category=CommandCategory.FINDER,
                details={"path": expanded_path}
            )

    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Finder navigation failed: {exc}",
            command_name="Finder Control",
            category=CommandCategory.FINDER
        )

    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown Finder action: {action}",
        command_name="Finder Control",
        category=CommandCategory.FINDER
    )
