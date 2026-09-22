from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.exceptions import ExternalTimeoutError
from src.models.entry import DreamEntry, HabitEntry, ReflectionEntry, ThoughtEntry
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.telegram.handlers.dream import handle_dream_confirm
from src.services.telegram.handlers.habits import handle_habits_confirm
from src.services.telegram.handlers.reflect import handle_reflect_confirm
from src.services.telegram.handlers.thought import handle_thought_confirm


class SessionRepo:
    def __init__(self, session):
        self.session = session

    async def get(self, _user_id):
        return self.session

    async def save(self, session):
        self.session = session


class UserRepo:
    def __init__(self):
        self.profile = UserProfile(
            telegram_user_id=1,
            language="en",
            sheet_id="1AbCDefGh1234567890xYz987654321",
        )

    async def get_by_telegram_id(self, _user_id):
        return self.profile


class TimeoutSheets:
    async def append_habit_entry(self, *_args):
        raise ExternalTimeoutError("timeout")

    async def append_dream_entry(self, *_args):
        raise ExternalTimeoutError("timeout")

    async def append_thought_entry(self, *_args):
        raise ExternalTimeoutError("timeout")

    async def append_reflection_entry(self, *_args):
        raise ExternalTimeoutError("timeout")


class Deps:
    def __init__(self, session):
        self._session_repo = SessionRepo(session)
        self._user_repo = UserRepo()
        self._sheets = TimeoutSheets()

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return self._user_repo

    def sheets_client(self):
        return self._sheets

    def usage_event_repo(self):
        return None

    def llm_client(self):
        return None


def _case(session, data):
    query = SimpleNamespace(
        data=data,
        answer=AsyncMock(),
        edit_message_reply_markup=AsyncMock(),
        edit_message_text=AsyncMock(),
    )
    bot = SimpleNamespace(send_message=AsyncMock())
    deps = Deps(session)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=bot)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=10),
        callback_query=query,
    )
    return update, context, deps, bot


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "state", "entry", "data"),
    [
        (
            handle_dream_confirm,
            ConversationState.DREAM_AWAITING_CONFIRMATION,
            DreamEntry(timestamp=datetime.now(timezone.utc), record="dream"),
            "dream_confirm:yes",
        ),
        (
            handle_thought_confirm,
            ConversationState.THOUGHT_AWAITING_CONFIRMATION,
            ThoughtEntry(timestamp=datetime.now(timezone.utc), record="thought"),
            "thought_confirm:yes",
        ),
        (
            handle_reflect_confirm,
            ConversationState.REFLECT_AWAITING_CONFIRMATION,
            ReflectionEntry(timestamp=datetime.now(timezone.utc), answers={"q": "a"}),
            "reflect_confirm:yes",
        ),
    ],
)
async def test_retryable_save_failure_preserves_pending_entry(handler, state, entry, data):
    session = SessionData(user_id=1, state=state, pending_entry=entry.model_dump(mode="json"))
    original = dict(session.pending_entry or {})
    update, context, deps, bot = _case(session, data)

    await handler(update, context)

    saved = deps.session_repo().session
    assert saved.state == state
    assert saved.pending_entry == original
    kwargs = bot.send_message.await_args.kwargs
    assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_habit_save_timeout_preserves_pending_entry_and_uuid():
    entry = HabitEntry(date=date(2026, 9, 22), raw_record="diary", diary="diary")
    pending = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": entry.date.isoformat(),
        "raw_record": entry.raw_record,
        "diary": entry.diary,
        "input_type": "text",
        "field_order": [],
        "entry_id": entry.entry_id,
    }
    session = SessionData(
        user_id=1,
        state=ConversationState.HABITS_AWAITING_CONFIRMATION,
        pending_entry=pending,
    )
    update, context, deps, bot = _case(session, "habits_confirm:yes")

    await handle_habits_confirm(update, context)

    saved = deps.session_repo().session
    assert saved.state == ConversationState.HABITS_AWAITING_CONFIRMATION
    assert saved.pending_entry is not None
    assert saved.pending_entry["entry_id"] == entry.entry_id
    assert "reply_markup" in bot.send_message.await_args.kwargs
