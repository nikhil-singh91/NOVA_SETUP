"""Centralized constant values for NOVA.

This module defines every fixed, non-secret value used across NOVA:
application metadata, directory paths, logging defaults, AI provider
defaults, voice settings, network behavior, supported file formats,
memory limits, and minimum supported Python version.

No other module in NOVA should hardcode string literals, numeric
thresholds, or paths that belong in one of these categories. Instead,
import the relevant constant from this module. This keeps every
"magic string" or "magic number" in the project defined in exactly
one place, so a value only ever needs to change here.

This module contains constants only: no classes, no functions, and
no executable logic beyond simple literal and path construction.

Example:
    from core.constants import APP_NAME, DEFAULT_LOG_LEVEL

    print(f"{APP_NAME} starting with log level {DEFAULT_LOG_LEVEL}.")
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

# =============================================================================
# 1. Application
# =============================================================================

APP_NAME: Final[str] = "NOVA"
"""The display name of the application."""

APP_VERSION: Final[str] = "0.1.0"
"""The current semantic version of NOVA."""

COPYRIGHT: Final[str] = "Copyright (c) 2026 NOVA Project Contributors"
"""The copyright notice displayed in application metadata and CLI banners."""

DEFAULT_ENCODING: Final[str] = "utf-8"
"""The default text encoding used for all file and stream I/O."""

DEFAULT_TIMEZONE: Final[str] = "Asia/Kolkata"
"""The default timezone used for timestamps when no other timezone is specified."""

# =============================================================================
# 2. Directories
# =============================================================================

CACHE_DIR: Final[Path] = Path("data") / "cache"
"""Directory used for transient, regenerable cached data."""

DATA_DIR: Final[Path] = Path("data")
"""Root directory for all persistent application data."""

ASSETS_DIR: Final[Path] = Path("assets")
"""Directory containing application assets (images, icons, sounds, etc.)."""

LOG_DIR: Final[Path] = Path("logs")
"""Directory where rotating log files are written."""

MEMORY_DIR: Final[Path] = DATA_DIR / "memory"
"""Directory used to persist short-term and long-term memory data."""

MODELS_DIR: Final[Path] = Path("models")
"""Directory used to store local model artifacts and model metadata."""

PLUGIN_DIR: Final[Path] = Path("plugins")
"""Directory scanned for installable NOVA plugins."""

PROMPTS_DIR: Final[Path] = Path("prompts")
"""Directory containing prompt templates used by AI providers."""

TEMP_DIR: Final[Path] = Path("data") / "temp"
"""Directory used for short-lived temporary files that may be safely deleted."""

# =============================================================================
# 3. Logging
# =============================================================================

DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
"""The timestamp format used in log messages."""

DEFAULT_LOG_LEVEL: Final[str] = "INFO"
"""The default logging verbosity used when no override is configured."""

LOG_FILE_NAME: Final[str] = "nova.log"
"""The file name used for NOVA's primary rotating log file."""

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
"""The log message format string used by all logging handlers."""

# =============================================================================
# 4. AI
# =============================================================================

DEFAULT_MODEL: Final[str] = "gemini-2.0-flash"
"""The default AI model used when no specific model is requested."""


DEFAULT_PROVIDER: Final[str] = "gemini"
"""The default AI provider."""

PROVIDER_GEMINI: Final[str] = "gemini"
PROVIDER_GROQ: Final[str] = "groq"
PROVIDER_OPENROUTER: Final[str] = "openrouter"
PROVIDER_CEREBRAS: Final[str] = "cerebras"
"""Supported AI provider identifiers."""


DEFAULT_TIMEOUT: Final[float] = 30.0
"""The default timeout, in seconds, for AI provider requests."""

MAX_CONTEXT_MESSAGES: Final[int] = 20
"""The maximum number of prior conversation messages retained as context."""

MAX_MEMORY_RESULTS: Final[int] = 10
"""The maximum number of memory records retrieved for a single query."""

SUPPORTED_PROVIDERS: Final[tuple[str, ...]] = (
    PROVIDER_CEREBRAS,
    PROVIDER_GEMINI,
    PROVIDER_GROQ,
    PROVIDER_OPENROUTER,
)
"""The set of AI provider identifiers supported by NOVA."""

# =============================================================================
# 5. Voice
# =============================================================================

AUTO_LANGUAGE_DETECTION: Final[bool] = True
"""Automatically detect whether the user is speaking English or Hinglish."""

CHANNELS: Final[int] = 1

"""Default audio channel count."""

DEFAULT_LANGUAGE: Final[str] = "en-IN"

"""Default language for speech recognition."""

SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = (

    "en-IN",

    "hi-IN",

)

"""Languages supported by NOVA."""

DEFAULT_VOICE_PROVIDER: Final[str] = "elevenlabs"

"""Default text-to-speech provider."""

DEFAULT_VOICE: Final[str] = "Bella"

"""Default female companion voice."""

ROMAN_HINDI_ENABLED: Final[bool] = True

"""Reply in Roman Hindi instead of Devanagari when speaking Hinglish."""

HINDI_SCRIPT_ENABLED: Final[bool] = False

"""Do not generate Hindi script unless explicitly requested."""

SAMPLE_RATE: Final[int] = 16000

"""Default audio sample rate."""

WAKE_WORDS: Final[tuple[str, ...]] = (

    "nova",

    "hey nova",

)

"""Supported wake words."""


# =============================================================================
# Commands
# =============================================================================

EXIT_COMMANDS: Final[tuple[str, ...]] = (
    "bye",
    "exit",
    "quit",
    "stop",
)
"""Commands that terminate NOVA."""

# =============================================================================
# 6. Network
# =============================================================================

BACKOFF_FACTOR: Final[float] = 0.5
"""The exponential backoff multiplier applied between retry attempts."""

MAX_RETRIES: Final[int] = 3
"""The maximum number of retry attempts for a failed network request."""

REQUEST_TIMEOUT: Final[float] = 15.0
"""The default timeout, in seconds, for general outbound network requests."""

# =============================================================================
# 7. File Formats
# =============================================================================

SUPPORTED_AUDIO_FORMATS: Final[tuple[str, ...]] = (".flac", ".m4a", ".mp3", ".ogg", ".wav")
"""The audio file extensions supported for input and output."""

SUPPORTED_DOCUMENT_FORMATS: Final[tuple[str, ...]] = (".csv", ".docx", ".json", ".pdf", ".txt")
"""The document file extensions supported for reading and processing."""

SUPPORTED_IMAGE_FORMATS: Final[tuple[str, ...]] = (".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp")
"""The image file extensions supported for vision-related processing."""

# =============================================================================
# 8. Memory
# =============================================================================

LONG_TERM_LIMIT: Final[int] = 5000
"""The maximum number of records retained in long-term memory."""

SHORT_TERM_LIMIT: Final[int] = 50
"""The maximum number of records retained in short-term memory before eviction."""

SUMMARY_TRIGGER: Final[int] = 40
"""The short-term memory record count at which older entries are summarized."""

# =============================================================================
# 9. Version
# =============================================================================

PYTHON_MIN_VERSION: Final[tuple[int, int]] = (3, 12)
"""The minimum supported Python version, as a (major, minor) tuple."""


__all__ = [
    # Application
    "APP_NAME",
    "APP_VERSION",
    "COPYRIGHT",
    "DEFAULT_ENCODING",
    "DEFAULT_TIMEZONE",
    # Directories
    "CACHE_DIR",
    "DATA_DIR",
    "ASSETS_DIR",
    "LOG_DIR",
    "MEMORY_DIR",
    "MODELS_DIR",
    "PLUGIN_DIR",
    "PROMPTS_DIR",
    "TEMP_DIR",
    # Logging
    "DATE_FORMAT",
    "DEFAULT_LOG_LEVEL",
    "LOG_FILE_NAME",
    "LOG_FORMAT",
    # AI
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "DEFAULT_TIMEOUT",
    "MAX_CONTEXT_MESSAGES",
    "MAX_MEMORY_RESULTS",
    "SUPPORTED_PROVIDERS",
    "PROVIDER_GEMINI",
    "PROVIDER_GROQ",
    "PROVIDER_OPENROUTER",
    "PROVIDER_CEREBRAS",

    # Voice
    "AUTO_LANGUAGE_DETECTION",
    "CHANNELS",
    "DEFAULT_LANGUAGE",
    "SUPPORTED_LANGUAGES",
    "DEFAULT_VOICE_PROVIDER",
    "DEFAULT_VOICE",
    "ROMAN_HINDI_ENABLED",
    "HINDI_SCRIPT_ENABLED",
    "SAMPLE_RATE",
    "WAKE_WORDS",

    # Commands
    "EXIT_COMMANDS",
    
    # Network
    "BACKOFF_FACTOR",
    "MAX_RETRIES",
    "REQUEST_TIMEOUT",
    # File Formats
    "SUPPORTED_AUDIO_FORMATS",
    "SUPPORTED_DOCUMENT_FORMATS",
    "SUPPORTED_IMAGE_FORMATS",
    # Memory
    "LONG_TERM_LIMIT",
    "SHORT_TERM_LIMIT",
    "SUMMARY_TRIGGER",
    # Version
    "PYTHON_MIN_VERSION",

]
