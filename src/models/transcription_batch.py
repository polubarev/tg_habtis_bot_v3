from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TranscriptionMediaType(str, Enum):
    VOICE = "voice"
    AUDIO = "audio"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"


class TranscriptionItemStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptionBatchStatus(str, Enum):
    COLLECTING = "collecting"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TranscriptionBatchItem(BaseModel):
    index: int = 0
    message_id: int
    file_id: str
    file_unique_id: str
    media_type: TranscriptionMediaType
    file_format: str
    mime_type: Optional[str] = None
    file_size: int = 0
    duration_seconds: int = 0
    status: TranscriptionItemStatus = TranscriptionItemStatus.PENDING
    transcript: Optional[str] = None
    error_code: Optional[str] = None


class TranscriptionBatch(BaseModel):
    user_id: int
    chat_id: int
    batch_id: str = Field(default_factory=lambda: uuid4().hex)
    status: TranscriptionBatchStatus = TranscriptionBatchStatus.COLLECTING
    items: list[TranscriptionBatchItem] = Field(default_factory=list)
    total_duration_seconds: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=60)
    )
    queued_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    @property
    def is_collecting_expired(self) -> bool:
        if self.status != TranscriptionBatchStatus.COLLECTING:
            return False
        now = datetime.now(timezone.utc)
        if self.expires_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        return now > self.expires_at
