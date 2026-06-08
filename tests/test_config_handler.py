from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config.constants import MESSAGES_EN
from src.core.exceptions import SheetAccessError
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.telegram.handlers.config import handle_config_text


class FakeSessionRepo:
    def __init__(self, session: SessionData):
        self._session = session

    async def get(self, user_id: int):
        return self._session

    async def save(self, session: SessionData) -> None:
        self._session = session


class FakeDeps:
    def __init__(self, session_repo: FakeSessionRepo, user_repo=None, sheets_client=None):
        self._session_repo = session_repo
        self._user_repo = user_repo
        self._sheets_client = sheets_client

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return self._user_repo

    def sheets_client(self):
        return self._sheets_client


class FakeUserRepo:
    def __init__(self, profile: UserProfile | None = None):
        self.profile = profile
        self.updated: list[UserProfile] = []

    async def get_by_telegram_id(self, _user_id: int):
        return self.profile

    async def update(self, profile: UserProfile) -> None:
        self.profile = profile
        self.updated.append(profile.model_copy(deep=True))


class FailingSheetsClient:
    async def ensure_tabs(self, _sheet_id: str) -> None:
        raise SheetAccessError("denied")


@pytest.mark.asyncio
async def test_handle_config_text_invalid_sheet_reply():
    session = SessionData(user_id=123, state=ConversationState.CONFIG_AWAITING_SHEET_URL)
    session_repo = FakeSessionRepo(session)
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": FakeDeps(session_repo)}))
    message = SimpleNamespace(text="not a sheet", reply_text=AsyncMock())
    update = SimpleNamespace(effective_user=SimpleNamespace(id=123, username="user"), message=message)

    handled = await handle_config_text(update, context)

    assert handled is True
    message.reply_text.assert_awaited_once_with(MESSAGES_EN["sheet_url_invalid"])
    assert session_repo._session.state == ConversationState.CONFIG_AWAITING_SHEET_URL


@pytest.mark.asyncio
async def test_handle_config_text_does_not_persist_sheet_before_validation_success():
    session = SessionData(user_id=123, state=ConversationState.CONFIG_AWAITING_SHEET_URL)
    session_repo = FakeSessionRepo(session)
    user_repo = FakeUserRepo(
        UserProfile(
            telegram_user_id=123,
            telegram_username="user",
            sheet_id="old-sheet-id",
            sheet_url="https://docs.google.com/spreadsheets/d/old-sheet-id",
            sheets_validated=True,
            language="en",
        )
    )
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={"deps": FakeDeps(session_repo, user_repo, FailingSheetsClient())}
        )
    )
    message = SimpleNamespace(
        text="https://docs.google.com/spreadsheets/d/1AbCDefGh1234567890xYz987654321/edit",
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(effective_user=SimpleNamespace(id=123, username="user"), message=message)

    handled = await handle_config_text(update, context)

    assert handled is True
    assert user_repo.profile is not None
    assert user_repo.profile.sheet_id == "old-sheet-id"
    assert user_repo.profile.sheets_validated is True
    assert user_repo.updated == []
    message.reply_text.assert_any_await(MESSAGES_EN["sheet_permission_error"])
