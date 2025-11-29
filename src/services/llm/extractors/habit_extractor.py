
from typing import Any, Dict

from src.config.constants import DEFAULT_HABIT_SCHEMA
from src.core.exceptions import ExtractionError
from src.core.logging import get_logger
from src.services.llm.client import LLMClient
from src.services.llm.prompts.habits import HABIT_EXTRACTION_SYSTEM_PROMPT

logger = get_logger(__name__)


class HabitExtractor:
    """Coordinates prompt construction and parsing for habit entries."""

    def __init__(self, client: LLMClient):
        self.client = client

    async def extract(self, raw_text: str, language: str = "ru", schema=DEFAULT_HABIT_SCHEMA) -> Dict[str, Any]:
        if self.client._model is None:
            raise ExtractionError("LLM client is not configured")

        messages = [
            {"role": "system", "content": HABIT_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ]

        # If LangChain model supports async invoke
        try:
            chain = self.client.with_structured_output(dict)
            result = await chain.ainvoke(messages)
            return result  # type: ignore[return-value]
        except Exception as exc:
            logger.warning("Habit extraction failed", error=str(exc))
            raise ExtractionError("Habit extraction failed") from exc
