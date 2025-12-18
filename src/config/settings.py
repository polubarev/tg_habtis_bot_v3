from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Application
    app_name: str = "Habits Diary Bot"
    app_version: str = "2.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Google Cloud
    gcp_project_id: str | None = None
    gcp_region: str = "europe-west1"
    google_credentials_path: str | None = None

    # Telegram
    telegram_bot_token: str | None = None
    telegram_webhook_url: Optional[str] = None
    telegram_webhook_secret: str = Field(default="")

    # OpenRouter / LLM
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-3-5-sonnet"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000

    # Whisper / STT
    openai_api_key: str | None = None  # For Whisper API
    whisper_model: str = "whisper-1"

    # Firestore
    firestore_collection_users: str = "users"
    firestore_collection_sessions: str = "sessions"

    # Session
    session_ttl_minutes: int = 60

    # Rate limiting
    rate_limit_requests_per_minute: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> "Settings":
    """Get cached settings instance."""

    return Settings()
