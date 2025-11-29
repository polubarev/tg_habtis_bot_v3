
from typing import Any, Dict, Optional

from openai import AsyncOpenAI


class LlmClient:
    """Thin wrapper around OpenRouter-compatible OpenAI client."""

    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key
        self.client = None
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    def is_configured(self) -> bool:
        return bool(self.client)

    async def run_completion(self, messages: list[Dict[str, str]], model: str) -> dict[str, Any]:
        if not self.client:
            raise RuntimeError("LLM client is not configured")
        response = await self.client.chat.completions.create(model=model, messages=messages)
        return response.to_dict_recursive()
