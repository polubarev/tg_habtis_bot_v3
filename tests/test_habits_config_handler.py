from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config.constants import DEFAULT_HABIT_SCHEMA, MESSAGES_EN
from src.models.habit import HabitSchema
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.telegram.handlers.habits_config import (
    handle_habit_edit_attr_callback,
    handle_habit_field_callback,
    handle_habits_config_text,
)


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

    async def update(self, profile: UserProfile) -> None:
        self.profile = profile


class FakeDeps:
    def __init__(self, session_repo: FakeSessionRepo, user_repo: FakeUserRepo) -> None:
        self._session_repo = session_repo
        self._user_repo = user_repo

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return self._user_repo


@pytest.mark.asyncio
@pytest.mark.parametrize("attr", ["type", "description"])
async def test_diary_description_cannot_be_edited(attr):
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
        data=f"habit_edit_attr:{attr}",
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
    assert query.edit_message_text.await_args.args[0] == MESSAGES_EN["habit_diary_fixed"]
    assert deps.session_repo().session.state == ConversationState.IDLE


@pytest.mark.asyncio
async def test_diary_field_edit_button_shows_fixed_behavior():
    user_id = 123
    session = SessionData(user_id=user_id, state=ConversationState.CONFIG_EDITING_HABITS)
    profile = UserProfile(
        telegram_user_id=user_id,
        language="en",
        habit_schema=DEFAULT_HABIT_SCHEMA.model_copy(deep=True),
    )
    query = SimpleNamespace(
        data="habit_field:edit:diary",
        edit_message_text=AsyncMock(),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        callback_query=query,
    )
    deps = FakeDeps(FakeSessionRepo(session), FakeUserRepo(profile))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}))

    await handle_habit_field_callback(update, context)

    assert query.edit_message_text.await_args.args[0] == MESSAGES_EN["habit_diary_fixed"]
    assert deps.session_repo().session.state == ConversationState.IDLE


@pytest.mark.asyncio
async def test_adding_diary_does_not_ask_for_unused_description():
    user_id = 123
    session = SessionData(
        user_id=user_id,
        state=ConversationState.CONFIG_EDITING_HABITS,
        temp_data={"habit_action": "add", "habit_add_stage": "name"},
    )
    profile = UserProfile(
        telegram_user_id=user_id,
        language="en",
        habit_schema=HabitSchema(fields={}, include_diary=False),
    )
    message = SimpleNamespace(text="diary", reply_text=AsyncMock())
    update = SimpleNamespace(effective_user=SimpleNamespace(id=user_id), message=message)
    deps = FakeDeps(FakeSessionRepo(session), FakeUserRepo(profile))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}))

    handled = await handle_habits_config_text(update, context)

    assert handled is True
    assert deps.user_repo().profile.habit_schema.include_diary is True
    assert deps.user_repo().profile.habit_schema.fields["diary"] == DEFAULT_HABIT_SCHEMA.fields["diary"]
    assert deps.session_repo().session.state == ConversationState.IDLE
    assert "diary" in message.reply_text.await_args.args[0].lower()
