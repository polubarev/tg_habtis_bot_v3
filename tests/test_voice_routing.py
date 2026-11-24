import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.constants import FileSizeLimit
from telegram.error import BadRequest, NetworkError

from src.config.constants import BUTTONS_EN, MESSAGES_EN
from src.config.settings import Settings
from src.models.enums import InputType
from src.models.session import ConversationState, SessionData
from src.services.telegram.handlers import router as router_module
from src.services.telegram.utils import TELEGRAM_TEXT_CHUNK_SIZE, telegram_text_length
from src.services.transcription.interfaces import TranscriptionResult


class FakeSentMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.delete = AsyncMock()


class FakeMessage:
    def __init__(self, voice, *, message_id: int, fail_transcript_echo: bool = False) -> None:
        self.voice = voice
        self.message_id = message_id
        self.text = None
        self.fail_transcript_echo = fail_transcript_echo
        self.replies: list[tuple[str, dict, FakeSentMessage]] = []

    async def reply_text(self, text: str, **kwargs):
        if self.fail_transcript_echo and text.startswith("Voice transcription:"):
            raise BadRequest("send failed")
        sent = FakeSentMessage(text)
        self.replies.append((text, kwargs, sent))
        return sent


class FakeTelegramFile:
    def __init__(self, data: bytes = b"audio", error: Exception | None = None) -> None:
        self.data = data
        self.error = error
        self.download_as_bytearray = AsyncMock(side_effect=self._download)

    async def _download(self, **kwargs):
        if self.error:
            raise self.error
        return bytearray(self.data)


class FakeBot:
    def __init__(self, telegram_file: FakeTelegramFile) -> None:
        self.telegram_file = telegram_file
        self.get_file = AsyncMock(return_value=telegram_file)


class FakeTranscriber:
    def __init__(self, text: str) -> None:
        self.text = text
        self.transcribe = AsyncMock(
            return_value=TranscriptionResult(text=text, language="en")
        )


class FakeDeps:
    def __init__(
        self, transcriber: FakeTranscriber, settings: Settings, session: SessionData | None
    ) -> None:
        self._transcriber = transcriber
        self._session_repo = SimpleNamespace(get=AsyncMock(return_value=session), save=AsyncMock())
        self.settings = settings

    def session_repo(self):
        return self._session_repo

    def user_repo(self):
        return None

    def whisper_client(self):
        return self._transcriber


def build_voice_case(
    *,
    transcript: str = "hello",
    file_size: int = 1024,
    download_error: Exception | None = None,
    fail_transcript_echo: bool = False,
    session: SessionData | None = None,
    message_id: int = 1,
):
    settings = Settings(
        _env_file=None,
        telegram_download_timeout_seconds=1,
        transcription_timeout_seconds=1,
    )
    transcriber = FakeTranscriber(transcript)
    deps = FakeDeps(transcriber, settings, session)
    telegram_file = FakeTelegramFile(error=download_error)
    bot = FakeBot(telegram_file)
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"deps": deps}),
        bot=bot,
    )
    voice = SimpleNamespace(
        duration=415,
        file_size=file_size,
        file_id="voice-file-id",
    )
    message = FakeMessage(voice, message_id=message_id, fail_transcript_echo=fail_transcript_echo)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        message=message,
    )
    return update, context, transcriber, bot


@pytest.mark.asyncio
async def test_long_standalone_voice_transcript_is_chunked_and_replies_to_note():
    transcript = "x" * 4504
    update, context, transcriber, bot = build_voice_case(transcript=transcript)
    await router_module.route_media(update, context)

    assert update.message.replies[0][0] == MESSAGES_EN["processing"]
    transcript_chunks = [text for text, _, _ in update.message.replies[1:]]
    assert len(transcript_chunks) == 2
    assert all(
        telegram_text_length(chunk) <= TELEGRAM_TEXT_CHUNK_SIZE
        for chunk in transcript_chunks
    )
    assert "".join(transcript_chunks) == MESSAGES_EN["voice_transcribed"].format(
        text=transcript
    )
    assert all(
        options["reply_to_message_id"] == update.message.message_id
        for _, options, _ in update.message.replies[1:]
    )
    transcriber.transcribe.assert_awaited_once()
    bot.get_file.assert_awaited_once()
    update.message.replies[0][2].delete.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [
        ConversationState.IDLE,
        ConversationState.CONFIG_TIMEZONE,
        ConversationState.HABITS_AWAITING_CONFIRMATION,
    ],
)
async def test_standalone_voice_notes_leave_session_untouched(state):
    session = SessionData(user_id=123, state=state)
    transcript = BUTTONS_EN["cancel"]
    notes = [
        build_voice_case(transcript=transcript, session=session, message_id=message_id)
        for message_id in (11, 12)
    ]
    await asyncio.gather(
        *(router_module.route_media(update, context) for update, context, _, _ in notes)
    )

    for update, context, transcriber, _ in notes:
        transcriber.transcribe.assert_awaited_once()
        assert [text for text, _, _ in update.message.replies] == [
            MESSAGES_EN["processing"],
            MESSAGES_EN["voice_transcribed"].format(text=transcript),
        ]
        assert update.message.replies[-1][1]["reply_to_message_id"] == update.message.message_id
        router_module.get_session_repo(context).save.assert_not_awaited()
    assert session.state == state


@pytest.mark.asyncio
async def test_voice_note_still_appends_to_active_entry_collection(monkeypatch):
    session = SessionData(user_id=123, state=ConversationState.ENTRY_COLLECTING)
    update, context, _, _ = build_voice_case(transcript="my entry", session=session)
    append = AsyncMock(return_value=True)
    monkeypatch.setattr(router_module, "handle_entry_collection_text", append)

    await router_module.route_media(update, context)

    append.assert_awaited_once_with(update, context, "my entry", input_type=InputType.VOICE)
    assert [text for text, _, _ in update.message.replies] == [MESSAGES_EN["processing"]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "starting_state", [ConversationState.IDLE, ConversationState.ENTRY_COLLECTING]
)
async def test_voice_note_cannot_enter_new_collection_during_transcription(
    monkeypatch, starting_state
):
    session = SessionData(user_id=123, state=starting_state)
    update, context, transcriber, _ = build_voice_case(session=session)
    append = AsyncMock()
    monkeypatch.setattr(router_module, "handle_entry_collection_text", append)

    async def start_new_collection(*args, **kwargs):
        session.state = ConversationState.ENTRY_COLLECTING
        session.refresh_expiry(ttl_minutes=60)
        return TranscriptionResult(text="hello", language="en")

    transcriber.transcribe.side_effect = start_new_collection
    await router_module.route_media(update, context)

    append.assert_not_awaited()
    assert update.message.replies[-1][0] == MESSAGES_EN["voice_transcribed"].format(text="hello")


@pytest.mark.asyncio
async def test_voice_download_failure_returns_visible_error(monkeypatch):
    update, context, transcriber, _ = build_voice_case(
        download_error=NetworkError("download failed")
    )
    route_text = AsyncMock()
    monkeypatch.setattr(router_module, "route_text", route_text)

    await router_module.route_voice(update, context)

    assert [text for text, _, _ in update.message.replies] == [
        MESSAGES_EN["processing"],
        MESSAGES_EN["voice_download_error"],
    ]
    transcriber.transcribe.assert_not_awaited()
    route_text.assert_not_awaited()
    update.message.replies[0][2].delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_voice_download_timeout_returns_visible_error(monkeypatch):
    update, context, transcriber, _ = build_voice_case(
        download_error=asyncio.TimeoutError()
    )
    route_text = AsyncMock()
    monkeypatch.setattr(router_module, "route_text", route_text)

    await router_module.route_voice(update, context)

    assert [text for text, _, _ in update.message.replies] == [
        MESSAGES_EN["processing"],
        MESSAGES_EN["external_timeout_error"],
    ]
    transcriber.transcribe.assert_not_awaited()
    route_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_oversized_voice_is_rejected_before_download(monkeypatch):
    update, context, transcriber, bot = build_voice_case(
        file_size=int(FileSizeLimit.FILESIZE_DOWNLOAD) + 1
    )
    route_text = AsyncMock()
    monkeypatch.setattr(router_module, "route_text", route_text)

    await router_module.route_voice(update, context)

    assert [text for text, _, _ in update.message.replies] == [
        MESSAGES_EN["processing"],
        MESSAGES_EN["voice_too_large"],
    ]
    bot.get_file.assert_not_awaited()
    transcriber.transcribe.assert_not_awaited()
    route_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_transcription_timeout_returns_visible_error(monkeypatch):
    update, context, transcriber, _ = build_voice_case()
    transcriber.transcribe.side_effect = asyncio.TimeoutError()
    route_text = AsyncMock()
    monkeypatch.setattr(router_module, "route_text", route_text)

    await router_module.route_voice(update, context)

    assert [text for text, _, _ in update.message.replies] == [
        MESSAGES_EN["processing"],
        MESSAGES_EN["external_timeout_error"],
    ]
    route_text.assert_not_awaited()
    update.message.replies[0][2].delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_transcript_display_failure_does_not_block_routing(monkeypatch):
    transcript = "still route this"
    update, context, _, _ = build_voice_case(
        transcript=transcript,
        fail_transcript_echo=True,
        session=SessionData(user_id=123, state=ConversationState.HABITS_AWAITING_CONTENT),
    )
    habits = AsyncMock()
    monkeypatch.setattr(router_module, "handle_habits_text", habits)

    await router_module.route_voice(update, context)

    habits.assert_awaited_once_with(update, context, transcript, input_type=InputType.VOICE)
