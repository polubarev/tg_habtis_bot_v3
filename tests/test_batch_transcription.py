import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.models.transcription_batch import (
    TranscriptionBatch,
    TranscriptionBatchItem,
    TranscriptionItemStatus,
    TranscriptionMediaType,
)
from src.config.settings import Settings
from src.models.session import ConversationState
from src.models.session import SessionData
from src.services.storage.firestore.transcription_batch_repo import TranscriptionBatchRepository
from src.services.telegram.handlers.transcription import (
    extract_supported_media,
    handle_transcription_media,
    transcription_command,
)
from src.services.transcription.processor import format_batch_result, split_result_text
from src.services.transcription import processor as processor_module
from src.services.transcription.interfaces import TranscriptionResult
from src.services.transcription.processor import RetryableBatchError, TranscriptionBatchProcessor
from src.core.exceptions import ExternalTimeoutError
from src.services.transcription.scheduler import build_transcription_dispatch_url


def _item(unique_id: str, duration: int = 10) -> TranscriptionBatchItem:
    return TranscriptionBatchItem(
        message_id=int(unique_id.strip("f") or "1"),
        file_id=f"file-{unique_id}",
        file_unique_id=unique_id,
        media_type=TranscriptionMediaType.VOICE,
        file_format="ogg",
        file_size=100,
        duration_seconds=duration,
    )


@pytest.mark.asyncio
async def test_concurrent_appends_keep_all_items_in_order():
    repo = TranscriptionBatchRepository()
    batch = await repo.create_or_resume(1, 10, 60)

    results = await asyncio.gather(
        *(
            repo.append_item(
                1,
                batch.batch_id,
                _item(str(index)),
                max_items=10,
                max_duration_seconds=3600,
                ttl_minutes=60,
            )
            for index in range(1, 11)
        )
    )

    stored = await repo.get(1)
    assert stored is not None
    assert all(result.code == "accepted" for result in results)
    assert len(stored.items) == 10
    assert [item.index for item in stored.items] == list(range(1, 11))


@pytest.mark.asyncio
async def test_duplicate_and_duration_limit_do_not_change_batch():
    repo = TranscriptionBatchRepository()
    batch = await repo.create_or_resume(2, 20, 60)
    first = await repo.append_item(
        2,
        batch.batch_id,
        _item("1", 3500),
        max_items=10,
        max_duration_seconds=3600,
        ttl_minutes=60,
    )
    duplicate = await repo.append_item(
        2,
        batch.batch_id,
        _item("1", 10),
        max_items=10,
        max_duration_seconds=3600,
        ttl_minutes=60,
    )
    too_long = await repo.append_item(
        2,
        batch.batch_id,
        _item("2", 101),
        max_items=10,
        max_duration_seconds=3600,
        ttl_minutes=60,
    )

    assert first.code == "accepted"
    assert duplicate.code == "duplicate"
    assert too_long.code == "duration_limit"
    stored = await repo.get(2)
    assert stored is not None
    assert len(stored.items) == 1


@pytest.mark.parametrize(
    ("attribute", "expected_type", "expected_format"),
    [
        ("voice", TranscriptionMediaType.VOICE, "ogg"),
        ("audio", TranscriptionMediaType.AUDIO, "m4a"),
        ("video", TranscriptionMediaType.VIDEO, "mp4"),
        ("video_note", TranscriptionMediaType.VIDEO_NOTE, "mp4"),
    ],
)
def test_extract_supported_media(attribute, expected_type, expected_format):
    media = SimpleNamespace(
        file_id="secret-file-id",
        file_unique_id="stable-id",
        file_name="recording.m4a" if attribute == "audio" else None,
        mime_type="audio/mp4" if attribute == "audio" else None,
        file_size=123,
        duration=12,
    )
    message = SimpleNamespace(voice=None, audio=None, video=None, video_note=None)
    setattr(message, attribute, media)

    result = extract_supported_media(message)

    assert result is not None
    assert result.media_type == expected_type
    assert result.file_format == expected_format
    assert not hasattr(result, "forward_origin")


def test_format_result_preserves_order_and_marks_failures():
    batch = TranscriptionBatch(user_id=1, chat_id=1)
    second = _item("2")
    second.index = 2
    second.status = TranscriptionItemStatus.FAILED
    first = _item("1")
    first.index = 1
    first.status = TranscriptionItemStatus.COMPLETED
    first.transcript = "Hello world"
    batch.items = [second, first]

    text = format_batch_result(batch, "en")

    assert text.index("1. Voice") < text.index("2. Voice")
    assert "Hello world" in text
    assert "could not be transcribed" in text


def test_split_result_text_respects_limit():
    chunks = split_result_text("paragraph\n\n" * 100, limit=100)
    assert len(chunks) > 3
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_dispatch_url_replaces_telegram_webhook_suffix():
    assert (
        build_transcription_dispatch_url("https://example.test/telegram/webhook")
        == "https://example.test/transcriptions/dispatch"
    )


def test_aware_session_expiry_does_not_raise():
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    past = datetime.now(timezone.utc) - timedelta(minutes=5)

    assert SessionData(user_id=1, expires_at=future).is_expired() is False
    assert SessionData(user_id=1, expires_at=past).is_expired() is True


def test_aware_batch_expiry_does_not_raise():
    batch = TranscriptionBatch(
        user_id=1,
        chat_id=1,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    assert batch.is_collecting_expired is True


class _SessionRepo:
    def __init__(self):
        self.value = None

    async def get(self, user_id):
        return self.value

    async def save(self, session):
        self.value = session


class _Scheduler:
    def __init__(self):
        self.calls = []

    async def enqueue(self, user_id, batch_id):
        self.calls.append((user_id, batch_id))
        return "task"


class _Deps:
    def __init__(self):
        self.settings = Settings(
            transcription_max_items=10,
            transcription_max_duration_seconds=3600,
        )
        self.sessions = _SessionRepo()
        self.batches = TranscriptionBatchRepository()
        self.scheduler = _Scheduler()

    def session_repo(self):
        return self.sessions

    def transcription_batch_repo(self):
        return self.batches

    def transcription_scheduler(self):
        return self.scheduler

    def user_repo(self):
        return None


class _Message:
    def __init__(self, message_id=1, voice=None):
        self.message_id = message_id
        self.voice = voice
        self.audio = None
        self.video = None
        self.video_note = None
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))


def _context(deps):
    return SimpleNamespace(application=SimpleNamespace(bot_data={"deps": deps}))


def _update(message):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        effective_chat=SimpleNamespace(id=42),
        message=message,
    )


@pytest.mark.asyncio
async def test_tenth_item_queues_automatically_and_resets_session():
    deps = _Deps()
    context = _context(deps)
    await transcription_command(_update(_Message()), context)

    for index in range(1, 11):
        voice = SimpleNamespace(
            file_id=f"file-{index}",
            file_unique_id=f"unique-{index}",
            file_size=100,
            duration=10,
            mime_type="audio/ogg",
        )
        handled = await handle_transcription_media(
            _update(_Message(message_id=index, voice=voice)), context
        )
        assert handled is True

    assert len(deps.scheduler.calls) == 1
    assert deps.sessions.value is not None
    assert deps.sessions.value.state == ConversationState.IDLE


class _TelegramFile:
    file_size = 100

    async def download_as_bytearray(self):
        return bytearray(b"audio")


class _Bot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def get_file(self, file_id):
        return _TelegramFile()

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id, document, filename):
        self.documents.append((chat_id, filename))


class _UserRepo:
    async def get_by_telegram_id(self, user_id):
        return SimpleNamespace(language="en")


class _Transcriber:
    def __init__(self, fail_once=False):
        self.calls = 0
        self.fail_once = fail_once

    async def transcribe(self, data, format="ogg"):
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise ExternalTimeoutError("temporary")
        return TranscriptionResult(text="checkpointed transcript")


@pytest.mark.asyncio
async def test_processor_retries_pending_item_then_purges_content(monkeypatch):
    repo = TranscriptionBatchRepository()
    batch = await repo.create_or_resume(99, 99, 60)
    await repo.append_item(
        99,
        batch.batch_id,
        _item("9"),
        max_items=10,
        max_duration_seconds=3600,
        ttl_minutes=60,
    )
    await repo.queue(99, batch.batch_id)
    bot = _Bot()
    monkeypatch.setattr(processor_module, "Bot", lambda token: bot)
    transcriber = _Transcriber(fail_once=True)
    settings = Settings(
        telegram_bot_token="test-token",
        operation_timeout_seconds=5,
        transcription_task_max_attempts=5,
    )
    processor = TranscriptionBatchProcessor(settings, repo, transcriber, _UserRepo())

    with pytest.raises(RetryableBatchError):
        await processor.process(99, batch.batch_id, retry_count=0)

    pending = await repo.get(99)
    assert pending is not None
    assert pending.items[0].status == TranscriptionItemStatus.PENDING

    assert await processor.process(99, batch.batch_id, retry_count=1) == "delivered"
    delivered = await repo.get(99)
    assert delivered is not None
    assert delivered.delivered_at is not None
    assert delivered.items[0].file_id == ""
    assert delivered.items[0].transcript is None
    assert transcriber.calls == 2
    assert "checkpointed transcript" in bot.messages[0][1]
