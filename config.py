"""
Centralized configuration using Pydantic Settings.
All values loaded from environment variables / .env file.
"""

from pydantic import field_validator
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

    @field_validator("ALLOWED_USER_IDS", mode="before")
    def parse_allowed_users(cls, v: any) -> list[int]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    # --- TMDB ---
    TMDB_API_KEY: str

    # --- Radarr ---
    RADARR_URL: str = "http://radarr:7878"
    RADARR_API_KEY: str
    RADARR_QUALITY_PROFILE_ID: int = 1
    RADARR_ROOT_FOLDER: str = "/movies"

    # --- Bazarr ---
    BAZARR_URL: str = "http://bazarr:6767"
    BAZARR_API_KEY: str

    # --- Jellyfin ---
    JELLYFIN_URL: str = "http://jellyfin:8096"
    JELLYFIN_API_KEY: str

    # --- Webhook Server ---
    WEBHOOK_HOST: str = "0.0.0.0"
    WEBHOOK_PORT: int = 9090

    # --- Misc ---
    LOG_LEVEL: str = "INFO"
    SUBTITLE_LANGUAGE: str = "tr,en"
    SUBTITLE_PROFILE: str = "stand"


settings = Settings()
