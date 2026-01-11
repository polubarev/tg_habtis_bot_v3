from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config.constants import MESSAGES_EN
from src.models.session import ConversationState, SessionData
from src.services.telegram.handlers.config import handle_config_text


class FakeSessionRepo:
    def __init__(self, session: SessionData):
        self._session = session

    async def get(self, user_id: int):
        return self._session

    async def save(self, session: SessionData) -> None:
        self._session = session


class FakeDeps:
    def __init__(self, session_repo: FakeSessionRepo):
        self._session_repo = session_repo

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return None

    def sheets_client(self):
        return None


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
