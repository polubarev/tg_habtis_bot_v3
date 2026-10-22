
import asyncio
import time
from typing import Any, Dict, Literal, Optional
import json
import re

import httpx
from pydantic import BaseModel, ConfigDict, Field, create_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.config.constants import DEFAULT_HABIT_SCHEMA
from src.config.settings import get_settings
from src.core.analytics import log_event
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, ExtractionError
from src.core.logging import get_logger
from src.models.habit import HabitFieldConfig, HabitSchema
from src.services.llm.client import LLMClient, diary_processing_timeout
from src.services.llm.prompts.habits import HABIT_EXTRACTION_SYSTEM_PROMPT

logger = get_logger(__name__)


class HabitExtractor:
    """Coordinates prompt construction and parsing for habit entries."""

    def __init__(self, client: LLMClient):
        self.client = client

    def _type_annotation(self, field_config: HabitFieldConfig | Dict[str, Any]) -> Any:
        """Resolve type annotation based on field configuration.
        Maps field type strings to Python types for Pydantic model creation.
        """
        if not field_config:
            return str
        
        # Handle both dict and HabitFieldConfig objects
        if isinstance(field_config, HabitFieldConfig):
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
        elif ft in {"integer", "int"}:
            return int
        elif ft in {"number", "float", "double", "decimal"}:
            return float
        elif ft in {"boolean", "bool"}:
            return bool
        elif ft in {"list"}:
            cleaned = [str(opt) for opt in (options or []) if str(opt).strip()]
            if cleaned:
                literal_type: Any = Literal.__getitem__(tuple(cleaned))
                return list[literal_type] if allow_multiple else literal_type
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

    def _build_model(self, schema: HabitSchema) -> type[BaseModel] | None:
        """All enabled fields are required in the response; unknown habits are null."""
        fields: dict[str, Any] = {}
        for name, cfg in schema.fields.items():
            if name in {"timestamp", "date", "raw_record", "diary", "entry_id",
                        "input_type", "field_order", "defaulted_fields"}:
                continue
            constraints: dict[str, Any] = {"description": cfg.description}
            py_type = self._type_annotation(cfg)
            if py_type in (int, float):
                if cfg.minimum is not None:
                    constraints["ge"] = cfg.minimum
                if cfg.maximum is not None:
                    constraints["le"] = cfg.maximum
            fields[name] = (Optional[py_type], Field(..., **constraints))
        if schema.include_diary:
            fields["diary"] = (str, Field(..., description="Full current diary, without summarizing"))
        if not fields:
            return None
        return create_model("HabitExtraction", __config__=ConfigDict(extra="forbid"), **fields)

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
            return True
        message = str(exc).lower()
        return "timeout" in message or "timed out" in message

    async def extract(
        self, raw_text: str, language: str = "ru", schema=DEFAULT_HABIT_SCHEMA,
        *, history: list[dict[str, str]] | None = None,
        previous_diary: str | None = None,
        new_text: str | None = None,
    ) -> Dict[str, Any]:
        schema_for_llm = self._resolve_schema(schema)
        structured_model = self._build_model(schema_for_llm)
        if structured_model is None:
            return {}
        if self.client._model is None:
            raise ExtractionError("LLM client is not configured")
        turns = history if history is not None else [{"role": "user", "content": raw_text}]
        fields_for_prompt = {
            name: cfg.model_dump(exclude={"default"})
            for name, cfg in schema_for_llm.fields.items()
            if name in structured_model.model_fields and name != "diary"
        }
        instructions = (
            f"{HABIT_EXTRACTION_SYSTEM_PROMPT}\nLanguage: {language}\n"
            f"Diary enabled: {schema_for_llm.include_diary}\n"
            f"Configured habits: {json.dumps(fields_for_prompt, ensure_ascii=False)}"
        )
        messages = [SystemMessage(content=instructions)] + [
            AIMessage(content=turn["content"]) if turn["role"] == "assistant"
            else HumanMessage(content=turn["content"])
            for turn in turns
        ]
        # Conservative UTF-8 budget covers even long Russian text, JSON escaping
        # and reasoning overhead. The provider's 65k cap is checked via finish_reason.
        max_tokens = min(65_536, max(
            get_settings().llm_max_tokens, 4096,
            len(raw_text.encode("utf-8")) + len(json.dumps(fields_for_prompt)) + 2048,
        ))
        logger.info("Habit LLM request", language=language,
                    schema_field_count=len(structured_model.model_fields),
                    text_length=len(raw_text), max_tokens=max_tokens)
        started = time.monotonic()
        ok = False
        try:
            chain = self.client.with_structured_output(
                structured_model, max_tokens=max_tokens,
                timeout=diary_processing_timeout(raw_text, get_settings().llm_timeout_seconds),
            )
            result = await chain.ainvoke(messages)
            if isinstance(result, dict) and "raw" in result and "parsed" in result:
                raw = result["raw"]
                metadata = getattr(raw, "response_metadata", {}) or {}
                extra = getattr(raw, "additional_kwargs", {}) or {}
                if metadata.get("finish_reason") not in {None, "stop"} or extra.get("refusal"):
                    raise ExternalResponseError("Incomplete or refused structured output")
                if result.get("parsing_error") or result["parsed"] is None:
                    raise ExternalResponseError("Invalid structured output")
                # Do not accept a partial JSON object repaired by a tolerant parser.
                content = getattr(raw, "content", None)
                result = json.loads(content) if isinstance(content, str) else result["parsed"]
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            payload = structured_model.model_validate(result).model_dump()
            if schema_for_llm.include_diary:
                latest_input = new_text if new_text is not None else raw_text
                if fields_only_input(latest_input, schema_for_llm):
                    payload["diary"] = previous_diary or ""
                elif not payload["diary"].strip():
                    raise ExternalResponseError("Empty diary for narrative input")
                if "[Update]" in payload["diary"]:
                    raise ExternalResponseError("Generated diary contains technical markers")
            ok = True
            return payload
        except (ExternalTimeoutError, ExternalResponseError):
            raise
        except Exception as exc:
            logger.warning("Habit extraction failed", error_type=type(exc).__name__)
            if self._is_timeout_error(exc):
                raise ExternalTimeoutError("LLM request timed out") from exc
            raise ExternalResponseError("LLM request failed") from exc
        finally:
            log_event("llm.call", extractor="habit", model=get_settings().llm_model,
                      latency_ms=int((time.monotonic() - started) * 1000), ok=ok)


def fields_only_input(text: str, schema: HabitSchema) -> bool:
    """Conservative guard for bare assignments, never general narrative mentions.

    Richer commands remain the model's responsibility. In particular sentences
    about sleeping, exercise or feelings do not match this grammar.
    """
    names = {name.replace("_", " ") for name in schema.fields if name != "diary"}
    aliases = {
        "настроение": {"настроение", "mood"},
        "важность дня": {"важность дня", "важность", "importance", "day importance"},
        "mood": {"mood", "настроение"},
        "importance": {"importance", "day importance", "важность дня", "важность"},
    }
    for name in list(names):
        names.update(aliases.get(name.casefold(), set()))
    if not names:
        return False
    value = text.casefold().replace("_", " ").strip()
    explicitly_fields_only = bool(re.search(r"это тоже только поля|fields only", value))
    if explicitly_fields_only:
        value = re.sub(r"это тоже только поля|fields only", "", value)
        if "утренняя зарядка" in names:
            value = re.sub(r"утренней зарядки не было", "", value)
        if "сон часы" in names:
            value = re.sub(r"спал \d+(?:[.,]\d+)? часов", "", value)
        if "тренировка" in names:
            value = re.sub(r"тренировок (?=\d)", "тренировка ", value)
    value = re.sub(
        r"поправь только поля|сам дневник не меняй|пока только значения полей|"
        r"рассказа про день нет|update only (?:the )?fields|leave (?:the )?diary unchanged",
        "", value,
    )
    name_pattern = "|".join(re.escape(name.casefold()) for name in sorted(names, key=len, reverse=True))
    assignment = rf"(?:{name_pattern})\s*[:=]?\s*(?:-?\d+(?:[.,]\d+)?|true|false|да|нет|null)"
    value, count = re.subn(assignment, "", value)
    return count > 0 and not re.sub(r"[\s,.;:!—-]|\b(?:и|and)\b", "", value)
