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

    def to_sheet_row(self, field_order: list[str], base_header: list[str] | None = None) -> list[Any]:
        """Convert entry to row aligned with header."""

        base_header = base_header or ["date", "raw_diary", "diary"]
        row: list[Any] = []
        for field in base_header:
            if field == "timestamp":
                row.append(self.created_at.isoformat())
            elif field == "date":
                row.append(self.date.isoformat())
            elif field == "raw_diary":
                row.append(self.raw_diary)
            elif field == "diary":
                row.append(self.diary or "")
            else:
                row.append(self.extra_fields.get(field, ""))
        for field in field_order:
            if field in base_header:
                continue
            row.append(self.extra_fields.get(field, ""))
        return row


class DreamEntry(BaseModel):
    """A dream log entry."""

    timestamp: datetime
    date: date
    raw_text: str


class ThoughtEntry(BaseModel):
    """A lightweight note or thought entry."""

    timestamp: datetime
    date: date
    raw_text: str


class ReflectionEntry(BaseModel):
    """Answers to custom reflection questions."""

    date: date
    answers: dict[str, str] = Field(default_factory=dict)
