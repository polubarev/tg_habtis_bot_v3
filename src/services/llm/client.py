
from typing import Optional

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.language_models import BaseChatModel
except Exception:  # pragma: no cover - optional import path compatibility
    ChatOpenAI = None
    BaseChatModel = object

from src.config.settings import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """OpenRouter LLM client wrapper."""

    def __init__(self):
        settings = get_settings()
        self._model: Optional[BaseChatModel] = None
        if ChatOpenAI is None:
            logger.warning("LangChain ChatOpenAI not available; LLM calls disabled")
            return
        self._model = ChatOpenAI(
            model=settings.llm_model,
            openai_api_key=settings.openrouter_api_key,
            openai_api_base=settings.openrouter_base_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
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
    def model(self):
        if self._model is None:
            raise RuntimeError("LLM client is not configured")
        return self._model

    def with_structured_output(self, schema: type):
        if self._model is None:
            raise RuntimeError("LLM client is not configured")
        return self._model.with_structured_output(schema)
