
import time
from typing import Optional

import httpx

from src.config.settings import get_settings
from src.core.analytics import log_event
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, TranscriptionError
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
        started = time.monotonic()
        audio_bytes = len(audio_data)
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(self._base_url, headers=headers, data=data, files=files)
                response.raise_for_status()
                try:
                    payload = response.json()
                except Exception as exc:
                    raise ExternalResponseError("Invalid transcription response") from exc
                text = payload.get("text")
                language = payload.get("language")
                if not isinstance(text, str) or not text.strip():
                    raise ExternalResponseError("Transcription response missing text")
                logger.info("Transcription result", language=language, text_length=len(text))
                log_event(
                    "transcription.call",
                    model=self._model,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    audio_bytes=audio_bytes,
                    language=language,
                    text_length=len(text),
                    ok=True,
                )
                return TranscriptionResult(text=text or "", language=language)
        except ExternalTimeoutError:
            log_event(
                "transcription.call",
                model=self._model,
                latency_ms=int((time.monotonic() - started) * 1000),
                audio_bytes=audio_bytes,
                ok=False,
                error="ExternalTimeoutError",
            )
            raise
        except ExternalResponseError:
            log_event(
                "transcription.call",
                model=self._model,
                latency_ms=int((time.monotonic() - started) * 1000),
                audio_bytes=audio_bytes,
                ok=False,
                error="ExternalResponseError",
            )
            raise
        except httpx.TimeoutException as exc:  # pragma: no cover - networking
            logger.warning("Transcription timeout", error=str(exc))
            log_event(
                "transcription.call",
                model=self._model,
                latency_ms=int((time.monotonic() - started) * 1000),
                audio_bytes=audio_bytes,
                ok=False,
                error="timeout",
            )
            raise ExternalTimeoutError("Transcription timed out") from exc
        except httpx.HTTPStatusError as exc:  # pragma: no cover - networking
            status = exc.response.status_code
            logger.warning("Transcription HTTP error", status=status, error=str(exc))
            log_event(
                "transcription.call",
                model=self._model,
                latency_ms=int((time.monotonic() - started) * 1000),
                audio_bytes=audio_bytes,
                ok=False,
                error=f"http_{status}",
            )
            if status in {408, 429, 500, 502, 503, 504}:
                raise ExternalTimeoutError("Transcription timed out") from exc
            raise ExternalResponseError("Transcription HTTP error") from exc
        except Exception as exc:  # pragma: no cover - networking
            logger.warning("Transcription failed", error=str(exc))
            log_event(
                "transcription.call",
                model=self._model,
                latency_ms=int((time.monotonic() - started) * 1000),
                audio_bytes=audio_bytes,
                ok=False,
                error=type(exc).__name__,
            )
            raise TranscriptionError("Transcription failed") from exc
