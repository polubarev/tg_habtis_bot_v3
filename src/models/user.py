
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.enums import Language
from src.models.habit import HabitSchema


class CustomQuestion(BaseModel):
    """User-defined reflection question."""

    id: str
    text: str
    language: str = Language.EN.value
    active: bool = True


class UsageStats(BaseModel):
    """Per-user usage counters for bot features."""

    habits: int = 0
    dream: int = 0
    thought: int = 0
    reflection: int = 0


class UserProfile(BaseModel):
    """Complete user profile stored in Firestore."""

    telegram_user_id: int
    telegram_username: Optional[str] = None
    sheet_id: Optional[str] = None
    sheet_url: Optional[str] = None
    sheets_validated: bool = False
    habit_schema: HabitSchema = Field(default_factory=HabitSchema)
    custom_questions: list[CustomQuestion] = Field(default_factory=list)
    usage_stats: UsageStats = Field(default_factory=UsageStats)
    language: str = Language.EN.value
    timezone: str = "Europe/Moscow"
    reminder_time: Optional[str] = None
    reminder_enabled: bool = False
    reminder_task_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    onboarding_completed: bool = False
