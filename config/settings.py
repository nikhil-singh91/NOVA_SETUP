"""
Centralized application configuration for NOVA.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env from project root is loaded into environment
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)

logger = logging.getLogger(__name__)


class NovaConfigurationError(Exception):
    """Raised when NOVA configuration is invalid."""


class Settings(BaseSettings):
    """
    Central configuration for NOVA.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ======================================================
    # AI PROVIDERS
    # ======================================================

    gemini_api_key: SecretStr = Field(..., alias="GEMINI_API_KEY")
    groq_api_key: SecretStr = Field(..., alias="GROQ_API_KEY")
    openrouter_api_key: SecretStr = Field(..., alias="OPENROUTER_API_KEY")
    cerebras_api_key: SecretStr = Field(..., alias="CEREBRAS_API_KEY")

    # ======================================================
    # SERVICES
    # ======================================================

    tavily_api_key: SecretStr = Field(..., alias="TAVILY_API_KEY")
    elevenlabs_api_key: SecretStr = Field(..., alias="ELEVENLABS_API_KEY")
    openweather_api_key: SecretStr = Field(..., alias="OPENWEATHER_API_KEY")
    news_api_key: SecretStr = Field(..., alias="NEWS_API_KEY")

    # Optional until you generate one
    google_maps_api_key: SecretStr | None = Field(
        default=None,
        alias="GOOGLE_MAPS_API_KEY",
    )

    # ======================================================
    # APPLICATION
    # ======================================================

    app_name: str = "NOVA"
    app_version: str = "0.1.0"

    app_env: str = Field(
        default="development",
        alias="APP_ENV",
    )

    debug: bool = Field(
        default=False,
        alias="DEBUG",
    )

    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
    )

    # ======================================================
    # STORAGE
    # ======================================================

    memory_path: str = "data/memory.db"
    log_directory: str = "logs"

    # ======================================================
    # VOICE
    # ======================================================

    voice_enabled: bool = True
    voice_name: str = "Nova"
    tts_voice: str = Field(
        default="hi-IN-SwaraNeural",
        alias="TTS_VOICE",
    )
    stt_engine: str = Field(
        default="whisper",
        alias="STT_ENGINE",
    )
    tts_engine: str = Field(
        default="edge_tts",
        alias="TTS_ENGINE",
    )
    whisper_model_name: str = Field(
        default="small",
        alias="WHISPER_MODEL_NAME",
    )
    stt_device_index: int | None = Field(
        default=None,
        alias="STT_DEVICE_INDEX",
    )
    stt_sample_rate: int | None = Field(
        default=16000,
        alias="STT_SAMPLE_RATE",
    )
    stt_timeout_seconds: float | None = Field(
        default=5.0,
        alias="STT_TIMEOUT_SECONDS",
    )
    stt_phrase_time_limit_seconds: float | None = Field(
        default=15.0,
        alias="STT_PHRASE_TIME_LIMIT_SECONDS",
    )
    stt_ambient_noise_calibration_seconds: float = Field(
        default=1.0,
        alias="STT_AMBIENT_NOISE_CALIBRATION_SECONDS",
    )
    stt_dynamic_energy_threshold: bool = Field(
        default=True,
        alias="STT_DYNAMIC_ENERGY_THRESHOLD",
    )
    stt_energy_threshold: int | None = Field(
        default=None,
        alias="STT_ENERGY_THRESHOLD",
    )
    stt_silence_duration_seconds: float = Field(
        default=0.9,
        alias="STT_SILENCE_DURATION_SECONDS",
    )
    stt_min_speech_duration_seconds: float = Field(
        default=0.35,
        alias="STT_MIN_SPEECH_DURATION_SECONDS",
    )
    stt_max_speech_duration_seconds: float = Field(
        default=20.0,
        alias="STT_MAX_SPEECH_DURATION_SECONDS",
    )
    stt_language: str = Field(
        default="en",
        alias="STT_LANGUAGE",
    )
    tts_rate: str = Field(
        default="+0%",
        alias="TTS_RATE",
    )
    tts_volume: str = Field(
        default="+0%",
        alias="TTS_VOLUME",
    )

    # ======================================================
    # BROWSER AUTOMATION
    # ======================================================

    default_browser: str = Field(
        default="chrome",
        alias="DEFAULT_BROWSER",
    )
    browser_auto_shorts_interval_seconds: float = Field(
        default=15.0,
        alias="BROWSER_AUTO_SHORTS_INTERVAL_SECONDS",
    )
    browser_action_timeout_seconds: float = Field(
        default=10.0,
        alias="BROWSER_ACTION_TIMEOUT_SECONDS",
    )
    browser_headless: bool = Field(
        default=False,
        alias="BROWSER_HEADLESS",
    )
    browser_max_research_pages: int = Field(
        default=3,
        alias="BROWSER_MAX_RESEARCH_PAGES",
    )
    browser_max_content_chars: int = Field(
        default=6000,
        alias="BROWSER_MAX_CONTENT_CHARS",
    )
    browser_max_task_steps: int = Field(
        default=6,
        alias="BROWSER_MAX_TASK_STEPS",
    )
    browser_page_extract_timeout_seconds: float = Field(
        default=8.0,
        alias="BROWSER_PAGE_EXTRACT_TIMEOUT_SECONDS",
    )
    nova_browser_debug: bool = Field(
        default=False,
        alias="NOVA_BROWSER_DEBUG",
    )
    nova_intent_debug: bool = Field(
        default=False,
        alias="NOVA_INTENT_DEBUG",
    )
    nova_media_debug: bool = Field(
        default=False,
        alias="NOVA_MEDIA_DEBUG",
    )
    desktop_workspace_dir: str = Field(
        default="~/Desktop/NOVA_WORKSPACE",
        alias="DESKTOP_WORKSPACE_DIR",
    )
    desktop_camera_output_dir: str = Field(
        default="~/Pictures/NOVA",
        alias="DESKTOP_CAMERA_OUTPUT_DIR",
    )
    nova_desktop_debug: bool = Field(
        default=False,
        alias="NOVA_DESKTOP_DEBUG",
    )

    # ======================================================
    # DEFAULT AI
    # ======================================================

    default_provider: str = "gemini"

    # ======================================================
    # REGION
    # ======================================================

    timezone: str = "Asia/Kolkata"

    # ======================================================
    # VALIDATORS
    # ======================================================

    @field_validator(
        "gemini_api_key",
        "groq_api_key",
        "openrouter_api_key",
        "cerebras_api_key",
        "tavily_api_key",
        "elevenlabs_api_key",
        "openweather_api_key",
        "news_api_key",
        "google_maps_api_key",
        mode="after",
    )
    @classmethod
    def validate_api_key(
        cls,
        value: SecretStr | None,
    ) -> SecretStr | None:
        if value is None:
            return value

        if not value.get_secret_value().strip():
            raise ValueError("API key cannot be empty.")

        return value

    @field_validator("log_level", mode="after")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        value = value.upper()

        valid = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if value not in valid:
            raise ValueError(f"Invalid log level: {value}")

        return value

    @field_validator("app_env", mode="after")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        value = value.lower()

        valid = {
            "development",
            "production",
            "staging",
            "test",
        }

        if value not in valid:
            raise ValueError(f"Invalid environment: {value}")

        return value


def load_settings() -> Settings:
    """
    Load validated application settings.
    """

    try:
        return Settings()

    except ValidationError as exc:
        missing_fields = [
            str(err.get("loc", [""])[0]).lower()
            for err in exc.errors()
        ]
        if "gemini_api_key" in missing_fields:
            logger.error("GEMINI_API_KEY is missing. Add it to the .env file.")
            raise NovaConfigurationError(
                "GEMINI_API_KEY is missing. Add it to the .env file."
            ) from exc

        logger.exception("Configuration Error")
        raise NovaConfigurationError(
            "NOVA failed to load configuration.\n"
            "Check your .env file."
        ) from exc


settings = load_settings()

