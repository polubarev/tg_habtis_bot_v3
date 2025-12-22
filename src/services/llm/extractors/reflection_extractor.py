import asyncio
from typing import Any, Dict, List

import httpx
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from src.core.exceptions import ExternalResponseError, ExternalTimeoutError
from src.core.logging import get_logger
from src.services.llm.client import LLMClient
from src.services.llm.prompts.reflections import REFLECTION_EXTRACTION_SYSTEM_PROMPT

logger = get_logger(__name__)


class ReflectionExtractor:
    """Extract answers to reflection questions from freeform text."""

    def __init__(self, client: LLMClient):
        self.client = client

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
            return True
        message = str(exc).lower()
        return "timeout" in message or "timed out" in message

    async def extract(self, raw_text: str, questions: List[str], language: str = "en") -> Dict[str, str]:
        if self.client._model is None:
            raise RuntimeError("LLM client is not configured")

        messages = [
            SystemMessage(content=REFLECTION_EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Language: {language}\n"
                    f"Questions:\n" + "\n".join(f"- {q}" for q in questions) + "\n"
                    f"User reply:\n{raw_text}\n"
                    "Return only the JSON object mapping each question text to its answer."
                )
            ),
        ]
        logger.info(messages)
        try:
            # Use raw model call to avoid structured-output schema issues with dict
            result = await self.client.model.ainvoke(messages)
            content = result.content if isinstance(result, AIMessage) else getattr(result, "content", result)

            def _to_str(val: Any) -> str:
                if isinstance(val, str):
                    return val
                if isinstance(val, list):
                    # gemini on LangChain returns list[{"type":"text","text":...}]
                    parts = []
                    for item in val:
                        if isinstance(item, dict) and "text" in item:
                            parts.append(str(item["text"]))
                        else:
                            parts.append(str(item))
                    return "\n".join(parts)
                if isinstance(val, dict) and "text" in val:
                    return str(val.get("text"))
                return str(val)

            text_content = _to_str(content)

            payload = {}
            try:
                import json

                payload = json.loads(text_content)
            except Exception:
                # try to extract JSON substring
                if isinstance(text_content, str) and "{" in text_content and "}" in text_content:
                    try:
                        snippet = text_content[text_content.find("{") : text_content.rfind("}") + 1]
                        payload = json.loads(snippet)
                    except Exception as exc:
                        raise ExternalResponseError("Invalid reflection response") from exc
                else:
                    raise ExternalResponseError("Invalid reflection response")
            logger.info(
                "Reflection LLM response",
                extra={"keys": list(payload.keys()) if isinstance(payload, dict) else None},
            )
            if not isinstance(payload, dict):
                raise ExternalResponseError("Reflection response was not a JSON object")
            return payload
        except ExternalTimeoutError:
            raise
        except ExternalResponseError:
            raise
        except Exception as exc:
            logger.warning("Reflection extraction failed", error=str(exc))
            if self._is_timeout_error(exc):
                raise ExternalTimeoutError("Reflection request timed out") from exc
            raise ExternalResponseError("Reflection request failed") from exc
