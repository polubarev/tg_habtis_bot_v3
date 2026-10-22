import pytest

from src.config.constants import DEFAULT_HABIT_SCHEMA
from src.models.habit import HabitFieldConfig, HabitSchema
from src.services.llm.extractors.habit_extractor import HabitExtractor


class FakeClient:
    _model = object()

    def __init__(self):
        self.schema = None
        self.messages = None

    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        return self

    async def ainvoke(self, messages):
        self.messages = messages
        return {"workout": True, "diary": "shortened"}


@pytest.mark.asyncio
async def test_extractor_requests_diary_and_custom_fields():
    client = FakeClient()
    schema = HabitSchema(fields={
        **DEFAULT_HABIT_SCHEMA.fields,
        "workout": HabitFieldConfig(type="boolean", description="Did I work out?"),
    })

    result = await HabitExtractor(client).extract("I worked out", schema=schema)

    assert result == {"workout": True, "diary": "shortened"}
    assert set(client.schema.model_fields) == {"workout", "diary"}
    assert client.messages[1].content == "I worked out"


@pytest.mark.asyncio
async def test_extractor_processes_diary_without_custom_fields():
    client = FakeClient()

    async def invoke(messages):
        return {"diary": "Long diary"}
    client.ainvoke = invoke
    result = await HabitExtractor(client).extract("Long diary", schema=DEFAULT_HABIT_SCHEMA)

    assert result == {"diary": "Long diary"}
    assert set(client.schema.model_fields) == {"diary"}
