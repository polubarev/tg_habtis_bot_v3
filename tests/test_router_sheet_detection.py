from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.models.session import ConversationState, SessionData
from src.services.telegram.handlers import router as router_module


class FakeSessionRepo:
    def __init__(self) -> None:
        self.sessions: dict[int, SessionData] = {}

    async def get(self, user_id: int) -> SessionData | None:
        return self.sessions.get(user_id)

    async def save(self, session: SessionData) -> None:
        self.sessions[session.user_id] = session


class FakeDeps:
    def __init__(self, session_repo: FakeSessionRepo) -> None:
        self._session_repo = session_repo

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return None

    def feedback_repo(self):
        return None

    def sheets_client(self):
        return None

    def llm_client(self):
        return None

    def whisper_client(self):
        return None


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.replies: list[tuple[str, dict]] = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append((text, kwargs))
        return None


class FakeUpdate:
    def __init__(self, text: str, user_id: int) -> None:
        self.effective_user = SimpleNamespace(id=user_id, username="tester")
        self.message = FakeMessage(text)


def _build_context(deps: FakeDeps):
    return SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}))


@pytest.mark.asyncio
async def test_route_text_sheet_link_routes_to_config(monkeypatch):
    session_repo = FakeSessionRepo()
    user_id = 123
    session_repo.sessions[user_id] = SessionData(
        user_id=user_id,
        state=ConversationState.HABITS_AWAITING_CONTENT,
    )
    context = _build_context(FakeDeps(session_repo))
    update = FakeUpdate(
        "https://docs.google.com/spreadsheets/d/abc1234567890/edit#gid=0",
        user_id=user_id,
    )

    config_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(router_module, "handle_config_text", config_mock)

    await router_module.route_text(update, context)

    session = await session_repo.get(user_id)
    assert session is not None
    assert session.state == ConversationState.CONFIG_AWAITING_SHEET_URL
    assert config_mock.await_count == 1
    expected = router_module._messages_for_lang("en")["sheet_detected"]
    assert update.message.replies[0][0] == expected


@pytest.mark.asyncio
async def test_route_text_sheet_id_routes_to_config(monkeypatch):
    session_repo = FakeSessionRepo()
    user_id = 456
    context = _build_context(FakeDeps(session_repo))
    update = FakeUpdate("1AbCDefGh1234567890xYz987654321", user_id=user_id)

    config_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(router_module, "handle_config_text", config_mock)

    await router_module.route_text(update, context)

    session = await session_repo.get(user_id)
    assert session is not None
    assert session.state == ConversationState.CONFIG_AWAITING_SHEET_URL
    assert config_mock.await_count == 1


@pytest.mark.asyncio
async def test_route_text_custom_iso_date_is_not_treated_as_sheet_id(monkeypatch):
    session_repo = FakeSessionRepo()
    user_id = 789
    session_repo.sessions[user_id] = SessionData(
        user_id=user_id,
        state=ConversationState.HABITS_AWAITING_DATE,
    )
    context = _build_context(FakeDeps(session_repo))
    update = FakeUpdate("2026-06-06", user_id=user_id)

    config_mock = AsyncMock(return_value=True)
    date_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(router_module, "handle_config_text", config_mock)
    monkeypatch.setattr(router_module, "handle_habits_date_text", date_mock)

    await router_module.route_text(update, context)

    config_mock.assert_not_awaited()
    date_mock.assert_awaited_once()
