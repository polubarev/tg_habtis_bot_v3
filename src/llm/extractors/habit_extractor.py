
from typing import Any, Dict

from src.llm.client import LlmClient
from src.llm.prompts.habits import HABIT_EXTRACTION_SYSTEM_PROMPT
from src.models.habit import HabitSchema


class HabitExtractor:
    """Coordinates prompt construction and parsing for habit entries."""

    def __init__(self, client: LlmClient):
        self.client = client

    async def extract(self, schema: HabitSchema, raw_text: str, language: str = "ru") -> Dict[str, Any]:
        if not self.client.is_configured():
            raise RuntimeError("LLM client is not configured")
        messages = [
            {"role": "system", "content": HABIT_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ]
        response = await self.client.run_completion(messages, model="gpt-4o-mini")
        return response
