"""Real collection/handler/extractor/save path; only provider and I/O are fakes.

Scripted prose verifies orchestration and validation, not Gemini's writing quality.
The separate live evaluation records actual model responses for human review.
"""
import asyncio
from datetime import date
import html
import json
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
import httpx
import pytest

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError
from src.models.enums import EntryType, InputType
from src.models.habit import HabitFieldConfig, HabitSchema
from src.models.session import ConversationState, SessionData
from src.services.llm.client import LLMClient, diary_processing_timeout
from src.services.llm.extractors.habit_extractor import HabitExtractor
from src.services.telegram.handlers import habits
from src.services.telegram.handlers.entry_collection import (
    handle_entry_collection_callback, handle_entry_collection_text, start_entry_collection,
)
from src.services.telegram.utils import TELEGRAM_TEXT_CHUNK_SIZE, telegram_text_length
from tests.test_entry_collection_handlers import FakeBot, FakeDeps, FakeMessage, _update

FIXTURES = json.loads((Path(__file__).parents[1] /
                      "docs/evals/2026-10-22/main/fixtures.json").read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in FIXTURES["cases"]}


def evaluation_schema():
    fields = {}
    for name, cfg in FIXTURES["habitSchema"]["properties"].items():
        cfg = dict(cfg)
        if "array" in cfg["type"]:
            cfg.update(type="list", options=cfg["items"]["enum"], allow_multiple=True)
            cfg.pop("items")
        fields[name] = HabitFieldConfig(**cfg)
    return HabitSchema(fields=fields)


class StructuredClient:
    """Provider boundary returning the same envelope as LangChain include_raw."""
    _model = object()

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        self.options = kwargs
        return self

    async def ainvoke(self, messages):
        self.requests.append((messages, self.schema, self.options))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = await response()
        if isinstance(response, dict) and "raw" in response:
            return response
        return {"raw": AIMessage(content=json.dumps(response, ensure_ascii=False),
                                 response_metadata={"finish_reason": "stop"}),
                "parsed": response, "parsing_error": None}


def make_context(*responses, schema=None, language="ru"):
    deps = FakeDeps()
    deps.user_repo().profile.language = language
    deps.user_repo().profile.habit_schema = schema or evaluation_schema()
    deps._llm_client = StructuredClient(*responses)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=FakeBot())
    return deps, context


async def collect(context, text, *, voice=False, parts=None):
    for index, part in enumerate(parts or [text], start=1):
        await handle_entry_collection_text(
            _update(FakeMessage(part, index)), context, part,
            input_type=InputType.VOICE if voice else InputType.TEXT,
        )
    status = FakeMessage("status")
    await handle_entry_collection_callback(
        _update(status, callback_data="entry_collect:done"), context,
    )
    return status


async def start(context, selected="2026-10-22"):
    await start_entry_collection(_update(FakeMessage()), context, EntryType.HABIT,
                                 flow_context={"selected_date": selected})


async def add(context):
    await habits.handle_habits_confirm(
        _update(FakeMessage(), callback_data="habits_confirm:no"), context,
    )


async def confirm(context):
    await habits.handle_habits_confirm(
        _update(FakeMessage(), callback_data="habits_confirm:yes"), context,
    )


@pytest.mark.asyncio
async def test_first_draft_three_additions_then_save_and_retry():
    case = CASES["morning_and_ratings"]
    morning, ratings = case["turns"][1:]
    first = "Утром позавтракал овсянкой с грушей. Днём чинил настольную лампу, потерял один маленький винтик. Вечером играл в Mars с другом Борисом сорок две минуты."
    integrated = first.replace(" Днём", " Утром после завтрака сходил в магазин за батарейками ААА. На кассе вернули лишние семнадцать рублей, я отдал их обратно. Днём")
    mixed = "Пока Катя бегала, мастурбировал. Настроение 2, важность дня 2."
    final = integrated + "\n\nПока Катя бегала, мастурбировал."
    responses = [
        {"diary": first, **case["turns"][0]["expected"]},
        {"diary": integrated, **morning["expected"]},
        # The application must reject a rewrite of prose on a bare field command.
        {"diary": "UNWANTED REWRITE", **ratings["expected"]},
        {"diary": final, **ratings["expected"], "настроение": 2, "важность_дня": 2,
         "мастурбация": 1},
    ]
    deps, context = make_context(*responses)
    await start(context)
    inputs = [case["turns"][0]["text"], morning["text"], ratings["text"], mixed]
    for index, text in enumerate(inputs):
        status = await collect(context, text, voice=index == 1)
        session = await deps.session_repo().get(1)
        assert session.state == ConversationState.HABITS_AWAITING_CONFIRMATION
        assert session.pending_entry["raw_record"] == "\n\n".join(inputs[:index + 1])
        if index == 2:
            assert session.pending_entry["diary"] == integrated
            assert session.pending_entry["настроение"] == 2
        if index < 3:
            await add(context)
    pending = dict(session.pending_entry)
    assert pending["diary"] == final
    assert pending["input_type"] == "mixed"
    assert final.index("батарейками") < final.index("Днём")
    assert final in html.unescape("".join(t for t, _, _ in status.replies))
    assert "Настроение 2" not in final and "[Update]" not in final
    requests = deps.llm_client().requests
    assert len(requests) == 4
    assert [m.type for m in requests[-1][0]] == [
        "system", "human", "ai", "human", "ai", "human", "ai", "human",
    ]
    assert [m.content for m in requests[-1][0] if m.type == "human"] == inputs
    original_append = deps.sheets_client().append_habit_entry
    async def timeout(*args):
        raise ExternalTimeoutError("save timeout")
    deps.sheets_client().append_habit_entry = timeout
    await confirm(context)
    assert (await deps.session_repo().get(1)).pending_entry == pending
    deps.sheets_client().append_habit_entry = original_append
    await confirm(context)
    await confirm(context)  # A stale duplicate callback must not write twice.
    assert len(requests) == 4
    assert len(deps.sheets_client().appended) == 1
    saved = deps.sheets_client().appended[0][2]
    assert saved.diary == final and saved.raw_record == "\n\n".join(inputs)
    assert saved.entry_id == pending["entry_id"]
    assert saved.extra_fields["мастурбация"] == 1
    assert not (await deps.session_repo().get(1)).temp_data


@pytest.mark.asyncio
@pytest.mark.parametrize(("case_id", "diaries"), [
    ("explicit_corrections", [
        "Сегодня утром была одна тренировка — плавал в бассейне двадцать минут. Потом отнёс соседке её синий зонт. Настроение 4, важность дня 3, спал 6,5 часов. Зарядки не было.",
        "Бассейн был вчера, сегодня я не тренировался. Потом отнёс соседке её синий зонт именно сегодня. Настроение 2, важность дня 3, спал 6,5 часов. Зарядки не было.",
        "Бассейн был вчера, сегодня я не тренировался. Потом отнёс соседке её синий зонт именно сегодня. Настроение 2, важность дня 5, спал 6,5 часов. Зарядки не было. Вечером заметил, что молния на рюкзаке снова заедает. Пока не чинил.",
    ]),
    ("sensitive_and_uncertain", [
        "Ну, живот вроде чуть-чуть отпускает, но я не уверен, что стало лучше. Врач никакого диагноза пока не назвал. Пока жена бегала, один раз подрочил. Она оставила на столе записку «суп в зелёной кастрюле», я сначала её не заметил. Секса сегодня не было, минета тоже не было. Я не тренировался.",
        "Ну, живот вроде чуть-чуть отпускает, но я не уверен, что стало лучше. Врач никакого диагноза пока не назвал. Пока жена бегала, один раз подрочил. Она оставила на столе записку «суп в зелёной кастрюле», я сначала её не заметил. Минета не было. Я не тренировался. Вечером мы с женой поговорили про отпуск, решили пока ничего не бронировать. Секс был один раз перед сном.",
    ]),
    ("ambiguous_time", [
        "Утром возился с дверной ручкой. После обеда дремал на диване, не знаю сколько. Вечером смотрел дождь из окна. Мне было грустно, но оценку настроению я не давал. Алкоголь не пил.",
        "Утром возился с дверной ручкой. После обеда дремал на диване, не знаю сколько. Вечером смотрел дождь из окна. Мне было грустно, но оценку настроению я не давал. Алкоголь не пил.\n\nЕщё созвонился с другом Лёшей, он рассказал про свою новую собаку. Уже не помню, утром или вечером это было. С грустью этот звонок никак не связан.",
    ]),
])
async def test_fixture_corrections_preserve_complete_prose_through_save(case_id, diaries):
    turns = CASES[case_id]["turns"]
    deps, context = make_context(*[
        {"diary": diary, **turn["expected"]} for turn, diary in zip(turns, diaries)
    ])
    await start(context)
    for index, turn in enumerate(turns):
        await collect(context, turn["text"])
        pending = (await deps.session_repo().get(1)).pending_entry
        assert pending["diary"] == diaries[index]
        for key, value in turn["expected"].items():
            assert pending[key] == value
        if index < len(turns) - 1:
            await add(context)
    await confirm(context)
    assert deps.sheets_client().appended[0][2].diary == diaries[-1]
    assert len(deps.llm_client().requests) == len(turns)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["append", "rewrite"])
async def test_saved_append_uses_diary_fields_and_same_row_rewrite_resets(action):
    schema = HabitSchema(fields={"mood": HabitFieldConfig(type="integer", description="Mood")})
    deps, context = make_context({"diary": "Saved prose.\n\nNew event.", "mood": 2}, schema=schema)
    existing = SimpleNamespace(row_index=7, raw_record="Saved source. [Update] mood 2",
                               entry_data={"diary": "Saved prose.", "mood": "2"})
    async def find(*args):
        return existing
    deps.sheets_client().find_latest_habit_entry = find
    await habits.handle_habits_date_callback(
        _update(FakeMessage(), callback_data="habits_date:today"), context,
    )
    await habits.handle_habits_existing_choice(
        _update(FakeMessage(), callback_data=f"habits_existing:{action}"), context,
    )
    if action == "rewrite":
        deps.llm_client().responses = [{"diary": "New event.", "mood": None}]
    await collect(context, "New event.")
    messages = deps.llm_client().requests[0][0][1:]
    if action == "append":
        assert [m.type for m in messages] == ["human", "ai", "human"]
        assert messages[0].content == existing.raw_record
        assert json.loads(messages[1].content) == {"diary": "Saved prose.", "mood": "2"}
    else:
        assert [m.content for m in messages] == ["New event."]
    await confirm(context)
    writes = deps.sheets_client().updated
    assert len(writes) == 1 and writes[0][1] == 7
    assert writes[0][3].diary == ("Saved prose.\n\nNew event." if action == "append" else "New event.")
    assert writes[0][3].raw_record == (
        existing.raw_record + "\n\nNew event." if action == "append" else "New event."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [
    asyncio.TimeoutError(), RuntimeError("HTTP 402"), {}, {"diary": ""},
    {"diary": "[Update] invented"},
    {"raw": AIMessage(content='{"diary":"cut', response_metadata={"finish_reason": "length"}),
     "parsed": {"diary": "cut"}, "parsing_error": None},
    {"raw": AIMessage(content="", additional_kwargs={"refusal": "blocked"}),
     "parsed": None, "parsing_error": None},
    {"raw": AIMessage(content='{"diary":"cut"', response_metadata={"finish_reason": "stop"}),
     "parsed": {"diary": "cut"}, "parsing_error": None},
])
@pytest.mark.parametrize("language", ["ru", "en"])
async def test_failures_preserve_raw_previous_diary_and_notice_on_preview_retry(failure, language):
    deps, context = make_context({"diary": "Prior prose."}, failure,
                                 schema=HabitSchema(), language=language)
    await start(context)
    await collect(context, "Prior source.")
    await add(context)
    status = await collect(context, "New complete addition.")
    session = await deps.session_repo().get(1)
    assert session.pending_entry["diary"] == "Prior prose.\n\nNew complete addition."
    assert session.pending_entry["raw_record"] == "Prior source.\n\nNew complete addition."
    msgs = MESSAGES_RU if language == "ru" else MESSAGES_EN
    assert msgs["diary_integration_failed"] in "".join(t for t, _, _ in status.replies)
    assert len(deps.llm_client().requests) == 2
    # Ready collection preview retry must retain the warning and not call the model.
    retried = FakeMessage()
    await handle_entry_collection_callback(
        _update(retried, callback_data="entry_collect:retry"), context,
    )
    assert msgs["diary_integration_failed"] in "".join(t for t, _, _ in retried.replies)
    assert len(deps.llm_client().requests) == 2


@pytest.mark.asyncio
async def test_actual_timeout_cancels_call_and_retains_initial_input(monkeypatch):
    async def slow():
        await asyncio.sleep(1)
    deps, context = make_context(slow, schema=HabitSchema())
    monkeypatch.setattr(habits, "_LLM_TIMEOUT", 0.01)
    await start(context)
    await collect(context, "All source.")
    assert (await deps.session_repo().get(1)).pending_entry["diary"] == "All source."


@pytest.mark.asyncio
@pytest.mark.parametrize(("diary_enabled", "custom"), [(True, False), (False, True), (False, False)])
async def test_diary_only_and_disabled_diary(diary_enabled, custom):
    schema = HabitSchema(include_diary=diary_enabled, fields={
        "workout": HabitFieldConfig(type="boolean", description="Exercise"),
    } if custom else {})
    response = {"diary": "Exercise story."} if diary_enabled else {"workout": True}
    deps, context = make_context(response, schema=schema)
    await start(context)
    await collect(context, "I exercised.")
    pending = (await deps.session_repo().get(1)).pending_entry
    assert ("diary" in pending) == diary_enabled
    assert len(deps.llm_client().requests) == int(diary_enabled or custom)
    if custom:
        assert pending["workout"] is True


@pytest.mark.asyncio
async def test_multipart_last_ratings_does_not_erase_narrative_and_long_preview():
    long_diary = "Абзац < & > 📝. " * 1000
    schema = HabitSchema(fields={"mood": HabitFieldConfig(type="integer", description="Mood")})
    deps, context = make_context({"diary": long_diary, "mood": 2}, schema=schema)
    await start(context)
    status = await collect(context, "", parts=[long_diary, "Mood 2"])
    messages, _, options = deps.llm_client().requests[0]
    assert [m.content for m in messages[1:]] == [long_diary, "Mood 2"]
    assert options["max_tokens"] > 2000
    assert all(telegram_text_length(t) <= TELEGRAM_TEXT_CHUNK_SIZE for t, _, _ in status.replies)
    assert all("reply_markup" not in kwargs for _, kwargs, _ in status.replies[:-1])
    assert "reply_markup" in status.replies[-1][1]
    assert long_diary in html.unescape("".join(t for t, _, _ in status.replies))
    assert (await deps.session_repo().get(1)).pending_entry["diary"] == long_diary


@pytest.mark.asyncio
async def test_different_dates_and_users_never_share_history():
    deps, context = make_context({"diary": "Day one."}, {"diary": "Day two."},
                                 {"diary": "Other user."}, schema=HabitSchema())
    await start(context, "2026-10-21")
    await collect(context, "Source one.")
    # Even an old temp_data object cannot supply history to a different selected date.
    session = await deps.session_repo().get(1)
    session.state = ConversationState.HABITS_AWAITING_CONTENT
    session.selected_date = date(2026, 10, 22)
    await deps.session_repo().save(session)
    await habits.handle_habits_text(_update(FakeMessage("Source two.")), context)
    await deps.session_repo().save(SessionData(user_id=2, selected_date=date(2026, 10, 22),
                                              state=ConversationState.HABITS_AWAITING_CONTENT))
    other = _update(FakeMessage("Other source."))
    other.effective_user.id = 2
    await habits.handle_habits_text(other, context)
    assert [[m.content for m in req[0][1:]] for req in deps.llm_client().requests] == [
        ["Source one."], ["Source two."], ["Other source."],
    ]


@pytest.mark.asyncio
async def test_fields_only_initial_empty_diary_and_preserved_sleep_narrative():
    turns = CASES["fields_only"]["turns"][:2]
    deps, context = make_context(*[{"diary": "", **t["expected"]} for t in turns])
    await start(context)
    for turn in turns:
        await collect(context, turn["text"])
        assert (await deps.session_repo().get(1)).pending_entry["diary"] == ""
        await add(context)
    story = "Спал 6,5 часов. Зарядки не было. Алкоголь не пил. Секса не было."
    deps.llm_client().responses.append({"diary": story, **turns[-1]["expected"], "сон_часы": 6.5})
    await collect(context, story)
    pending = (await deps.session_repo().get(1)).pending_entry
    assert pending["diary"] == story and pending["сон_часы"] == 6.5


@pytest.mark.asyncio
async def test_missing_provider_keeps_lossless_initial_draft():
    deps, context = make_context(schema=HabitSchema())
    deps._llm_client = None
    await start(context)
    status = await collect(context, "All input retained.")
    assert (await deps.session_repo().get(1)).pending_entry["diary"] == "All input retained."
    assert MESSAGES_RU["diary_integration_failed"] in "".join(t for t, _, _ in status.replies)


@pytest.mark.asyncio
async def test_real_langchain_request_uses_json_schema_and_dynamic_budget():
    requests = []
    transport_timeouts = []
    diary = "Long original sentence. " * 600
    def respond(request):
        requests.append(json.loads(request.content))
        transport_timeouts.append(request.extensions["timeout"])
        return httpx.Response(200, json={
            "id": "synthetic", "object": "chat.completion", "created": 1,
            "model": "google/gemini-3.8-flash",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"diary": diary}),
            }}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 20, "total_tokens": 40},
        })
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
        client = LLMClient.__new__(LLMClient)
        client._model = ChatOpenAI(model="google/gemini-3.8-flash", api_key="synthetic",
                                  max_completion_tokens=2000, http_async_client=http_client)
        result = await HabitExtractor(client).extract(diary, schema=HabitSchema())
    assert result["diary"] == diary
    assert len(requests) == 1
    request = requests[0]
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert request["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert request["max_completion_tokens"] > 2000
    assert request["model"] == "google/gemini-3.8-flash"
    assert client._model.max_tokens == 2000
    assert transport_timeouts[0]["read"] > 45


def test_long_processing_timeout_keeps_short_timeout_and_caps_growth():
    assert diary_processing_timeout("short", 45) == 45
    assert diary_processing_timeout("x" * 20_000, 45) == 125
    assert diary_processing_timeout("x" * 100_000, 45) == 180
    assert diary_processing_timeout("x" * 100_000, 240) == 240


@pytest.mark.asyncio
async def test_provider_payment_failure_makes_one_http_request():
    calls = []
    def payment_required(request):
        calls.append(request)
        return httpx.Response(402, json={"error": {"message": "Insufficient credits"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(payment_required)) as http_client:
        client = LLMClient.__new__(LLMClient)
        client._model = ChatOpenAI(model="google/gemini-3.8-flash", api_key="synthetic",
                                  http_async_client=http_client)
        with pytest.raises(ExternalResponseError):
            await HabitExtractor(client).extract("Full source.", schema=HabitSchema())
    assert len(calls) == 1


def test_existing_fixed_diary_description_is_refreshed():
    from src.config.constants import DEFAULT_HABIT_SCHEMA
    from src.services.telegram.handlers.habits_config import _ensure_diary_field
    profile = SimpleNamespace(habit_schema=HabitSchema(fields={
        "diary": HabitFieldConfig(type="string", description="Full original text unchanged"),
    }))
    assert _ensure_diary_field(profile) is True
    assert profile.habit_schema.fields["diary"] == DEFAULT_HABIT_SCHEMA.fields["diary"]
    assert _ensure_diary_field(profile) is False


@pytest.mark.asyncio
async def test_defaults_are_applied_in_code_and_not_sent_as_model_evidence():
    schema = HabitSchema(fields={"mood": HabitFieldConfig(type="integer", description="Mood",
                                                         default=3)})
    deps, context = make_context({"diary": "An event.", "mood": None}, schema=schema)
    await start(context)
    await collect(context, "An event.")
    session = await deps.session_repo().get(1)
    assert session.pending_entry["mood"] == 3
    assert session.pending_entry["defaulted_fields"] == ["mood"]
    assert json.loads(session.temp_data["entry_messages"][-1]["content"])["mood"] is None
    assert '"default"' not in deps.llm_client().requests[0][0][0].content


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [
    {"diary": "Text.", "mood": 8},
    {"diary": "Text."},
    {"diary": None, "mood": 2},
    {"diary": "Text.", "mood": 2, "entry_id": "model-controlled"},
])
async def test_schema_rejects_invalid_fields_and_technical_overwrites(invalid):
    schema = HabitSchema(fields={"mood": HabitFieldConfig(type="integer", description="Mood",
                                                         minimum=1, maximum=5)})
    deps, context = make_context(invalid, schema=schema)
    await start(context)
    await collect(context, "Full original input.")
    session = await deps.session_repo().get(1)
    assert session.temp_data["entry_processing_failed"] is True
    assert session.pending_entry["diary"] == "Full original input."
    assert session.pending_entry["entry_id"] != "model-controlled"
