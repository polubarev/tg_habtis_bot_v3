
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Protocol

if False:  # pragma: no cover - typing only
    from src.models.transcription_batch import TranscriptionBatch, TranscriptionBatchItem


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""

    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration_seconds: Optional[float] = None


class ITranscriber(ABC):
    """Interface for speech-to-text services."""

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        format: str = "ogg",
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio to text."""
        raise NotImplementedError


class ITranscriptionTaskScheduler(Protocol):
    async def enqueue(self, user_id: int, batch_id: str) -> str:
        ...


class ITranscriptionBatchRepository(Protocol):
    async def get(self, user_id: int) -> "TranscriptionBatch | None":
        ...

    async def create_or_resume(
        self, user_id: int, chat_id: int, ttl_minutes: int
    ) -> "TranscriptionBatch":
        ...

    async def append_item(
        self,
        user_id: int,
        batch_id: str,
        item: "TranscriptionBatchItem",
        *,
        max_items: int,
        max_duration_seconds: int,
        ttl_minutes: int,
    ):
        ...

    async def clear(self, user_id: int, batch_id: str, ttl_minutes: int) -> "TranscriptionBatch":
        ...

    async def cancel(self, user_id: int, batch_id: str) -> "TranscriptionBatch":
        ...

    async def queue(self, user_id: int, batch_id: str) -> "TranscriptionBatch":
        ...

    async def claim(self, user_id: int, batch_id: str) -> "TranscriptionBatch | None":
        ...

    async def checkpoint_item(
        self,
        user_id: int,
        batch_id: str,
        index: int,
        *,
        transcript: str | None = None,
        error_code: str | None = None,
    ) -> "TranscriptionBatch":
        ...

    async def complete(self, user_id: int, batch_id: str) -> "TranscriptionBatch":
        ...

    async def mark_delivered_and_purge(
        self, user_id: int, batch_id: str
    ) -> "TranscriptionBatch":
        ...
