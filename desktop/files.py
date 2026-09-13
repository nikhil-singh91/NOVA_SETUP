"""Safe file and folder management with multi-root resolution, overwrite protection, and macOS Trash integration."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from core.environment import environment_observer
from core.logger import get_logger

from desktop.safety import DesktopSafetyPolicy

logger = get_logger(__name__)


class FileSystemManager:
    """Safely manages directories and files across user-accessible locations."""

    @classmethod
    def get_safe_search_roots(cls) -> list[Path]:
        """Return approved user search directories dynamically resolving home."""
        home = Path.home()
        roots = [
            (home / "Desktop").resolve(),
            (home / "Documents").resolve(),
            (home / "Downloads").resolve(),
            (home / "Projects").resolve(),
            (home / "Applications").resolve(),
            DesktopSafetyPolicy.get_default_workspace().resolve(),
        ]
        # Include active workspace root if distinct
        current_ws = Path.cwd().resolve()
        if current_ws not in roots:
            roots.append(current_ws)
        return [r for r in roots if r.exists()]

    @classmethod
    def resolve_destination(cls, location_or_parent: str | Path | None = None) -> Path:
        """Resolve a natural language location or parent folder name into an absolute directory Path."""
        home = Path.home()
        if location_or_parent is None:
            return (home / "Desktop").resolve()

        if isinstance(location_or_parent, Path):
            return location_or_parent.resolve()

        loc_clean = location_or_parent.strip().lower()

        # Standard system folders
        if any(loc_clean == p or loc_clean.endswith(f" {p}") for p in ["desktop", "my desktop", "on desktop", "on my desktop"]):
            return (home / "Desktop").resolve()
        if any(loc_clean == p or loc_clean.endswith(f" {p}") for p in ["documents", "my documents", "in documents", "in my documents"]):
            return (home / "Documents").resolve()
        if any(loc_clean == p or loc_clean.endswith(f" {p}") for p in ["downloads", "my downloads", "in downloads", "in my downloads"]):
            return (home / "Downloads").resolve()
        if loc_clean in ["projects", "my projects"]:
            proj = (home / "Projects").resolve()
            proj.mkdir(parents=True, exist_ok=True)
            return proj
        if loc_clean in ["home", "my home"]:
            return home.resolve()
        if loc_clean in ["workspace", "my workspace", "novaworkspace", "nova_workspace"]:
            return DesktopSafetyPolicy.get_default_workspace().resolve()

        # Check if location specifies an existing named parent folder
        folder_query = loc_clean
        for prefix in ["inside ", "in ", "into ", "under ", "folder ", "the "]:
            if folder_query.startswith(prefix):
                folder_query = folder_query[len(prefix):].strip()
        for suffix in [" folder", " directory", " dir"]:
            if folder_query.endswith(suffix):
                folder_query = folder_query[:-len(suffix)].strip()

        if folder_query:
            matches = cls.find_folders_by_name(folder_query)
            if matches:
                return matches[0]

        # Default fallback to Desktop
        return (home / "Desktop").resolve()

    @classmethod
    def find_folders_by_name(cls, folder_name: str) -> list[Path]:
        """Search approved safe directories for folders matching the given name (case-insensitive)."""
        target_name = folder_name.lower().strip()
        for suffix in [" folder", " directory", " dir"]:
            if target_name.endswith(suffix):
                target_name = target_name[:-len(suffix)].strip()

        matches: list[Path] = []
        visited_strs: set[str] = set()

        for root in cls.get_safe_search_roots():
            try:
                # Search 1-2 levels deep inside roots
                for entry in root.iterdir():
                    if entry.is_dir():
                        entry_res = entry.resolve()
                        if entry.name.lower() == target_name and str(entry_res).lower() not in visited_strs:
                            matches.append(entry_res)
                            visited_strs.add(str(entry_res).lower())
                        # Check subdirectories
                        try:
                            for sub in entry.iterdir():
                                if sub.is_dir() and sub.name.lower() == target_name:
                                    sub_res = sub.resolve()
                                    if str(sub_res).lower() not in visited_strs:
                                        matches.append(sub_res)
                                        visited_strs.add(str(sub_res).lower())
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError) as exc:
                logger.debug("Error searching directory '%s': %s", root, exc)

        return matches

    @classmethod
    def find_files_by_name(cls, file_name: str) -> list[Path]:
        """Search approved safe directories for files matching the given name (case-insensitive)."""
        target_name = file_name.lower().strip()
        matches: list[Path] = []
        visited_strs: set[str] = set()

        for root in cls.get_safe_search_roots():
            try:
                # Search 1-2 levels deep inside roots
                for entry in root.iterdir():
                    entry_res = entry.resolve()
                    if entry.is_file():
                        if (entry.name.lower() == target_name or entry.stem.lower() == target_name) and str(entry_res).lower() not in visited_strs:
                            matches.append(entry_res)
                            visited_strs.add(str(entry_res).lower())
                    elif entry.is_dir():
                        try:
                            for sub in entry.iterdir():
                                if sub.is_file() and (sub.name.lower() == target_name or sub.stem.lower() == target_name):
                                    sub_res = sub.resolve()
                                    if str(sub_res).lower() not in visited_strs:
                                        matches.append(sub_res)
                                        visited_strs.add(str(sub_res).lower())
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError) as exc:
                logger.debug("Error searching files in '%s': %s", root, exc)

        return matches

    @classmethod
    def find_items(cls, query: str, target_type: str = "any") -> list[Path]:
        """Find files or folders matching a search query across approved roots."""
        clean_q = query.lower().strip()
        for prefix in ["my ", "the ", "a "]:
            if clean_q.startswith(prefix):
                clean_q = clean_q[len(prefix):].strip()

        matches: list[Path] = []
        if target_type in ("folder", "dir", "directory"):
            matches = cls.find_folders_by_name(clean_q)
        elif target_type == "file":
            matches = cls.find_files_by_name(clean_q)
        else:
            # Check folders first, then files
            matches = cls.find_folders_by_name(clean_q)
            file_matches = cls.find_files_by_name(clean_q)
            for fm in file_matches:
                if fm not in matches:
                    matches.append(fm)

        return matches

    @classmethod
    def create_folder(
        cls,
        folder_name: str,
        parent: Path | None = None,
        location: str | None = None,
        on_desktop: bool = False,
    ) -> tuple[bool, Path, str]:
        """Create a new folder inside the requested location or parent directory."""
        if parent:
            base_dir = parent.resolve()
        elif on_desktop:
            base_dir = (Path.home() / "Desktop").resolve()
        elif location:
            base_dir = cls.resolve_destination(location)
        else:
            base_dir = (Path.home() / "Desktop").resolve()

        target_dir = (base_dir / folder_name).resolve()

        if not DesktopSafetyPolicy.is_safe_path(target_dir):
            return False, target_dir, f"Cannot create folder in restricted system path: {target_dir}"

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Created directory: '%s'", target_dir)
            environment_observer.update_action_context(
                action="CREATE_FOLDER",
                created_path=target_dir,
            )
            return True, target_dir, f"Created folder '{folder_name}' at {target_dir}"
        except Exception as exc:
            logger.error("Failed to create folder '%s': %s", target_dir, exc)
            return False, target_dir, f"Failed to create folder: {exc}"

    @classmethod
    def create_files(
        cls,
        file_names: list[str],
        parent: Path | None = None,
        location: str | None = None,
        content_map: dict[str, str] | None = None,
        overwrite: bool = False,
    ) -> tuple[bool, list[Path], str]:
        """Create multiple files safely with overwrite protection and optional initial content."""
        if parent:
            base_dir = parent.resolve()
        elif location:
            base_dir = cls.resolve_destination(location)
        else:
            base_dir = (Path.home() / "Desktop").resolve()

        base_dir.mkdir(parents=True, exist_ok=True)
        created_paths: list[Path] = []
        contents = content_map or {}

        try:
            for fname in file_names:
                clean_name = fname.strip()
                if not clean_name:
                    continue
                file_path = (base_dir / clean_name).resolve()

                if not DesktopSafetyPolicy.is_safe_path(file_path):
                    logger.warning("Skipping restricted file path: %s", file_path)
                    continue

                # Ensure parent subdirectories exist
                file_path.parent.mkdir(parents=True, exist_ok=True)

                if file_path.exists() and not overwrite:
                    logger.info("File '%s' already exists; preserving without destructive overwrite.", file_path)
                    created_paths.append(file_path)
                    continue

                text_to_write = contents.get(clean_name, "")
                file_path.write_text(text_to_write, encoding="utf-8")
                logger.info("Created file: '%s' (%d bytes)", file_path, len(text_to_write))
                created_paths.append(file_path)

            if created_paths:
                environment_observer.update_action_context(
                    action="CREATE_FILES",
                    created_path=created_paths[0],
                )

            file_list_str = ", ".join([p.name for p in created_paths])
            return True, created_paths, f"Created {len(created_paths)} file(s): {file_list_str} in {base_dir.name}"
        except Exception as exc:
            logger.error("Failed to create files: %s", exc)
            return False, created_paths, f"Error creating files: {exc}"

    @classmethod
    def rename_item(cls, target_query: str, new_name: str, parent: Path | None = None) -> tuple[bool, Path | None, str]:
        """Rename an existing file or folder safely."""
        clean_new = new_name.strip()
        if not clean_new:
            return False, None, "New name cannot be empty."

        # Find target
        if parent:
            candidate = parent / target_query
            if candidate.exists():
                matches = [candidate]
            else:
                matches = cls.find_items(target_query)
        else:
            matches = cls.find_items(target_query)

        if not matches:
            return False, None, f"Could not find '{target_query}' to rename."

        if len(matches) > 1:
            match_str = ", ".join(f"'{m.parent.name}/{m.name}'" for m in matches[:3])
            return False, None, f"I found multiple items named '{target_query}': {match_str}. Please specify which one."

        target_path = matches[0]
        new_path = (target_path.parent / clean_new).resolve()

        if new_path.exists():
            return False, target_path, f"An item named '{clean_new}' already exists in {target_path.parent.name}."

        try:
            target_path.rename(new_path)
            logger.info("Renamed '%s' to '%s'", target_path, new_path)
            environment_observer.update_action_context(action="RENAME", created_path=new_path)
            return True, new_path, f"Renamed '{target_path.name}' to '{clean_new}' in {target_path.parent.name}."
        except Exception as exc:
            logger.error("Failed to rename '%s': %s", target_path, exc)
            return False, target_path, f"Failed to rename: {exc}"

    @classmethod
    def open_item(cls, target_path: Path, app_name: str | None = None) -> tuple[bool, str]:
        """Open a file or folder in Finder or a specified application."""
        resolved = target_path.resolve()
        if not resolved.exists():
            return False, f"Path does not exist: {resolved}"

        if app_name:
            from desktop.apps import AppLauncher
            canonical_app = AppLauncher.resolve_app_name(app_name)
            success, msg, spoken = AppLauncher.launch(canonical_app, target_path=resolved)
            return success, spoken or msg
        else:
            subprocess.run(["open", str(resolved)], check=False)
            if resolved.is_dir():
                return True, f"Opened {resolved.name} folder in Finder."
            else:
                return True, f"Opened {resolved.name}."

    @classmethod
    def safe_move_to_trash(cls, target_path: Path) -> tuple[bool, str]:
        """Safely move a file or directory to the macOS Trash instead of permanent deletion."""
        resolved = target_path.resolve()
        if not resolved.exists():
            return False, f"Path does not exist: {resolved}"

        if not DesktopSafetyPolicy.is_safe_path(resolved):
            return False, f"Refusing to delete restricted system path: {resolved}"

        # 1. Attempt AppleScript Finder deletion (moves to Trash natively)
        script = f"""
        tell application "Finder"
            try
                delete POSIX file "{resolved}"
                return "SUCCESS"
            on error errMsg
                return "ERROR:" & errMsg
            end try
        end tell
        """
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3.0)
            if proc.returncode == 0 and "SUCCESS" in proc.stdout:
                logger.info("Moved '%s' to Trash via Finder.", resolved)
                return True, f"Moved '{resolved.name}' to Trash."
        except Exception as exc:
            logger.debug("Finder trash note: %s", exc)

        # 2. Fallback: move to ~/.Trash
        try:
            trash_dir = Path.home() / ".Trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            dest = trash_dir / resolved.name
            if dest.exists():
                timestamp = int(os.times().system)
                dest = trash_dir / f"{resolved.stem}_{timestamp}{resolved.suffix}"
            shutil.move(str(resolved), str(dest))
            logger.info("Moved '%s' to ~/.Trash (%s).", resolved, dest)
            return True, f"Moved '{resolved.name}' to Trash."
        except Exception as exc:
            logger.error("Failed to move '%s' to Trash: %s", resolved, exc)
            return False, f"Failed to delete '{resolved.name}': {exc}"

    @classmethod
    def create_tree(
        cls,
        root_name: str,
        subfolders: list[str],
        files: list[str] | None = None,
        parent: Path | None = None,
        location: str | None = None,
    ) -> tuple[bool, Path, list[Path], str]:
        """Create a nested folder tree with subfolders and files."""
        success, root_path, msg = cls.create_folder(root_name, parent=parent, location=location)
        if not success:
            return False, root_path, [], msg

        all_created: list[Path] = [root_path]

        # Create subfolders
        for sub in subfolders:
            sub_clean = sub.strip()
            if sub_clean:
                sub_path = (root_path / sub_clean).resolve()
                sub_path.mkdir(parents=True, exist_ok=True)
                all_created.append(sub_path)

        # Create root files if any
        if files:
            _, created_files, _ = cls.create_files(files, parent=root_path)
            all_created.extend(created_files)

        logger.info("Created tree structure at '%s' with %d nodes.", root_path, len(all_created))
        return True, root_path, all_created, f"Created tree structure for '{root_name}' with {len(subfolders)} subfolders."
