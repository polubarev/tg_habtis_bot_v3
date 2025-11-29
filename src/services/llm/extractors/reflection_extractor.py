from typing import Dict, List, Any

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from src.core.logging import get_logger
from src.services.llm.client import LLMClient
from src.services.llm.prompts.reflections import REFLECTION_EXTRACTION_SYSTEM_PROMPT

logger = get_logger(__name__)


class ReflectionExtractor:
    """Extract answers to reflection questions from freeform text."""

    def __init__(self, client: LLMClient):
        self.client = client

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
                    except Exception:
                        payload = {}
                else:
                    payload = {}
            logger.info(
                "Reflection LLM response",
                extra={"keys": list(payload.keys()) if isinstance(payload, dict) else None},
            )
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            logger.warning("Reflection extraction failed", error=str(exc))
            # fallback: empty answers
            return {q: "" for q in questions}
