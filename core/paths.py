"""Centralized path resolution for NOVA.

This module is the single place where NOVA resolves the absolute
filesystem locations of its working directories, and where those
directories are physically created on disk if they do not already
exist. Every other module that needs a directory path (for logs,
cached data, memory storage, model artifacts, plugins, or prompt
templates) should import the relevant constant from this module
rather than constructing a path itself.

This module deliberately does not import ``config.settings``.
Directory resolution here depends only on the project's physical
location on disk and the relative paths defined in
``core.constants``; none of the current settings values (API keys,
log level, debug flag, app environment) change *where* these
directories live. If a future phase requires environment-specific
directory layouts, ``settings`` should be introduced here at that
point, deliberately, rather than imported unused.

All directories exposed by this module are guaranteed to exist by
the time this module has finished importing: :func:`ensure_directories`
is called exactly once, at import time, guarded by a lock so that
concurrent imports from multiple threads cannot create directories
more than once or race on the filesystem.

Example:
    from core.paths import LOG_DIR, MEMORY_DIR

    log_file = LOG_DIR / "nova.log"
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Final

from core.constants import CACHE_DIR as _CACHE_DIR_RELATIVE
from core.constants import DATA_DIR as _DATA_DIR_RELATIVE
from core.constants import ASSETS_DIR as _ASSETS_DIR_RELATIVE
from core.constants import LOG_DIR as _LOG_DIR_RELATIVE
from core.constants import MEMORY_DIR as _MEMORY_DIR_RELATIVE
from core.constants import MODELS_DIR as _MODELS_DIR_RELATIVE
from core.constants import PLUGIN_DIR as _PLUGIN_DIR_RELATIVE
from core.constants import PROMPTS_DIR as _PROMPTS_DIR_RELATIVE
from core.constants import TEMP_DIR as _TEMP_DIR_RELATIVE
from core.logger import get_logger

logger = get_logger(__name__)

# --- Singleton guard for directory creation ---
_directory_creation_lock = threading.Lock()
_directories_ensured = False


def project_root() -> Path:
    """Return the absolute path to NOVA's project root directory.

    The project root is resolved relative to this file's own
    location on disk (two levels up from ``core/paths.py``), so it
    is correct regardless of the current working directory the
    application was launched from.

    Returns:
        The absolute :class:`~pathlib.Path` to the project root,
        i.e. the directory containing ``main.py``.
    """
    return Path(__file__).resolve().parent.parent


# --- Absolute, resolved directory paths ---



_ROOT: Final[Path] = project_root()

DATA_DIR: Final[Path] = _ROOT / _DATA_DIR_RELATIVE
"""Absolute path to the root directory for all persistent application data."""

ASSETS_DIR: Final[Path] = _ROOT / _ASSETS_DIR_RELATIVE
"""Absolute path to the application's assets directory."""

LOG_DIR: Final[Path] = _ROOT / _LOG_DIR_RELATIVE
"""Absolute path to the directory where rotating log files are written."""

CACHE_DIR: Final[Path] = _ROOT / _CACHE_DIR_RELATIVE
"""Absolute path to the directory used for transient, regenerable cached data."""

MEMORY_DIR: Final[Path] = _ROOT / _MEMORY_DIR_RELATIVE
"""Absolute path to the directory used to persist memory data."""

MODELS_DIR: Final[Path] = _ROOT / _MODELS_DIR_RELATIVE
"""Absolute path to the directory used to store local model artifacts."""

PLUGIN_DIR: Final[Path] = _ROOT / _PLUGIN_DIR_RELATIVE
"""Absolute path to the directory scanned for installable NOVA plugins."""

PROMPTS_DIR: Final[Path] = _ROOT / _PROMPTS_DIR_RELATIVE
"""Absolute path to the directory containing prompt templates."""

TEMP_DIR: Final[Path] = _ROOT / _TEMP_DIR_RELATIVE
"""Absolute path to the directory used for short-lived temporary files."""

_ALL_DIRECTORIES: Final[tuple[Path, ...]] = (
    DATA_DIR,
    ASSETS_DIR,
    LOG_DIR,
    CACHE_DIR,
    MEMORY_DIR,
    MODELS_DIR,
    PLUGIN_DIR,
    PROMPTS_DIR,
    TEMP_DIR,
)


def ensure_directories(*, force: bool = False) -> None:
    """Create every NOVA working directory if it does not already exist.

    This function is idempotent and thread-safe: concurrent calls
    from multiple threads will only ever create each directory once.
    It is called automatically, exactly once, when this module is
    first imported, so callers do not need to invoke it manually
    under normal circumstances.

    Args:
        force: If ``True``, re-run directory creation even if it has
            already completed successfully. Existing directories are
            left untouched (``exist_ok=True``); this is intended for
            testing scenarios where directories may have been removed
            after initial creation. Defaults to ``False``.

    Raises:
        OSError: If a directory cannot be created due to a
            filesystem error, such as insufficient permissions or an
            invalid path.
    """
    global _directories_ensured

    with _directory_creation_lock:
        if _directories_ensured and not force:
            return

        for directory in _ALL_DIRECTORIES:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError:
                logger.error(
                    "Failed to create required directory: %s", directory, exc_info=True
                )
                raise

        _directories_ensured = True
        logger.info(
            "NOVA directories initialized successfully."
        )       


# Ensure every working directory exists as soon as this module is
# imported, so the rest of the application can rely on these paths
# being usable immediately.
ensure_directories()


__all__ = [
    "project_root",
    "ensure_directories",
    "DATA_DIR",
    "ASSETS_DIR",
    "LOG_DIR",
    "CACHE_DIR",
    "MEMORY_DIR",
    "MODELS_DIR",
    "PLUGIN_DIR",
    "PROMPTS_DIR",
    "TEMP_DIR",
]
