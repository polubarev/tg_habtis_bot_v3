from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import TelegramError

from src.config.constants import BUTTONS_EN, MESSAGES_EN
from src.config.settings import Settings
from src.models.feedback import FeedbackEntry
from src.models.session import ConversationState, SessionData
from src.models.usage_event import UsageEvent
from src.models.user import UsageStats, UserProfile
from src.services.telegram.handlers.admin import (
    admin_command,
    handle_admin_broadcast_callback,
    handle_admin_broadcast_text,
    handle_admin_text,
)


class FakeSessionRepo:
    def __init__(self) -> None:
        self.sessions: dict[int, SessionData] = {}

    async def get(self, user_id: int) -> SessionData | None:
        return self.sessions.get(user_id)

    async def save(self, session: SessionData) -> None:
        self.sessions[session.user_id] = session


class FakeUserRepo:
    def __init__(self, users: list[UserProfile]) -> None:
        self.users = users

    async def get_by_telegram_id(self, telegram_id: int) -> UserProfile | None:
        return next((user for user in self.users if user.telegram_user_id == telegram_id), None)

    async def list_all(self) -> list[UserProfile]:
        return self.users


class FakeFeedbackRepo:
    def __init__(self, entries: list[FeedbackEntry]) -> None:
        self.entries = entries

    async def list_recent(self, limit: int = 10) -> list[FeedbackEntry]:
        return self.entries[:limit]


class FakeUsageEventRepo:
    def __init__(self, events: list[UsageEvent] | None = None) -> None:
        self.events = events or []

    async def create(self, event: UsageEvent) -> bool:
        self.events.append(event)
        return True

    async def list_between(self, start: datetime, end: datetime) -> list[UsageEvent]:
        return [event for event in self.events if start <= event.occurred_at < end]


class FakeDeps:
    def __init__(
        self,
        *,
        settings: Settings,
        session_repo: FakeSessionRepo | None = None,
        user_repo: FakeUserRepo | None = None,
        feedback_repo: FakeFeedbackRepo | None = None,
        usage_event_repo: FakeUsageEventRepo | None = None,
    ) -> None:
        self.settings = settings
        self._session_repo = session_repo
        self._user_repo = user_repo
        self._feedback_repo = feedback_repo
        self._usage_event_repo = usage_event_repo

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return self._user_repo

    def feedback_repo(self):
        return self._feedback_repo

    def usage_event_repo(self):
        return self._usage_event_repo


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.replies: list[tuple[str, dict]] = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append((text, kwargs))
        return self


class FakeBot:
    def __init__(self, fail_ids: set[int] | None = None) -> None:
        self.fail_ids = fail_ids or set()
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str):
        if chat_id in self.fail_ids:
            raise TelegramError("send failed")
        self.sent.append((chat_id, text))


def _context(deps: FakeDeps, bot: FakeBot | None = None):
    return SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}), bot=bot or FakeBot())


def _message_update(text: str, user_id: int):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="admin", first_name="Admin"),
        message=FakeMessage(text),
        callback_query=None,
    )


def _callback_update(data: str, user_id: int, message: FakeMessage):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="admin", first_name="Admin"),
        message=None,
        callback_query=SimpleNamespace(data=data, message=message, answer=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_admin_command_denies_non_admin():
    deps = FakeDeps(settings=Settings(admin_telegram_ids="42"), user_repo=FakeUserRepo([]))
    update = _message_update("/admin", user_id=1)

    await admin_command(update, _context(deps))

    assert update.message.replies[0][0] == MESSAGES_EN["admin_denied"]


@pytest.mark.asyncio
async def test_admin_stats_aggregates_users():
    users = [
        UserProfile(
            telegram_user_id=1,
            sheet_id="sheet",
            usage_stats=UsageStats(habits=2, dream=1, thought=0, reflection=3),
        ),
        UserProfile(
            telegram_user_id=2,
            usage_stats=UsageStats(habits=4, dream=0, thought=5, reflection=1),
        ),
    ]
    deps = FakeDeps(settings=Settings(admin_telegram_ids="1"), user_repo=FakeUserRepo(users))
    update = _message_update(BUTTONS_EN["admin_stats"], user_id=1)

    handled = await handle_admin_text(update, _context(deps))

    assert handled is True
    reply = update.message.replies[0][0]
    assert "Users: 2" in reply
    assert "Users with sheet: 1" in reply
    assert "Habits: 6" in reply
    assert "Reflections: 4" in reply


@pytest.mark.asyncio
async def test_admin_feedback_lists_recent_entries():
    entry = FeedbackEntry(
        telegram_user_id=2,
        telegram_username="tester",
        language="en",
        message="Please add export",
        created_at=datetime(2026, 6, 2, 10, 15),
    )
    deps = FakeDeps(
        settings=Settings(admin_telegram_ids="1"),
        user_repo=FakeUserRepo([UserProfile(telegram_user_id=1)]),
        feedback_repo=FakeFeedbackRepo([entry]),
    )
    update = _message_update(BUTTONS_EN["admin_feedback"], user_id=1)

    handled = await handle_admin_text(update, _context(deps))

    assert handled is True
    reply = update.message.replies[0][0]
    assert "Recent feedback:" in reply
    assert "@tester (2)" in reply
    assert "Please add export" in reply


@pytest.mark.asyncio
async def test_admin_week_stats_aggregates_period_events():
    now = datetime.now(timezone.utc)
    users = [
        UserProfile(telegram_user_id=1, created_at=now),
        UserProfile(telegram_user_id=2, sheet_id="sheet", created_at=now),
    ]
    events = [
        UsageEvent.create("feature.saved", user_id=2, feature="habits", occurred_at=now),
        UsageEvent.create("feature.saved", user_id=2, feature="dream", occurred_at=now),
        UsageEvent.create("voice.received", user_id=2, occurred_at=now),
        UsageEvent.create("feedback.submitted", user_id=2, feature="feedback", occurred_at=now),
        UsageEvent.create("command.used", user_id=2, feature="habits", occurred_at=now),
        UsageEvent.create(
            "broadcast.sent",
            user_id=1,
            feature="broadcast",
            occurred_at=now,
            metadata={"sent": 2, "failed": 1},
        ),
    ]
    deps = FakeDeps(
        settings=Settings(admin_telegram_ids="1"),
        user_repo=FakeUserRepo(users),
        usage_event_repo=FakeUsageEventRepo(events),
    )
    update = _message_update(BUTTONS_EN["admin_week"], user_id=1)

    handled = await handle_admin_text(update, _context(deps))

    assert handled is True
    reply = update.message.replies[0][0]
    assert "This week" in reply
    assert "Active users: 2" in reply
    assert "New users: 2" in reply
    assert "Users with sheet: 1" in reply
    assert "Saved entries: 2" in reply
    assert "Habits: 1" in reply
    assert "Dreams: 1" in reply
    assert "Voice messages: 1" in reply
    assert "Feedback: 1" in reply
    assert "Commands: 1" in reply
    assert "Broadcasts: 1 (sent 2, failed 1)" in reply


@pytest.mark.asyncio
async def test_admin_broadcast_requires_confirmation_before_sending():
    session_repo = FakeSessionRepo()
    users = [
        UserProfile(telegram_user_id=1),
        UserProfile(telegram_user_id=2),
        UserProfile(telegram_user_id=3),
    ]
    deps = FakeDeps(
        settings=Settings(admin_telegram_ids="1"),
        session_repo=session_repo,
        user_repo=FakeUserRepo(users),
        usage_event_repo=FakeUsageEventRepo(),
    )
    bot = FakeBot(fail_ids={3})
    context = _context(deps, bot=bot)
    start_update = _message_update(BUTTONS_EN["admin_broadcast"], user_id=1)

    assert await handle_admin_text(start_update, context) is True
    assert bot.sent == []
    session = await session_repo.get(1)
    assert session is not None
    assert session.state == ConversationState.ADMIN_AWAITING_BROADCAST

    draft_update = _message_update("Hello users", user_id=1)
    assert await handle_admin_broadcast_text(draft_update, context) is True
    assert bot.sent == []
    assert "Broadcast preview" in draft_update.message.replies[0][0]

    callback_message = FakeMessage()
    callback_update = _callback_update("admin_broadcast:send", user_id=1, message=callback_message)
    await handle_admin_broadcast_callback(callback_update, context)

    assert bot.sent == [(1, "Hello users"), (2, "Hello users")]
    assert "Sent: 2. Failed: 1." in callback_message.replies[0][0]
    assert (await session_repo.get(1)).state == ConversationState.IDLE
    assert deps._usage_event_repo.events[-1].event_name == "broadcast.sent"
    assert deps._usage_event_repo.events[-1].metadata == {"sent": 2, "failed": 1}
