from types import SimpleNamespace

import pytest

from src.config.settings import Settings
from src.models.enums import EntryType
from src.models.session import ConversationState
from src.models.user import UserProfile
from src.services.entry_collection import EntryCollectionManager
from src.services.storage.firestore.session_repo import SessionRepository
from src.services.storage.firestore.text_entry_collection_repo import (
    TextEntryCollectionRepository,
)
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

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)


class FakeUserRepo:
    def __init__(self) -> None:
        self.profile = UserProfile(
            telegram_user_id=1,
            language="en",
            sheet_id="1AbCDefGh1234567890xYz987654321",
        )

    async def get_by_telegram_id(self, _user_id: int):
        return self.profile


class FakeDeps:
    def __init__(self) -> None:
        self.settings = Settings(_env_file=None, text_entry_max_utf16_units=30_000)
        self._session_repo = SessionRepository(client=None)
        self._collection_repo = TextEntryCollectionRepository(settings=self.settings)
        self._manager = EntryCollectionManager(self._collection_repo)
        self._user_repo = FakeUserRepo()

    def session_repo(self):
        return self._session_repo

    def text_entry_collection_repo(self):
        return self._collection_repo

    def entry_collection_manager(self):
        return self._manager

    def user_repo(self):
        return self._user_repo

    def sheets_client(self):
        return object()

    def llm_client(self):
        return None

    def usage_event_repo(self):
        return None


def _update(message: FakeMessage, *, callback_data: str | None = None):
    query = FakeQuery(message, callback_data) if callback_data else None
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=10),
        message=None if query else message,
        callback_query=query,
    )


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
