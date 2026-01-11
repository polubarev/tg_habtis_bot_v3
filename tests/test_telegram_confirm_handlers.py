from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.config.constants import MESSAGES_EN
from src.services.telegram.handlers.dream import handle_dream_confirm
from src.services.telegram.handlers.habits import handle_habits_confirm
from src.services.telegram.handlers.reflect import handle_reflect_confirm
from src.services.telegram.handlers.thought import handle_thought_confirm


class _DummyAwaitable:
    def __await__(self):
        if False:
            yield None
        return None


class _DummyCallbackQuery:
    def __init__(self, data: str):
        self.data = data
        self.edit_message_text = AsyncMock()

    def answer(self):
        return _DummyAwaitable()


class _DummyContext:
    def __init__(self):
        self.application = SimpleNamespace(bot_data={})


def _build_update(data: str):
    query = _DummyCallbackQuery(data)
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=1))
    return update, query


@pytest.mark.asyncio
async def test_dream_confirm_without_session_sends_session_expired():
    update, query = _build_update("dream_confirm:yes")
    context = _DummyContext()

    await handle_dream_confirm(update, context)

    query.edit_message_text.assert_awaited_once_with(MESSAGES_EN["session_expired"])


@pytest.mark.asyncio
async def test_thought_confirm_without_session_sends_session_expired():
    update, query = _build_update("thought_confirm:yes")
    context = _DummyContext()

    await handle_thought_confirm(update, context)

    query.edit_message_text.assert_awaited_once_with(MESSAGES_EN["session_expired"])


@pytest.mark.asyncio
async def test_reflect_confirm_without_session_sends_session_expired():
    update, query = _build_update("reflect_confirm:yes")
    context = _DummyContext()

    await handle_reflect_confirm(update, context)

    query.edit_message_text.assert_awaited_once_with(MESSAGES_EN["session_expired"])


@pytest.mark.asyncio
async def test_habits_confirm_without_session_sends_session_expired():
    update, query = _build_update("habits_confirm:yes")
    context = _DummyContext()

    await handle_habits_confirm(update, context)

    query.edit_message_text.assert_awaited_once_with(MESSAGES_EN["session_expired"])
