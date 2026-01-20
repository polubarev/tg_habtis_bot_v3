
import asyncio
from typing import Any, Dict, Optional, Literal
import json

import httpx
from pydantic import create_model
from langchain_core.messages import HumanMessage, SystemMessage

from src.config.constants import DEFAULT_HABIT_SCHEMA
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, ExtractionError
from src.core.logging import get_logger
from src.models.habit import HabitSchema
from src.services.llm.client import LLMClient
from src.services.llm.prompts.habits import HABIT_EXTRACTION_SYSTEM_PROMPT

logger = get_logger(__name__)


class HabitExtractor:
    """Coordinates prompt construction and parsing for habit entries."""

    def __init__(self, client: LLMClient):
        self.client = client

    def _type_annotation(self, field_config: Dict[str, Any]) -> Any:
        """Resolve type annotation based on field configuration.
        Maps field type strings to Python types for Pydantic model creation.
        """
        if not field_config:
            return str
        
        # Handle both dict and HabitFieldConfig objects
        if hasattr(field_config, "type"):
            field_type = field_config.type
            options = getattr(field_config, "options", None)
            allow_multiple = bool(getattr(field_config, "allow_multiple", False))
        else:
            field_type = field_config.get("type", "string")
            options = field_config.get("options")
            allow_multiple = bool(field_config.get("allow_multiple", False))
        
        # Normalize type string (handle list of types)
        if isinstance(field_type, list) and field_type:
            field_type = field_type[0]
        
        ft = str(field_type).lower()
        
        # Map to Python types
        if ft in {"string", "text", "str"}:
            return str
        elif ft in {"integer", "int", "number"}:
            return int
        elif ft in {"float", "double", "decimal"}:
            return float
        elif ft in {"boolean", "bool"}:
            return bool
        elif ft in {"list"}:
            cleaned = [str(opt) for opt in (options or []) if str(opt).strip()]
            if cleaned:
                literal = Literal[tuple(cleaned)]
                return list[literal] if allow_multiple else literal
            return list[str] if allow_multiple else str
        else:
            return str  # Default fallback

    def _resolve_schema(self, schema: Optional[HabitSchema]) -> HabitSchema:
        """Merge user schema with defaults (diary) without touching base technical fields."""

        base = DEFAULT_HABIT_SCHEMA.model_copy(deep=True)
        if schema is None:
            return base
        include_diary = getattr(schema, "include_diary", True)
        user_fields = getattr(schema, "fields", None) or {}
        if not include_diary:
            merged = schema.model_copy(deep=True)
            merged.fields.pop("diary", None)
            merged.include_diary = False
            return merged
        if not user_fields:
            return base
        merged = base.model_copy(deep=True)
        merged.fields.update(user_fields)
        merged.version = getattr(schema, "version", merged.version)
        merged.include_diary = True
        return merged

    def _build_model(self, schema: Optional[HabitSchema]) -> Optional[type]:
        """Build a loose Pydantic model from habit schema fields."""
        include_diary = getattr(schema, "include_diary", True)
        fields: dict[str, tuple[Any, Any]] = {}
        if include_diary:
            fields["diary"] = (Optional[Any], None)  # request diary summary when enabled
        if schema and getattr(schema, "fields", None):
            for name, field_config in schema.fields.items():
                py_type = self._type_annotation(field_config)
                fields[name] = (Optional[py_type], None)
        # always include raw_record as optional in structured output
        fields.setdefault("raw_record", (Optional[str], None))
        try:
            return create_model("HabitExtraction", **fields)  # type: ignore[arg-type]
        except Exception:
            return None

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
            return True
        message = str(exc).lower()
        return "timeout" in message or "timed out" in message

    async def extract(self, raw_text: str, language: str = "ru", schema=DEFAULT_HABIT_SCHEMA) -> Dict[str, Any]:
        if self.client._model is None:
            raise ExtractionError("LLM client is not configured")

        schema_for_llm = self._resolve_schema(schema)
        schema_dict = schema_for_llm.model_dump() if hasattr(schema_for_llm, "model_dump") else {}
        # keep descriptions/types for the model prompt
        fields_for_prompt = {
            name: cfg.model_dump() if hasattr(cfg, "model_dump") else cfg
            for name, cfg in (schema_for_llm.fields or {}).items()
        }
        for cfg in fields_for_prompt.values():
            if isinstance(cfg, dict):
                cfg.pop("default", None)
        structured_model = self._build_model(schema_for_llm)
        preview = (raw_text or "")[:500]
        logger.info(
            "Habit LLM request",
            extra={
                "language": language,
                "schema_fields": list(schema_dict.get("fields", {}).keys()),
                "text_preview": preview,
                "text_length": len(raw_text or ""),
            },
        )

        try:
            chain = self.client.with_structured_output(structured_model or dict)
            messages = [
                SystemMessage(content=HABIT_EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"Language: {language}\n"
                        "Schema (user-defined fields with descriptions):\n"
                        f"{json.dumps(fields_for_prompt, ensure_ascii=False)}\n"
                        f"User Raw record:\n{raw_text}\n"
                        "Return ONLY the structured JSON response matching the schema."
                    )
                ),
            ]
            logger.info(messages)
            result = await chain.ainvoke(messages)

            if structured_model and hasattr(result, "model_dump"):
                payload = result.model_dump()
            else:
                payload = result or {}
            logger.info(
                "Habit LLM response",
                extra={
                    "keys": list(payload.keys()) if isinstance(payload, dict) else None,
                    "preview": str(payload)[:500],
                },
            )
            if not isinstance(payload, dict):
                raise ExternalResponseError("LLM response was not a JSON object")
            return payload
        except ExternalTimeoutError:
            raise
        except ExternalResponseError:
            raise
        except Exception as exc:
            logger.warning("Habit extraction failed", error=str(exc))
            if self._is_timeout_error(exc):
                raise ExternalTimeoutError("LLM request timed out") from exc
            raise ExternalResponseError("LLM request failed") from exc
