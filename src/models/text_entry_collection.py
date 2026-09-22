from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.enums import EntryType, InputType


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


class TextEntryCollectionStatus(str, Enum):
    COLLECTING = "collecting"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TextEntryPart(BaseModel):
    message_id: int
    text: str
    input_type: InputType = InputType.TEXT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TextEntryCollection(BaseModel):
    collection_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: int
    chat_id: int
    entry_type: EntryType
    status: TextEntryCollectionStatus = TextEntryCollectionStatus.COLLECTING
    parts: list[TextEntryPart] = Field(default_factory=list)
    total_utf16_units: int = 0
    status_message_id: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    @property
    def combined_text(self) -> str:
        return "\n\n".join(part.text for part in sorted(self.parts, key=lambda part: part.message_id))

    @property
    def combined_input_type(self) -> InputType:
        kinds = {part.input_type for part in self.parts}
        if not kinds or kinds == {InputType.TEXT}:
            return InputType.TEXT
        if kinds == {InputType.VOICE}:
            return InputType.VOICE
        return InputType.MIXED

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and datetime.now(timezone.utc) > self.expires_at)

    def refresh_expiry(self, ttl_minutes: int) -> None:
        self.updated_at = datetime.now(timezone.utc)
        self.expires_at = self.updated_at + timedelta(minutes=ttl_minutes)
