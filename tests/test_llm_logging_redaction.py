"""Regression guard for SEC-2: user diary content must never reach the logs."""

from types import SimpleNamespace

import pytest

from src.services.llm.extractors import reflection_extractor as reflection_module
from src.services.llm.extractors.reflection_extractor import ReflectionExtractor
from src.services.llm.extractors import habit_extractor as habit_module
from src.services.llm.extractors.habit_extractor import HabitExtractor
from src.models.habit import HabitFieldConfig, HabitSchema

SECRET_TEXT = "today I relapsed and told nobody about it"


class RecordingLogger:
    """Captures every positional and keyword value passed to the logger."""

    def __init__(self) -> None:
        self.records: list[str] = []

    def _record(self, *args, **kwargs) -> None:
        self.records.append(repr(args) + repr(kwargs))

    info = _record
    warning = _record
    debug = _record
    error = _record

    def contains(self, needle: str) -> bool:
        return any(needle in record for record in self.records)


class FakeModel:
    async def ainvoke(self, _messages):
        return SimpleNamespace(content='{"How was today?": "fine"}', usage_metadata={})


class FakeStructuredClient:
    _model = object()

    def with_structured_output(self, _schema):
        return self

    async def ainvoke(self, _messages):
        return {"private_field_name": "private value", "diary": "fine"}


@pytest.mark.asyncio
async def test_reflection_extract_does_not_log_raw_text(monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr(reflection_module, "logger", recorder)

    client = SimpleNamespace(_model=FakeModel(), model=FakeModel())
    extractor = ReflectionExtractor(client)

    result = await extractor.extract(SECRET_TEXT, ["How was today?"], language="en")

    assert result == {"How was today?": "fine"}
    assert recorder.records, "expected the extractor to log something"
    assert not recorder.contains(SECRET_TEXT), (
        "raw reflection text leaked into a log record"
    )


@pytest.mark.asyncio
async def test_reflection_extract_does_not_log_question_text(monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr(reflection_module, "logger", recorder)

    client = SimpleNamespace(_model=FakeModel(), model=FakeModel())
    extractor = ReflectionExtractor(client)

    await extractor.extract(SECRET_TEXT, ["How was today?"], language="en")

    assert not recorder.contains("How was today?"), (
        "user-configured reflection questions leaked into a log record"
    )


@pytest.mark.asyncio
async def test_habit_extract_logs_counts_not_content_or_custom_field_names(monkeypatch):
    recorder = RecordingLogger()
    monkeypatch.setattr(habit_module, "logger", recorder)
    extractor = HabitExtractor(FakeStructuredClient())
    schema = HabitSchema(
        fields={
            "private_field_name": HabitFieldConfig(
                type="string", description="a private custom description"
            )
        }
    )

    result = await extractor.extract(SECRET_TEXT, schema=schema)

    assert result["private_field_name"] == "private value"
    assert not recorder.contains(SECRET_TEXT)
    assert not recorder.contains("private_field_name")
    assert not recorder.contains("private value")
    assert not recorder.contains("a private custom description")
