import html
from types import SimpleNamespace

import pytest
from telegram.constants import ParseMode

from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.telegram.handlers.thought import handle_thought_text
from src.services.telegram.utils import (
    TELEGRAM_TEXT_CHUNK_SIZE,
    reply_confirmation_preview,
    reply_text_chunked,
    split_telegram_text,
    telegram_text_length,
)


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.replies: list[tuple[str, dict]] = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append((text, kwargs))
        return SimpleNamespace(text=text)


class FakeSessionRepo:
    def __init__(self, session: SessionData) -> None:
        self.session = session

    async def get(self, user_id: int):
        return self.session

    async def save(self, session: SessionData) -> None:
        self.session = session


class FakeUserRepo:
    def __init__(self, profile: UserProfile) -> None:
        self.profile = profile

    async def get_by_telegram_id(self, user_id: int):
        return self.profile


class FakeDeps:
    def __init__(self, session_repo: FakeSessionRepo, user_repo: FakeUserRepo) -> None:
        self._session_repo = session_repo
        self._user_repo = user_repo

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return self._user_repo

    def sheets_client(self):
        return None


def test_split_telegram_text_preserves_all_content():
    text = ("word " * 2500) + ("z" * 5000)

    chunks = split_telegram_text(text)

    assert len(chunks) > 1
    assert "".join(chunks) == text
    assert all(
        0 < telegram_text_length(chunk) <= TELEGRAM_TEXT_CHUNK_SIZE
        for chunk in chunks
    )


def test_split_telegram_text_counts_non_bmp_emoji_as_two_units():
    text = "😀" * 3000

    chunks = split_telegram_text(text)

    assert len(chunks) == 2
    assert "".join(chunks) == text
    assert all(
        telegram_text_length(chunk) <= TELEGRAM_TEXT_CHUNK_SIZE
        for chunk in chunks
    )


@pytest.mark.asyncio
async def test_reply_confirmation_preview_puts_keyboard_on_last_chunk():
    message = FakeMessage()
    keyboard = object()
    preview = "x" * (TELEGRAM_TEXT_CHUNK_SIZE * 2)

    await reply_confirmation_preview(
        message,
        "Review and confirm:",
        preview,
        reply_markup=keyboard,
    )

    assert len(message.replies) == 3
    assert all(
        telegram_text_length(text) <= TELEGRAM_TEXT_CHUNK_SIZE
        for text, _ in message.replies
    )
    assert all("reply_markup" not in kwargs for _, kwargs in message.replies[:-1])
    assert message.replies[-1][1]["reply_markup"] is keyboard
    assert "".join(text for text, _ in message.replies) == f"Review and confirm:\n{preview}"


@pytest.mark.asyncio
async def test_long_html_reply_falls_back_to_safe_plain_text_chunks():
    message = FakeMessage()
    keyboard = object()
    raw_value = "<long diary> " * 700
    formatted = f"<b>Diary</b>:\n{html.escape(raw_value)}"

    await reply_text_chunked(
        message,
        formatted,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )

    assert len(message.replies) > 1
    assert "".join(text for text, _ in message.replies) == f"Diary:\n{raw_value}"
    assert all("parse_mode" not in kwargs for _, kwargs in message.replies)
    assert message.replies[-1][1]["reply_markup"] is keyboard


@pytest.mark.asyncio
async def test_long_thought_preview_is_chunked_but_full_text_is_stored():
    long_text = "long thought " * 900
    session_repo = FakeSessionRepo(
        SessionData(user_id=1, state=ConversationState.THOUGHT_AWAITING_CONTENT)
    )
    user_repo = FakeUserRepo(
        UserProfile(
            telegram_user_id=1,
            language="en",
            sheet_id="1AbCDefGh1234567890xYz987654321",
        )
    )
    deps = FakeDeps(session_repo, user_repo)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}))
    message = FakeMessage(long_text)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        message=message,
    )

    handled = await handle_thought_text(update, context, long_text)

    assert handled is True
    assert session_repo.session.state == ConversationState.THOUGHT_AWAITING_CONFIRMATION
    assert session_repo.session.pending_entry is not None
    assert session_repo.session.pending_entry["record"] == long_text
    assert len(message.replies) > 1
    assert all(
        telegram_text_length(text) <= TELEGRAM_TEXT_CHUNK_SIZE
        for text, _ in message.replies
    )
    assert all("reply_markup" not in kwargs for _, kwargs in message.replies[:-1])
    assert "reply_markup" in message.replies[-1][1]
