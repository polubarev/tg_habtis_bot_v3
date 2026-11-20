import time
from contextvars import ContextVar
from typing import Any

import httpx
from pydantic import SecretStr

try:
    from langchain_openai import ChatOpenAI as ChatOpenAIType
    from openai import DefaultAsyncHttpxClient
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - optional import path compatibility
    ChatOpenAIType: Any = None  # type: ignore[no-redef]
    _IMPORT_ERROR = exc

from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

llm_http_timing: ContextVar[tuple[float, dict[str, int]] | None] = ContextVar(
    "llm_http_timing", default=None
)


async def _track_http_request(request: httpx.Request) -> None:
    timing = llm_http_timing.get()
    if timing is None:
        return
    started, metrics = timing
    metrics["http_request_start_ms"] = int((time.monotonic() - started) * 1000)

    async def track_transfer(event: str, _info: dict[str, Any]) -> None:
        # Only record milestones. Trace data can contain the authenticated request.
        if event.endswith(".send_request_body.complete"):
            metrics["http_request_sent_ms"] = int((time.monotonic() - started) * 1000)
        elif event.endswith(".receive_response_body.complete"):
            metrics["http_response_body_ms"] = int((time.monotonic() - started) * 1000)

    request.extensions["trace"] = track_transfer


async def _track_http_response(response: httpx.Response) -> None:
    timing = llm_http_timing.get()
    if timing is not None:
        started, metrics = timing
        metrics["http_response_headers_ms"] = int((time.monotonic() - started) * 1000)
        metrics["http_status"] = response.status_code


def diary_processing_timeout(text: str, base_seconds: float) -> float:
    """Allow full-diary generation time for long entries, with a bounded wait."""
    return max(base_seconds, min(180.0, base_seconds + max(0, len(text) - 8000) / 150))


class LLMClient:
    """OpenRouter LLM client wrapper."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model: Any = None
        if ChatOpenAIType is None:
            logger.warning(
                "LangChain ChatOpenAI not available; LLM calls disabled",
                error_type=type(_IMPORT_ERROR).__name__ if _IMPORT_ERROR else None,
            )
            return
        self._model = ChatOpenAIType(
            model=settings.llm_model,
            api_key=(
                SecretStr(settings.openrouter_api_key)
                if settings.openrouter_api_key is not None
                else None
            ),
            base_url=settings.openrouter_base_url,
            temperature=settings.llm_temperature,
            max_completion_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
            http_async_client=DefaultAsyncHttpxClient(
                timeout=settings.llm_timeout_seconds,
                event_hooks={"request": [_track_http_request], "response": [_track_http_response]},
            ),
            default_headers={
                "HTTP-Referer": "https://habits-diary-bot.app",
                "X-Title": "Habits Diary Bot",
            },
        )
        logger.info(
            "LLM client initialized",
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )

    @property
    def model(self) -> Any:
        if self._model is None:
            raise RuntimeError("LLM client is not configured")
        return self._model

    def with_structured_output(
        self, schema: type[Any], *, max_tokens: int | None = None, timeout: float | None = None,
    ) -> Any:
        if self._model is None:
            raise RuntimeError("LLM client is not configured")
        if max_tokens is not None:
            # Full diary output needs its own budget. A failed round has a visible fallback.
            request_timeout = timeout or get_settings().llm_timeout_seconds
            async_client = self._model.root_async_client.with_options(
                timeout=request_timeout, max_retries=0,
            )
            sync_client = self._model.root_client.with_options(
                timeout=request_timeout, max_retries=0,
            )
            model = self._model.model_copy(update={
                "max_tokens": max_tokens,
                "max_retries": 0,
                "request_timeout": request_timeout,
                "root_async_client": async_client,
                "async_client": async_client.chat.completions,
                "root_client": sync_client,
                "client": sync_client.chat.completions,
            })
            return model.with_structured_output(
                schema, method="json_schema", strict=True, include_raw=True,
            )
        return self._model.with_structured_output(schema)
