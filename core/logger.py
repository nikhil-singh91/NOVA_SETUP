"""Centralized logging configuration for NOVA.

This module is the single place where NOVA's logging system is
configured. It sets up a rotating file handler (for durable,
size-bounded log files) and a colored console handler (for readable
local development output), both attached once to a single named
logger (``"nova"``). Every other module obtains its own logger via
:func:`get_logger`, which returns a child of that logger and
automatically inherits its handlers and formatting.

No other module should call ``logging.basicConfig`` or attach its
own handlers. Doing so would risk duplicate log lines and
inconsistent formatting across the application.

Example:
    from nova.core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Provider initialized successfully.")

Thread Safety:
    Configuration is guarded by a ``threading.Lock`` so that
    concurrent calls to :func:`setup_logging` (or the lazy
    initialization inside :func:`get_logger`) cannot result in
    handlers being attached more than once. Python's ``logging``
    module handlers are themselves internally thread-safe, so
    logging calls from multiple threads are always safe once setup
    has completed.

Async Readiness:
    The standard library ``logging`` module is synchronous but
    thread-safe, and is safe to call directly from ``asyncio``
    coroutines and callbacks without blocking the event loop in any
    way that would corrupt log output. No dedicated async handler is
    required at this stage. If NOVA later needs non-blocking log I/O
    under heavy async load, a ``QueueHandler``/``QueueListener`` can
    be introduced here without changing the public API of this
    module (``setup_logging`` and ``get_logger`` would remain
    unchanged).
"""

from __future__ import annotations

import logging
import logging.handlers
import threading
from pathlib import Path

from config.settings import settings

# --- Module-level constants ---
_ROOT_LOGGER_NAME = "nova"
# _LOG_DIR = Path("logs")
_LOG_DIR = Path(settings.log_directory)
# _LOG_FILE = _LOG_DIR / "nova.log"
_LOG_FILE = _LOG_DIR / f"{settings.app_name.lower()}.log"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log file before rotation
_BACKUP_COUNT = 5  # Keep up to 5 rotated log files
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

# --- Singleton guards ---
_initialization_lock = threading.Lock()
_is_initialized = False


class _ColorFormatter(logging.Formatter):
    """A ``logging.Formatter`` that colorizes level names for the console.

    Colors are applied only to the level name portion of each log
    record, using standard ANSI escape codes. This keeps log files
    (written by a separate, non-colored formatter) clean and free of
    escape sequences, while making console output easier to scan
    during development.
    """

    _LEVEL_COLORS: dict[int, str] = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[1;41m",  # Bold white on red background
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with a colorized level name.

        Args:
            record: The log record to format.

        Returns:
            The fully formatted, colorized log message string.
        """
        color = self._LEVEL_COLORS.get(record.levelno, "")
        original_levelname = record.levelname
        try:
            if color:
                record.levelname = f"{color}{original_levelname}{self._RESET}"
            return super().format(record)
        finally:
            # Restore the original levelname so other handlers
            # (e.g. the file handler) are never affected by this
            # handler's mutation of the shared record object.
            record.levelname = original_levelname


def _ensure_log_directory_exists() -> None:
    """Create NOVA's log directory if it does not already exist.

    Raises:
        NovaLoggingError: If the log directory cannot be created due
            to a filesystem error (e.g. permissions).
    """
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise NovaLoggingError(
            f"Failed to create log directory at '{_LOG_DIR.resolve()}': {exc}"
        ) from exc


class NovaLoggingError(Exception):
    """Raised when NOVA's logging system fails to initialize."""


def setup_logging(*, force: bool = False) -> None:
    """Configure NOVA's logging system exactly once.

    Attaches a rotating file handler and a colored console handler
    to the shared ``"nova"`` logger, using the log level configured
    in :mod:`nova.config.settings`. This function is idempotent:
    calling it multiple times has no additional effect unless
    ``force`` is set to ``True``.

    Args:
        force: If ``True``, remove any existing handlers on the
            ``"nova"`` logger and reconfigure from scratch. Intended
            for testing or for explicitly reloading configuration at
            runtime. Defaults to ``False``.

    Raises:
        NovaLoggingError: If the log directory cannot be created or
            the file handler cannot be opened.
    """
    global _is_initialized

    with _initialization_lock:
        if _is_initialized and not force:
            return

        _ensure_log_directory_exists()

        nova_logger = logging.getLogger(_ROOT_LOGGER_NAME)
        # nova_logger.setLevel(settings.log_level)
        nova_logger.setLevel(getattr(logging, settings.log_level))

        if force:
            for handler in list(nova_logger.handlers):
                nova_logger.removeHandler(handler)
                handler.close()

        # Prevent double-logging through the root logger, since the
        # "nova" logger tree is fully self-contained.
        nova_logger.propagate = False

        if not nova_logger.handlers:
            plain_formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
            color_formatter = _ColorFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    filename=_LOG_FILE,
                    maxBytes=_MAX_BYTES,
                    backupCount=_BACKUP_COUNT,
                    encoding="utf-8",
                )
            except OSError as exc:
                raise NovaLoggingError(
                    f"Failed to open log file at '{_LOG_FILE.resolve()}': {exc}"
                ) from exc

            file_handler.setFormatter(plain_formatter)
            file_handler.setLevel(settings.log_level)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(color_formatter)
            console_handler.setLevel(logging.WARNING)

            class DashboardLogHandler(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    try:
                        from ui.health_checker import DashboardStatsManager
                        raw_msg = record.getMessage()
                        if record.exc_info:
                            if self.formatter:
                                formatted_exc = self.formatter.formatException(record.exc_info)
                            else:
                                import traceback
                                formatted_exc = "".join(traceback.format_exception(*record.exc_info))
                            if formatted_exc:
                                raw_msg = f"{raw_msg}\n{formatted_exc.strip()}"
                        DashboardStatsManager.add_log(
                            level=record.levelname,
                            msg=raw_msg,
                            timestamp=record.created,
                            logger_name=record.name,
                        )
                    except Exception:
                        pass

            dashboard_handler = DashboardLogHandler()
            dashboard_handler.setFormatter(plain_formatter)
            dashboard_handler.setLevel(logging.DEBUG)

            nova_logger.addHandler(file_handler)
            nova_logger.addHandler(console_handler)
            nova_logger.addHandler(dashboard_handler)

        _is_initialized = True
        nova_logger.debug(
            "Logging initialized (level=%s, log_file=%s).",
            settings.log_level,
            _LOG_FILE.resolve(),
        )


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger configured under NOVA's logging system.

    Lazily triggers :func:`setup_logging` on first use if logging has
    not yet been explicitly configured, so this function is always
    safe to call from any module without requiring callers to
    remember to initialize logging first.

    Args:
        name: The name of the requesting module, conventionally
            passed as ``__name__``. The returned logger will be
            namespaced beneath ``"nova"`` (e.g. ``"nova.providers.gemini_provider"``)
            so it inherits the handlers and formatting configured by
            :func:`setup_logging`.

    Returns:
        A standard library ``logging.Logger`` instance ready for use.
    """
    if not _is_initialized:
        setup_logging()

    child_name = name if name.startswith(_ROOT_LOGGER_NAME) else f"{_ROOT_LOGGER_NAME}.{name}"
    return logging.getLogger(child_name)
