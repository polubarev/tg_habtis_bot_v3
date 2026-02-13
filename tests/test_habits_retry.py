from datetime import date
from types import SimpleNamespace

import pytest

from src.config.constants import MESSAGES_EN
from src.core.exceptions import ExternalResponseError
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.telegram.handlers import habits as habits_module


class FakeSessionRepo:
    def __init__(self, session: SessionData):
        self._session = session

    async def get(self, user_id: int):
        return self._session

    async def save(self, session: SessionData) -> None:
        self._session = session


class FakeUserRepo:
    def __init__(self, profile: UserProfile):
        self._profile = profile

    async def get_by_telegram_id(self, user_id: int):
        return self._profile


class FakeLLMClient:
    def __init__(self):
        self._model = object()


class FakeDeps:
    def __init__(self, session_repo: FakeSessionRepo, user_repo: FakeUserRepo, llm_client: FakeLLMClient):
        self._session_repo = session_repo
        self._user_repo = user_repo
        self._llm_client = llm_client

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return self._user_repo

    def sheets_client(self):
        return None

    def llm_client(self):
        return self._llm_client


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.replies: list[tuple[str, dict]] = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append((text, kwargs))
        return None


class FakeUpdate:
    def __init__(self, text: str, user_id: int):
        self.effective_user = SimpleNamespace(id=user_id, username="tester")
        self.message = FakeMessage(text)


def _build_context(deps: FakeDeps):
    return SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}))


@pytest.mark.asyncio
async def test_handle_habits_text_retries_once_then_succeeds(monkeypatch):
    raw_text = "Morning workout, work, then home"
    session = SessionData(
        user_id=1,
        state=ConversationState.HABITS_AWAITING_CONTENT,
        selected_date=date(2026, 2, 12),
    )
    session_repo = FakeSessionRepo(session)
    user_repo = FakeUserRepo(UserProfile(telegram_user_id=1, language="en"))
    context = _build_context(FakeDeps(session_repo, user_repo, FakeLLMClient()))
    update = FakeUpdate(raw_text, user_id=1)

    class RetryThenSuccessExtractor:
        calls = 0

        def __init__(self, client):
            pass

        async def extract(self, raw_text: str, language: str = "en", schema=None):
            type(self).calls += 1
            if type(self).calls == 1:
                raise ExternalResponseError("bad structured output")
            return {"diary": "Parsed diary"}

    monkeypatch.setattr(habits_module, "HabitExtractor", RetryThenSuccessExtractor)

    handled = await habits_module.handle_habits_text(update, context, raw_text)

    assert handled is True
    assert RetryThenSuccessExtractor.calls == habits_module._HABIT_EXTRACTION_MAX_ATTEMPTS
    response_texts = [text for text, _ in update.message.replies]
    assert response_texts.count(MESSAGES_EN["external_response_error"]) == 0
    assert any(text.startswith(MESSAGES_EN["confirm_entry"]) for text in response_texts)

    assert session_repo._session.state == ConversationState.HABITS_AWAITING_CONFIRMATION
    assert session_repo._session.pending_entry is not None
    assert session_repo._session.pending_entry["diary"] == "Parsed diary"


@pytest.mark.asyncio
async def test_handle_habits_text_retries_then_falls_back_to_draft(monkeypatch):
    raw_text = "Morning workout, work, then home"
    session = SessionData(
        user_id=1,
        state=ConversationState.HABITS_AWAITING_CONTENT,
        selected_date=date(2026, 2, 12),
    )
    session_repo = FakeSessionRepo(session)
    user_repo = FakeUserRepo(UserProfile(telegram_user_id=1, language="en"))
    context = _build_context(FakeDeps(session_repo, user_repo, FakeLLMClient()))
    update = FakeUpdate(raw_text, user_id=1)

    class AlwaysFailExtractor:
        calls = 0

        def __init__(self, client):
            pass

        async def extract(self, raw_text: str, language: str = "en", schema=None):
            type(self).calls += 1
            raise ExternalResponseError("bad structured output")

    monkeypatch.setattr(habits_module, "HabitExtractor", AlwaysFailExtractor)

    handled = await habits_module.handle_habits_text(update, context, raw_text)

    assert handled is True
    assert AlwaysFailExtractor.calls == habits_module._HABIT_EXTRACTION_MAX_ATTEMPTS
    response_texts = [text for text, _ in update.message.replies]
    assert response_texts.count(MESSAGES_EN["external_response_error"]) == 1
    assert any(text.startswith(MESSAGES_EN["confirm_entry"]) for text in response_texts)

    assert session_repo._session.state == ConversationState.HABITS_AWAITING_CONFIRMATION
    assert session_repo._session.pending_entry is not None
    assert session_repo._session.pending_entry["diary"] == raw_text
