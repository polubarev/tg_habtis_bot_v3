from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.models.enums import InputType


class HabitEntry(BaseModel):
    """A single habit entry to be written to Google Sheets."""

    date: date
    raw_diary: str
    diary: Optional[str] = None
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "telegram"
    input_type: InputType = InputType.TEXT

    def to_sheet_row(self, field_order: list[str]) -> list[Any]:
        row = [self.date.isoformat()]
        for field in field_order:
            if field == "raw_diary":
                row.append(self.raw_diary)
            elif field == "diary":
                row.append(self.diary or "")
            else:
                row.append(self.extra_fields.get(field, ""))
        return row


class DreamEntry(BaseModel):
    """A dream log entry."""

    timestamp: datetime
    date: date
    raw_text: str
    mood: Optional[str] = None
    is_lucid: Optional[bool] = None
    tags: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


class ThoughtEntry(BaseModel):
    """A lightweight note or thought entry."""

    timestamp: datetime
    raw_text: str
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = None


class ReflectionEntry(BaseModel):
    """Answers to custom reflection questions."""

    date: date
    answers: dict[str, str] = Field(default_factory=dict)