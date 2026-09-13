"""Safety boundaries and workspace verification for NOVA Desktop Actions."""

from __future__ import annotations

from pathlib import Path

from config.settings import settings
from core.logger import get_logger

from desktop.models import DesktopActionPlan

logger = get_logger(__name__)


class DesktopSafetyPolicy:
    """Enforces workspace boundaries and prevents unintended file destruction or system modifications."""

    RESTRICTED_SYSTEM_ROOTS = [
        Path("/"),
        Path("/System"),
        Path("/Library"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/etc"),
        Path("/var"),
        Path("/private"),
    ]

    @classmethod
    def get_default_workspace(cls) -> Path:
        """Return the configured safe default workspace directory, creating it if needed."""
        ws_str = getattr(settings, "desktop_workspace_dir", "~/Desktop/NOVA_WORKSPACE")
        ws_path = Path(ws_str).expanduser().resolve()
        ws_path.mkdir(parents=True, exist_ok=True)
        return ws_path

    @classmethod
    def resolve_target_path(cls, relative_or_absolute: str, parent: Path | None = None) -> Path:
        """Resolve a requested path safely within the workspace or approved parent."""
        if not relative_or_absolute:
            return cls.get_default_workspace()

        raw_path = Path(relative_or_absolute).expanduser()
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            base = parent or cls.get_default_workspace()
            resolved = (base / raw_path).resolve()

        return resolved

    @classmethod
    def is_safe_path(cls, target_path: Path) -> bool:
        """Verify that a path is not in a restricted root system directory."""
        resolved = target_path.resolve()
        for restricted in cls.RESTRICTED_SYSTEM_ROOTS:
            if resolved == restricted or resolved == restricted / "bin":
                return False
        return True

    @classmethod
    def evaluate(cls, plan: DesktopActionPlan) -> DesktopActionPlan:
        """Evaluate plan safety and flag confirmation requirements if necessary."""
        # Actions outside approved paths or involving destructive operations
        if plan.target_path:
            p = Path(plan.target_path).expanduser().resolve()
            if not cls.is_safe_path(p):
                plan.requires_confirmation = True
                plan.confirmation_prompt = f"Warning: Target path '{p}' is outside safe workspace. Do you want to proceed?"

        return plan
