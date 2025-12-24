from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    """Possible states in a conversation flow."""

    IDLE = "idle"
    HABITS_AWAITING_DATE = "habits_awaiting_date"
    HABITS_AWAITING_CONTENT = "habits_awaiting_content"
    HABITS_AWAITING_CONFIRMATION = "habits_awaiting_confirmation"
    HABITS_AWAITING_EDIT = "habits_awaiting_edit"
    DREAM_AWAITING_CONTENT = "dream_awaiting_content"
    DREAM_AWAITING_CONFIRMATION = "dream_awaiting_confirmation"
    THOUGHT_AWAITING_CONTENT = "thought_awaiting_content"
    THOUGHT_AWAITING_CONFIRMATION = "thought_awaiting_confirmation"
    REFLECT_ANSWERING_QUESTIONS = "reflect_answering_questions"
    REFLECT_AWAITING_CONFIRMATION = "reflect_awaiting_confirmation"
    CONFIG_AWAITING_SHEET_URL = "config_awaiting_sheet_url"
    CONFIG_EDITING_HABITS = "config_editing_habits"
    CONFIG_ADDING_QUESTION = "config_adding_question"
    CONFIG_TIMEZONE = "config_timezone"
    CONFIG_LANGUAGE = "config_language"
    CONFIG_REMINDER_TIME = "config_reminder_time"
    ONBOARDING_WELCOME = "onboarding_welcome"
    ONBOARDING_LANGUAGE = "onboarding_language"
    ONBOARDING_SHEET_SETUP = "onboarding_sheet_setup"
    ONBOARDING_HABIT_REVIEW = "onboarding_habit_review"


class SessionData(BaseModel):
    """Conversation session data stored in Firestore."""

    user_id: int
    state: ConversationState = ConversationState.IDLE
    selected_date: Optional[date] = None
    pending_entry: Optional[dict[str, Any]] = None
    current_question_index: Optional[int] = None
    reflection_answers: dict[str, str] = Field(default_factory=dict)
    temp_data: dict[str, Any] = Field(default_factory=dict)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def reset(self) -> None:
        """Reset session to idle state."""

        self.state = ConversationState.IDLE
        self.selected_date = None
        self.pending_entry = None
        self.current_question_index = None
        self.reflection_answers = {}
        self.temp_data = {}
