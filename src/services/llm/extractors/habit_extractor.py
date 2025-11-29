
from typing import Any, Dict, Optional

from pydantic import create_model

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

    def _build_model(self, schema) -> Optional[type]:
        """Build a loose Pydantic model from habit schema fields."""

        if not schema or not getattr(schema, "fields", None):
            return None
        fields = {}
        for name in schema.fields.keys():
            fields[name] = (Optional[Any], None)
        # always include diary/raw_diary as optional in structured output
        fields.setdefault("raw_diary", (Optional[str], None))
        fields.setdefault("diary", (Optional[str], None))
        try:
            return create_model("HabitExtraction", **fields)  # type: ignore[arg-type]
        except Exception:
            return None

    async def extract(self, raw_text: str, language: str = "ru", schema=DEFAULT_HABIT_SCHEMA) -> Dict[str, Any]:
        if self.client._model is None:
            raise ExtractionError("LLM client is not configured")

        schema_dict = schema.model_dump() if hasattr(schema, "model_dump") else {}
        structured_model = self._build_model(schema)
        messages = [
            {"role": "system", "content": HABIT_EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Language: {language}\n"
                    f"Schema:\n{schema_dict}\n"
                    f"Text:\n{raw_text}\n"
                    "Return JSON only with fields from schema."
                ),
            },
        ]

        try:
            chain = self.client.with_structured_output(structured_model or dict)
            result = await chain.ainvoke(messages)
            if structured_model and hasattr(result, "model_dump"):
                return result.model_dump()
            return result or {}
        except Exception as exc:
            logger.warning("Habit extraction failed", error=str(exc))
            # fallback minimal structure
            return {"raw_diary": raw_text, "diary": raw_text}
