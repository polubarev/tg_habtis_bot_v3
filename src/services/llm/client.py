from typing import Any

from pydantic import SecretStr

try:
    from langchain_openai import ChatOpenAI as ChatOpenAIType
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - optional import path compatibility
    ChatOpenAIType: Any = None  # type: ignore[no-redef]
    _IMPORT_ERROR = exc

from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


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
