
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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
