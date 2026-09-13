"""Short-term desktop context tracker for follow-up actions and pronoun resolution."""

from __future__ import annotations

from pathlib import Path

from desktop.safety import DesktopSafetyPolicy


class DesktopContextManager:
    """Maintains short-term desktop context (active folder, last created files, recent apps)."""

    def __init__(self) -> None:
        self.last_workspace: Path = DesktopSafetyPolicy.get_default_workspace()
        self.last_project_dir: Path | None = None
        self.last_created_files: list[Path] = []
        self.last_opened_app: str | None = None
        self.last_captured_photo: Path | None = None

    def get_active_directory(self) -> Path:
        """Return the current active directory for subsequent operations."""
        if self.last_project_dir and self.last_project_dir.exists():
            return self.last_project_dir
        if self.last_workspace and self.last_workspace.exists():
            return self.last_workspace
        return DesktopSafetyPolicy.get_default_workspace()

    def set_active_project(self, project_path: Path) -> None:
        """Update active project directory."""
        self.last_project_dir = project_path

    def register_created_files(self, paths: list[Path]) -> None:
        """Record newly created files."""
        self.last_created_files = paths

    def register_opened_app(self, app_name: str) -> None:
        """Record last opened application."""
        self.last_opened_app = app_name

    def register_captured_photo(self, photo_path: Path) -> None:
        """Record last captured photo."""
        self.last_captured_photo = photo_path

    def reset(self) -> None:
        """Reset short-term session context."""
        self.last_workspace = DesktopSafetyPolicy.get_default_workspace()
        self.last_project_dir = None
        self.last_created_files = []
        self.last_opened_app = None
        self.last_captured_photo = None
