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


class LLMClient:
    """OpenRouter LLM client wrapper."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model: Any = None
        if ChatOpenAIType is None:
            logger.warning(
                "LangChain ChatOpenAI not available; LLM calls disabled",
                error=str(_IMPORT_ERROR) if _IMPORT_ERROR else None,
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

    def with_structured_output(self, schema: type[Any]) -> Any:
        if self._model is None:
            raise RuntimeError("LLM client is not configured")
        return self._model.with_structured_output(schema)
