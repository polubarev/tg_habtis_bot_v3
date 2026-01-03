from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackEntry(BaseModel):
    """User feedback captured from the settings menu."""

    telegram_user_id: int
    telegram_username: Optional[str] = None
    telegram_first_name: Optional[str] = None
    language: str = "en"
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
