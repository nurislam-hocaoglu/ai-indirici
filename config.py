"""
Centralized configuration using Pydantic Settings.
All values loaded from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str
    ALLOWED_USER_IDS: list[int] = []  # empty = allow all (not recommended)
    ADMIN_CHAT_ID: int  # receives error logs and fallback notifications

    # --- TMDB ---
    TMDB_API_KEY: str

    # --- Sonarr ---
    SONARR_URL: str = "http://sonarr:8989"
    SONARR_API_KEY: str
    SONARR_QUALITY_PROFILE_ID: int = 1
    SONARR_LANGUAGE_PROFILE_ID: int = 1
    SONARR_ROOT_FOLDER: str = "/tv"

    # --- Bazarr ---
    BAZARR_URL: str = "http://bazarr:6767"
    BAZARR_API_KEY: str

    # --- Jellyfin ---
    JELLYFIN_URL: str = "http://jellyfin:8096"
    JELLYFIN_API_KEY: str

    # --- Webhook Server ---
    WEBHOOK_HOST: str = "0.0.0.0"
    WEBHOOK_PORT: int = 8080

    # --- Misc ---
    LOG_LEVEL: str = "INFO"
    SUBTITLE_LANGUAGE: str = "tr"


settings = Settings()
