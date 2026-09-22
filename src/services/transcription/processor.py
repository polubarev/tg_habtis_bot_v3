from __future__ import annotations

import asyncio
from io import BytesIO

from telegram import Bot
from telegram.error import NetworkError, TelegramError, TimedOut

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.config.settings import Settings
from src.core.analytics import log_event
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, TranscriptionError
from src.models.transcription_batch import (
    TranscriptionBatch,
    TranscriptionBatchStatus,
    TranscriptionItemStatus,
    TranscriptionMediaType,
)
from src.services.storage.firestore.transcription_batch_repo import TranscriptionBatchRepository
from src.services.transcription.whisper import WhisperClient


class RetryableBatchError(RuntimeError):
    pass


def _duration_text(seconds: int) -> str:
    minutes, remaining = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{remaining:02d}" if hours else f"{minutes}:{remaining:02d}"


def _media_label(media_type: TranscriptionMediaType, lang: str) -> str:
    labels = {
        "ru": {
            TranscriptionMediaType.VOICE: "Голос",
            TranscriptionMediaType.AUDIO: "Аудио",
            TranscriptionMediaType.VIDEO: "Видео",
            TranscriptionMediaType.VIDEO_NOTE: "Видеосообщение",
        },
        "en": {
            TranscriptionMediaType.VOICE: "Voice",
            TranscriptionMediaType.AUDIO: "Audio",
            TranscriptionMediaType.VIDEO: "Video",
            TranscriptionMediaType.VIDEO_NOTE: "Video message",
        },
    }
    return labels["ru" if lang == "ru" else "en"][media_type]


def format_batch_result(batch: TranscriptionBatch, lang: str) -> str:
    msgs = MESSAGES_RU if lang == "ru" else MESSAGES_EN
    sections = [msgs["transcription_result_title"]]
    for item in sorted(batch.items, key=lambda value: value.index):
        header = f"{item.index}. {_media_label(item.media_type, lang)} · {_duration_text(item.duration_seconds)}"
        body = (
            item.transcript.strip()
            if item.status == TranscriptionItemStatus.COMPLETED and item.transcript
            else msgs["transcription_item_failed"]
        )
        sections.append(f"{header}\n{body}")
    return "\n\n".join(sections)


def split_result_text(text: str, limit: int = 3800) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        boundary = remaining.rfind("\n\n", 0, limit)
        if boundary < limit // 2:
            boundary = remaining.rfind("\n", 0, limit)
        if boundary < limit // 2:
            boundary = remaining.rfind(" ", 0, limit)
        if boundary <= 0:
            boundary = limit
        chunks.append(remaining[:boundary].rstrip())
        remaining = remaining[boundary:].lstrip()
    return chunks


class TranscriptionBatchProcessor:
    def __init__(
        self,
        settings: Settings,
        repo: TranscriptionBatchRepository,
        transcriber: WhisperClient,
        user_repo,
    ):
        self.settings = settings
        self.repo = repo
        self.transcriber = transcriber
        self.user_repo = user_repo

    def _bot(self) -> Bot:
        token = self.settings.get_telegram_bot_token()
        if not token:
            raise RuntimeError("Telegram bot token is not configured")
        return Bot(token=token)

    async def process(self, user_id: int, batch_id: str, retry_count: int = 0) -> str:
        batch = await self.repo.claim(user_id, batch_id)
        if batch is None:
            return "stale"
        if batch.delivered_at:
            return "already_delivered"
        if batch.status in {TranscriptionBatchStatus.CANCELLED, TranscriptionBatchStatus.COLLECTING}:
            return "not_queued"
        if batch.status in {
            TranscriptionBatchStatus.QUEUED,
            TranscriptionBatchStatus.PROCESSING,
        }:
            bot = self._bot()
            for item in sorted(batch.items, key=lambda value: value.index):
                if item.status != TranscriptionItemStatus.PENDING:
                    continue
                try:
                    tg_file = await asyncio.wait_for(
                        bot.get_file(item.file_id),
                        timeout=self.settings.telegram_download_timeout_seconds,
                    )
                    if tg_file.file_size and tg_file.file_size > self.settings.transcription_max_file_bytes:
                        await self.repo.checkpoint_item(
                            user_id, batch_id, item.index, error_code="file_too_large"
                        )
                        continue
                    data = await asyncio.wait_for(
                        tg_file.download_as_bytearray(),
                        timeout=self.settings.telegram_download_timeout_seconds,
                    )
                    if len(data) > self.settings.transcription_max_file_bytes:
                        await self.repo.checkpoint_item(
                            user_id, batch_id, item.index, error_code="file_too_large"
                        )
                        continue
                    result = await asyncio.wait_for(
                        self.transcriber.transcribe(bytes(data), format=item.file_format),
                        timeout=self.settings.transcription_timeout_seconds,
                    )
                    await self.repo.checkpoint_item(
                        user_id, batch_id, item.index, transcript=result.text.strip()
                    )
                except ExternalResponseError:
                    await self.repo.checkpoint_item(
                        user_id, batch_id, item.index, error_code="unsupported_media"
                    )
                except (asyncio.TimeoutError, ExternalTimeoutError, TranscriptionError, NetworkError, TimedOut):
                    if retry_count + 1 < self.settings.transcription_task_max_attempts:
                        raise RetryableBatchError("transient transcription failure")
                    await self.repo.checkpoint_item(
                        user_id, batch_id, item.index, error_code="retry_exhausted"
                    )
                except Exception:
                    if retry_count + 1 < self.settings.transcription_task_max_attempts:
                        raise RetryableBatchError("transient media failure")
                    await self.repo.checkpoint_item(
                        user_id, batch_id, item.index, error_code="media_failed"
                    )
            batch = await self.repo.complete(user_id, batch_id)

        profile = await self.user_repo.get_by_telegram_id(user_id) if self.user_repo else None
        lang = profile.language if profile and profile.language == "ru" else "en"
        try:
            await self._deliver(batch, lang)
        except RetryableBatchError:
            if retry_count + 1 < self.settings.transcription_task_max_attempts:
                raise
            await self.repo.mark_delivered_and_purge(user_id, batch_id)
            log_event(
                "transcription.batch_delivery_failed",
                user_id=user_id,
                item_count=len(batch.items),
            )
            return "delivery_failed"
        await self.repo.mark_delivered_and_purge(user_id, batch_id)
        completed = sum(i.status == TranscriptionItemStatus.COMPLETED for i in batch.items)
        failed = sum(i.status == TranscriptionItemStatus.FAILED for i in batch.items)
        log_event(
            "transcription.batch_completed",
            user_id=user_id,
            item_count=len(batch.items),
            completed_count=completed,
            failed_count=failed,
            duration_s=batch.total_duration_seconds,
        )
        return "delivered"

    async def _deliver(self, batch: TranscriptionBatch, lang: str) -> None:
        bot = self._bot()
        msgs = MESSAGES_RU if lang == "ru" else MESSAGES_EN
        text = format_batch_result(batch, lang)
        chunks = split_result_text(text)
        try:
            if len(chunks) <= 3:
                for chunk in chunks:
                    await bot.send_message(chat_id=batch.chat_id, text=chunk)
            else:
                await bot.send_message(
                    chat_id=batch.chat_id, text=msgs["transcription_result_file"]
                )
                document = BytesIO(text.encode("utf-8"))
                document.name = f"transcription-{batch.batch_id[:8]}.txt"
                await bot.send_document(
                    chat_id=batch.chat_id,
                    document=document,
                    filename=document.name,
                )
        except (NetworkError, TelegramError, TimedOut) as exc:
            raise RetryableBatchError("transcript delivery failed") from exc
