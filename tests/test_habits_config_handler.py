from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config.constants import DEFAULT_HABIT_SCHEMA
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.telegram.handlers.habits_config import handle_habit_edit_attr_callback


class FakeSessionRepo:
    def __init__(self, session: SessionData) -> None:
        self.session = session

    async def get(self, _user_id: int) -> SessionData:
        return self.session

    async def save(self, session: SessionData) -> None:
        self.session = session


class FakeUserRepo:
    def __init__(self, profile: UserProfile) -> None:
        self.profile = profile

    async def get_by_telegram_id(self, _user_id: int) -> UserProfile:
        return self.profile


class FakeDeps:
    def __init__(self, session_repo: FakeSessionRepo, user_repo: FakeUserRepo) -> None:
        self._session_repo = session_repo
        self._user_repo = user_repo

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return self._user_repo


@pytest.mark.asyncio
async def test_diary_non_description_edit_rerenders_allowed_attributes():
    user_id = 123
    session = SessionData(
        user_id=user_id,
        state=ConversationState.CONFIG_EDITING_HABITS,
        temp_data={
            "habit_action": "edit",
            "habit_edit_stage": "attr",
            "habit_edit_field": "diary",
        },
    )
    profile = UserProfile(
        telegram_user_id=user_id,
        language="en",
        habit_schema=DEFAULT_HABIT_SCHEMA.model_copy(deep=True),
    )
    query = SimpleNamespace(
        data="habit_edit_attr:type",
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        callback_query=query,
    )
    deps = FakeDeps(FakeSessionRepo(session), FakeUserRepo(profile))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}))

    await handle_habit_edit_attr_callback(update, context)

    query.edit_message_text.assert_awaited_once()
    assert "diary" in query.edit_message_text.await_args.args[0].lower()
