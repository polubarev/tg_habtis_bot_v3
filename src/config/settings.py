from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Habits Diary Bot"
    app_version: str = "2.0.0"
    app_commit_sha: str = "unknown"
    debug: bool = False
    log_level: str = "INFO"

    # Google Cloud
    gcp_project_id: str | None = None
    gcp_region: str = "europe-west1"
    google_credentials_path: str | None = None

    # Telegram
    telegram_bot_token: str | None = None
    telegram_bot_token_debug: str | None = None
    telegram_webhook_url: Optional[str] = None
    telegram_webhook_url_debug: Optional[str] = None
    telegram_webhook_secret: str = Field(default="")
    admin_telegram_ids: str = ""
    reminders_dispatch_url: Optional[str] = None
    reminders_dispatch_url_debug: Optional[str] = None
    reminders_queue_name: str = "reminders"
    reminders_dispatch_secret: str = Field(default="")
    transcription_dispatch_url: Optional[str] = None
    transcription_dispatch_url_debug: Optional[str] = None
    transcription_queue_name: str = "transcriptions"
    transcription_dispatch_secret: str = Field(default="")

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
    firestore_collection_feedback: str = "feedback"
    firestore_collection_usage_events: str = "usage_events"
    firestore_collection_transcription_batches: str = "transcription_batches"
    firestore_collection_text_entry_collections: str = "text_entry_collections"

    # Session
    session_ttl_minutes: int = 60
    text_entry_max_utf16_units: int = 30_000

    # Rate limiting
    rate_limit_requests_per_minute: int = 30
    # Cloud Tasks fires a handful of dispatches per user per day; this only needs
    # to be high enough to absorb legitimate retries.
    reminders_dispatch_rate_limit_per_minute: int = 10

    # External operation timeouts
    operation_timeout_seconds: int = 25
    telegram_download_timeout_seconds: int = 30
    transcription_timeout_seconds: int = 60
    llm_timeout_seconds: int = 45
    sheets_timeout_seconds: int = 25

    # Batch transcription
    transcription_max_items: int = 10
    transcription_max_file_bytes: int = 20 * 1024 * 1024
    transcription_max_duration_seconds: int = 3600
    transcription_task_deadline_seconds: int = 1800
    transcription_task_max_attempts: int = 5

    @model_validator(mode="after")
    def apply_legacy_operation_timeout(self) -> "Settings":
        """Use the legacy shared timeout for stages without explicit overrides."""

        configured_fields = self.model_fields_set
        if "operation_timeout_seconds" not in configured_fields:
            return self
        for field_name in (
            "telegram_download_timeout_seconds",
            "transcription_timeout_seconds",
            "llm_timeout_seconds",
            "sheets_timeout_seconds",
        ):
            if field_name not in configured_fields:
                setattr(self, field_name, self.operation_timeout_seconds)
        return self

    def get_telegram_bot_token(self) -> Optional[str]:
        if self.debug and self.telegram_bot_token_debug:
            return self.telegram_bot_token_debug
        return self.telegram_bot_token

    def get_telegram_webhook_url(self) -> Optional[str]:
        if self.debug and self.telegram_webhook_url_debug:
            return self.telegram_webhook_url_debug
        return self.telegram_webhook_url

    def get_reminders_dispatch_url(self) -> Optional[str]:
        if self.debug and self.reminders_dispatch_url_debug:
            return self.reminders_dispatch_url_debug
        return self.reminders_dispatch_url

    def get_transcription_dispatch_url(self) -> Optional[str]:
        if self.debug and self.transcription_dispatch_url_debug:
            return self.transcription_dispatch_url_debug
        return self.transcription_dispatch_url

    def get_admin_telegram_ids(self) -> set[int]:
        ids: set[int] = set()
        for raw_id in self.admin_telegram_ids.split(","):
            raw_id = raw_id.strip()
            if raw_id.isdigit():
                ids.add(int(raw_id))
        return ids


@lru_cache()
def get_settings() -> "Settings":
    """Get cached settings instance."""

    return Settings()
