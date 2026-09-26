from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config.settings import Settings
from src.models.enums import EntryType
from src.models.habit import HabitFieldConfig, HabitSchema
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.entry_collection import EntryCollectionManager
from src.services.storage.firestore.session_repo import SessionRepository
from src.services.storage.firestore.text_entry_collection_repo import (
    TextEntryCollectionRepository,
)
from src.services.telegram.handlers.habits import handle_habits_confirm, handle_habits_text
from src.services.telegram.handlers import habits as habits_module
from src.services.telegram.handlers.entry_collection import (
    handle_entry_collection_callback,
    handle_entry_collection_text,
    start_entry_collection,
)
from src.services.telegram.utils import TELEGRAM_TEXT_CHUNK_SIZE, telegram_text_length


class FakeMessage:
    _next_id = 100

    def __init__(self, text: str = "", message_id: int | None = None) -> None:
        self.text = text
        self.message_id = message_id or self._allocate_id()
        self.replies: list[tuple[str, dict, "FakeMessage"]] = []
        self.deleted = False

    @classmethod
    def _allocate_id(cls) -> int:
        cls._next_id += 1
        return cls._next_id

    async def reply_text(self, text: str, **kwargs):
        sent = FakeMessage(text)
        self.replies.append((text, kwargs, sent))
        return sent

    async def delete(self):
        self.deleted = True


class FakeQuery:
    def __init__(self, message: FakeMessage, data: str) -> None:
        self.message = message
        self.data = data
        self.answers: list[str | None] = []

    async def answer(self, text=None):
        self.answers.append(text)

    async def edit_message_text(self, text: str, **kwargs):
        self.message.text = text
        return self.message


class FakeBot:
    def __init__(self) -> None:
        self.edits: list[dict] = []
        self.sent: list[dict] = []
        self.deleted: list[dict] = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return FakeMessage(kwargs["text"])

    async def delete_message(self, **kwargs):
        self.deleted.append(kwargs)


class FakeUserRepo:
    def __init__(self) -> None:
        self.profile = UserProfile(
            telegram_user_id=1,
            language="en",
            sheet_id="1AbCDefGh1234567890xYz987654321",
        )

    async def get_by_telegram_id(self, _user_id: int):
        return self.profile

    async def update(self, profile):
        self.profile = profile


class FakeSheets:
    def __init__(self):
        self.appended = []
        self.updated = []

    async def append_habit_entry(self, sheet_id, field_order, entry):
        self.appended.append((sheet_id, field_order, entry))

    async def update_habit_entry(self, sheet_id, row_index, field_order, entry):
        self.updated.append((sheet_id, row_index, field_order, entry))


class FakeDeps:
    def __init__(self) -> None:
        self.settings = Settings(_env_file=None, text_entry_max_utf16_units=30_000)
        self._session_repo = SessionRepository(client=None)
        self._collection_repo = TextEntryCollectionRepository(settings=self.settings)
        self._manager = EntryCollectionManager(self._collection_repo)
        self._user_repo = FakeUserRepo()
        self._sheets_client = FakeSheets()
        self._llm_client = None

    def session_repo(self):
        return self._session_repo

    def text_entry_collection_repo(self):
        return self._collection_repo

    def entry_collection_manager(self):
        return self._manager

    def user_repo(self):
        return self._user_repo

    def sheets_client(self):
        return self._sheets_client

    def llm_client(self):
        return self._llm_client

    def usage_event_repo(self):
        return None


class ShorteningExtractor:
    def __init__(self, _client):
        pass

    async def extract(self, _raw_text, language="en", schema=None):
        return {"diary": "AI shortened this", "mood": 5}


def _update(message: FakeMessage, *, callback_data: str | None = None):
    query = FakeQuery(message, callback_data) if callback_data else None
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=10),
        message=None if query else message,
        callback_query=query,
    )


@pytest.mark.asyncio
async def test_collection_started_from_callback_follows_field_hints():
    deps = FakeDeps()
    bot = FakeBot()
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=bot)
    date_prompt = FakeMessage("Choose a date")
    hints = await bot.send_message(chat_id=10, text="Habit field hints")

    await start_entry_collection(
        _update(date_prompt, callback_data="habits_date:today"), context, EntryType.HABIT
    )

    collection = await deps.text_entry_collection_repo().get(1)
    assert collection.status_message_id > hints.message_id
    assert "Parts: 0" in bot.sent[-1]["text"]
    assert "reply_markup" in bot.sent[-1]
    assert date_prompt.deleted


@pytest.mark.asyncio
async def test_collection_status_follows_each_new_part():
    deps = FakeDeps()
    bot = FakeBot()
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=bot)
    prompt = FakeMessage("prompt")
    await start_entry_collection(_update(prompt), context, EntryType.HABIT)
    previous_status_id = prompt.replies[-1][2].message_id

    for count, text in enumerate(["first", "second"], start=1):
        part = FakeMessage(text)
        await handle_entry_collection_text(_update(part), context, text)

        assert len(part.replies) == 1, "Status must be sent below the new diary part"
        status_text, kwargs, status = part.replies[0]
        assert status.message_id > part.message_id
        assert f"Parts: {count}" in status_text
        assert "reply_markup" in kwargs
        collection = await deps.text_entry_collection_repo().get(1)
        assert collection.status_message_id == status.message_id
        assert bot.deleted[-1] == {"chat_id": 10, "message_id": previous_status_id}
        previous_status_id = status.message_id

    assert not bot.edits


@pytest.mark.asyncio
async def test_status_replacement_survives_old_card_delete_failure(monkeypatch):
    deps = FakeDeps()
    bot = FakeBot()
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=bot)
    await start_entry_collection(_update(FakeMessage("prompt")), context, EntryType.HABIT)
    monkeypatch.setattr(bot, "delete_message", AsyncMock(side_effect=RuntimeError("unavailable")))
    part = FakeMessage("first")

    assert await handle_entry_collection_text(_update(part), context, "first")

    status = part.replies[-1][2]
    collection = await deps.text_entry_collection_repo().get(1)
    assert collection.status_message_id == status.message_id
    await handle_entry_collection_callback(
        _update(status, callback_data="entry_collect:undo"), context
    )
    assert "Parts: 0" in status.text
    assert not collection.parts


@pytest.mark.asyncio
async def test_status_send_failure_preserves_previous_card(monkeypatch):
    deps = FakeDeps()
    bot = FakeBot()
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=bot)
    prompt = FakeMessage("prompt")
    await start_entry_collection(_update(prompt), context, EntryType.HABIT)
    previous_status_id = prompt.replies[-1][2].message_id
    part = FakeMessage("first")
    monkeypatch.setattr(part, "reply_text", AsyncMock(side_effect=RuntimeError("unavailable")))

    with pytest.raises(RuntimeError, match="unavailable"):
        await handle_entry_collection_text(_update(part), context, "first")

    collection = await deps.text_entry_collection_repo().get(1)
    assert collection.status_message_id == previous_status_id
    assert collection.combined_text == "first"
    assert not bot.deleted


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entry_type", "flow_context", "expected_state", "value_path"),
    [
        (
            EntryType.HABIT,
            {"selected_date": "2026-09-22"},
            ConversationState.HABITS_AWAITING_CONFIRMATION,
            "raw_record",
        ),
        (EntryType.DREAM, {}, ConversationState.DREAM_AWAITING_CONFIRMATION, "record"),
        (EntryType.THOUGHT, {}, ConversationState.THOUGHT_AWAITING_CONFIRMATION, "record"),
        (
            EntryType.REFLECTION,
            {"questions": ["How was today?"]},
            ConversationState.REFLECT_AWAITING_CONFIRMATION,
            None,
        ),
    ],
)
async def test_done_processes_two_parts_for_every_text_flow(
    entry_type,
    flow_context,
    expected_state,
    value_path,
):
    deps = FakeDeps()
    bot = FakeBot()
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=bot)
    prompt = FakeMessage("prompt", message_id=5)
    await start_entry_collection(
        _update(prompt), context, entry_type, flow_context=flow_context
    )

    await handle_entry_collection_text(_update(FakeMessage("first", 10)), context, "first")
    await handle_entry_collection_text(_update(FakeMessage("second", 20)), context, "second")

    status = FakeMessage("status", message_id=5)
    callback_update = _update(status, callback_data="entry_collect:done")
    await handle_entry_collection_callback(callback_update, context)

    session = await deps.session_repo().get(1)
    assert session is not None
    assert session.state == expected_state
    assert session.pending_entry is not None
    if value_path is None:
        assert session.pending_entry["answers"]["How was today?"] == "first\n\nsecond"
    else:
        assert session.pending_entry[value_path] == "first\n\nsecond"
    collection = await deps.text_entry_collection_repo().get(1)
    assert collection is not None
    assert collection.status.value == "ready"


@pytest.mark.asyncio
async def test_long_multipart_diary_confirmation_is_chunked():
    deps = FakeDeps()
    bot = FakeBot()
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=bot)
    prompt = FakeMessage("prompt", message_id=5)
    await start_entry_collection(
        _update(prompt),
        context,
        EntryType.HABIT,
        flow_context={"selected_date": "2026-09-22"},
    )
    part_one = "a" * 3500
    part_two = "b" * 3500
    await handle_entry_collection_text(_update(FakeMessage(part_one, 10)), context, part_one)
    await handle_entry_collection_text(_update(FakeMessage(part_two, 20)), context, part_two)

    status = FakeMessage("status", message_id=5)
    await handle_entry_collection_callback(
        _update(status, callback_data="entry_collect:done"), context
    )

    confirmation_chunks = [
        (text, kwargs)
        for text, kwargs, _sent in status.replies
        if text != "LLM disabled — using raw answers where possible."
    ]
    assert len(confirmation_chunks) >= 2
    assert all(telegram_text_length(text) <= TELEGRAM_TEXT_CHUNK_SIZE for text, _ in confirmation_chunks)
    assert all("reply_markup" not in kwargs for _, kwargs in confirmation_chunks[:-1])
    assert "reply_markup" in confirmation_chunks[-1][1]
    session = await deps.session_repo().get(1)
    assert session.pending_entry["raw_record"] == f"{part_one}\n\n{part_two}"
    assert session.pending_entry["diary"] == session.pending_entry["raw_record"]
    assert session.pending_entry["diary"] in "".join(text for text, _ in confirmation_chunks)

    await handle_habits_confirm(
        _update(FakeMessage("draft"), callback_data="habits_confirm:yes"), context
    )
    saved_entry = deps.sheets_client().appended[0][2]
    assert saved_entry.raw_record == f"{part_one}\n\n{part_two}"
    assert saved_entry.diary == saved_entry.raw_record


@pytest.mark.asyncio
async def test_habits_no_adds_to_draft_across_multiple_confirmation_rounds(monkeypatch):
    deps = FakeDeps()
    deps._llm_client = SimpleNamespace(_model=object())
    deps.user_repo().profile.habit_schema = HabitSchema(fields={
        "mood": HabitFieldConfig(type="integer", description="Mood score"),
    })
    monkeypatch.setattr(habits_module, "HabitExtractor", ShorteningExtractor)
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"deps": deps}), bot=FakeBot()
    )
    await start_entry_collection(
        _update(FakeMessage("prompt")),
        context,
        EntryType.HABIT,
        flow_context={"selected_date": "2026-09-22"},
    )

    async def collect(text: str, message_id: int) -> str:
        await handle_entry_collection_text(_update(FakeMessage(text, message_id)), context, text)
        await handle_entry_collection_callback(
            _update(FakeMessage("status"), callback_data="entry_collect:done"), context
        )
        session = await deps.session_repo().get(1)
        assert session is not None
        assert session.state == ConversationState.HABITS_AWAITING_CONFIRMATION
        assert session.pending_entry is not None
        assert session.pending_entry["diary"] == session.pending_entry["raw_record"]
        return session.pending_entry["raw_record"]

    assert await collect("first", 10) == "first"
    await handle_habits_confirm(
        _update(FakeMessage("draft"), callback_data="habits_confirm:no"), context
    )
    assert await collect("second", 20) == "first\n\n[Update]\nsecond"
    await handle_habits_confirm(
        _update(FakeMessage("draft"), callback_data="habits_confirm:no"), context
    )
    assert await collect("third", 30) == "first\n\n[Update]\nsecond\n\n[Update]\nthird"
    await handle_habits_confirm(
        _update(FakeMessage("draft"), callback_data="habits_confirm:yes"), context
    )
    saved_entry = deps.sheets_client().appended[0][2]
    assert saved_entry.diary == saved_entry.raw_record
    assert saved_entry.raw_record.endswith("third")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("append", "original\n\n[Update]\nnew text"),
        ("rewrite", "new text"),
    ],
)
async def test_existing_habit_update_saves_full_diary(action, expected, monkeypatch):
    deps = FakeDeps()
    deps._llm_client = SimpleNamespace(_model=object())
    deps.user_repo().profile.habit_schema = HabitSchema(fields={
        "mood": HabitFieldConfig(type="integer", description="Mood score"),
    })

    monkeypatch.setattr(habits_module, "HabitExtractor", ShorteningExtractor)
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"deps": deps}), bot=FakeBot()
    )
    session = SessionData(
        user_id=1,
        state=ConversationState.HABITS_AWAITING_CONTENT,
        selected_date=date(2026, 9, 22),
        temp_data={
            "existing_entry_action": action,
            "existing_raw_record": "original",
            "existing_row_index": 2,
        },
    )
    await deps.session_repo().save(session)

    await handle_habits_text(_update(FakeMessage("new text")), context, "new text")
    pending = await deps.session_repo().get(1)
    assert pending.pending_entry["raw_record"] == expected
    assert pending.pending_entry["diary"] == expected
    assert pending.pending_entry["mood"] == 5
    await handle_habits_confirm(
        _update(FakeMessage("draft"), callback_data="habits_confirm:yes"), context
    )

    saved_entry = deps.sheets_client().updated[0][3]
    assert saved_entry.raw_record == expected
    assert saved_entry.diary == expected
    assert saved_entry.extra_fields["mood"] == 5
