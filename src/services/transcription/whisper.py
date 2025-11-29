
from typing import Optional

import httpx

from src.config.settings import get_settings
from src.core.exceptions import TranscriptionError
from src.core.logging import get_logger
from src.services.transcription.interfaces import ITranscriber, TranscriptionResult

logger = get_logger(__name__)


class WhisperClient(ITranscriber):
    """OpenAI Whisper API client for speech-to-text."""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._model = settings.whisper_model
        self._base_url = "https://api.openai.com/v1/audio/transcriptions"

    async def transcribe(
        self,
        audio_data: bytes,
        format: str = "ogg",
        language_hint: Optional[str] = None,
    ) -> TranscriptionResult:
        if not self._api_key:
            raise TranscriptionError("Whisper API key missing")

        files = {"file": (f"audio.{format}", audio_data)}
        data = {"model": self._model}
        if language_hint:
            data["language"] = language_hint

        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(self._base_url, headers=headers, data=data, files=files)
                response.raise_for_status()
                payload = response.json()
                text = payload.get("text")
                language = payload.get("language")
                return TranscriptionResult(text=text or "", language=language)
        except Exception as exc:  # pragma: no cover - networking
            logger.warning("Transcription failed", error=str(exc))
            raise TranscriptionError("Transcription failed") from exc
