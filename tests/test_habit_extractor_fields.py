import pytest

from src.config.constants import DEFAULT_HABIT_SCHEMA
from src.models.habit import HabitFieldConfig, HabitSchema
from src.services.llm.extractors.habit_extractor import HabitExtractor


class FakeClient:
    _model = object()

    def __init__(self):
        self.schema = None
        self.messages = None

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    async def ainvoke(self, messages):
        self.messages = messages
        return {"workout": True, "diary": "shortened", "raw_record": "rewritten"}


@pytest.mark.asyncio
async def test_extractor_requests_only_custom_habit_fields():
    client = FakeClient()
    schema = HabitSchema(fields={
        **DEFAULT_HABIT_SCHEMA.fields,
        "workout": HabitFieldConfig(type="boolean", description="Did I work out?"),
    })

    result = await HabitExtractor(client).extract("I worked out", schema=schema)

    assert result == {"workout": True}
    assert set(client.schema.model_fields) == {"workout"}
    assert "do not return or rewrite" in client.messages[0].content.lower()
    assert '"diary"' not in client.messages[1].content
    assert '"raw_record"' not in client.messages[1].content


@pytest.mark.asyncio
async def test_extractor_skips_llm_when_only_diary_is_configured():
    client = FakeClient()

    result = await HabitExtractor(client).extract("Long diary", schema=DEFAULT_HABIT_SCHEMA)

    assert result == {}
    assert client.schema is None
