from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import BUTTONS_EN, BUTTONS_RU, MESSAGES_EN, MESSAGES_RU
from src.core.analytics import log_event
from src.models.session import ConversationState, SessionData
from src.models.transcription_batch import (
    TranscriptionBatchItem,
    TranscriptionBatchStatus,
    TranscriptionMediaType,
)
from src.services.telegram.keyboards import (
    build_main_menu_keyboard,
    build_transcription_keyboard,
)
from src.services.telegram.utils import (
    get_session_repo,
    get_settings_from_context,
    get_transcription_batch_repo,
    get_transcription_scheduler,
    record_usage_event,
    resolve_language,
    resolve_user_profile,
)
from src.services.transcription.scheduler import TranscriptionScheduleError


@dataclass(frozen=True)
class TelegramMedia:
    file_id: str
    file_unique_id: str
    media_type: TranscriptionMediaType
    file_format: str
    mime_type: str | None
    file_size: int
    duration_seconds: int


def extract_supported_media(message) -> TelegramMedia | None:
    media = None
    media_type = None
    default_format = "ogg"
    if getattr(message, "voice", None):
        media = message.voice
        media_type = TranscriptionMediaType.VOICE
    elif getattr(message, "audio", None):
        media = message.audio
        media_type = TranscriptionMediaType.AUDIO
        default_format = "mp3"
    elif getattr(message, "video", None):
        media = message.video
        media_type = TranscriptionMediaType.VIDEO
        default_format = "mp4"
    elif getattr(message, "video_note", None):
        media = message.video_note
        media_type = TranscriptionMediaType.VIDEO_NOTE
        default_format = "mp4"
    if media is None or media_type is None:
        return None

    file_name = getattr(media, "file_name", None)
    suffix = Path(file_name).suffix.lstrip(".").lower() if file_name else ""
    file_format = suffix or default_format
    return TelegramMedia(
        file_id=media.file_id,
        file_unique_id=media.file_unique_id,
        media_type=media_type,
        file_format=file_format,
        mime_type=getattr(media, "mime_type", None),
        file_size=int(getattr(media, "file_size", 0) or 0),
        duration_seconds=int(getattr(media, "duration", 0) or 0),
    )


def _duration_text(seconds: int) -> str:
    minutes, remaining = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


async def transcription_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_chat or not update.message:
        return
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = MESSAGES_RU if lang == "ru" else MESSAGES_EN
    settings = get_settings_from_context(context)
    repo = get_transcription_batch_repo(context)
    session_repo = get_session_repo(context)
    if repo is None or session_repo is None:
        await update.message.reply_text(msgs["transcription_enqueue_error"])
        return

    batch = await repo.create_or_resume(
        update.effective_user.id,
        update.effective_chat.id,
        settings.session_ttl_minutes,
    )
    if batch.status == TranscriptionBatchStatus.PROCESSING:
        await update.message.reply_text(
            msgs["transcription_processing"], reply_markup=build_main_menu_keyboard(lang)
        )
        return

    session = await session_repo.get(update.effective_user.id) or SessionData(
        user_id=update.effective_user.id
    )
    session.state = ConversationState.TRANSCRIPTION_COLLECTING
    session.temp_data = {"transcription_batch_id": batch.batch_id}
    await session_repo.save(session)
    if batch.status == TranscriptionBatchStatus.QUEUED:
        text = msgs["transcription_retry_ready"].format(count=len(batch.items))
    elif batch.items:
        text = msgs["transcription_resumed"].format(
            count=len(batch.items), max_items=settings.transcription_max_items
        )
    else:
        text = msgs["transcription_prompt"]
    await update.message.reply_text(text, reply_markup=build_transcription_keyboard(lang))
    log_event("transcription.batch_started", user_id=update.effective_user.id)


async def _submit_batch(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    batch_id: str,
) -> bool:
    if not update.effective_user or not update.message:
        return False
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = MESSAGES_RU if lang == "ru" else MESSAGES_EN
    repo = get_transcription_batch_repo(context)
    scheduler = get_transcription_scheduler(context)
    session_repo = get_session_repo(context)
    if repo is None or scheduler is None or session_repo is None:
        await update.message.reply_text(msgs["transcription_enqueue_error"])
        return False
    batch = await repo.get(update.effective_user.id)
    if batch is None or batch.batch_id != batch_id or not batch.items:
        await update.message.reply_text(
            msgs["transcription_empty"], reply_markup=build_transcription_keyboard(lang)
        )
        return False
    if batch.status not in {
        TranscriptionBatchStatus.COLLECTING,
        TranscriptionBatchStatus.QUEUED,
    }:
        await update.message.reply_text(msgs["transcription_processing"])
        return False

    if batch.status == TranscriptionBatchStatus.COLLECTING:
        batch = await repo.queue(update.effective_user.id, batch_id)
    try:
        await scheduler.enqueue(update.effective_user.id, batch_id)
    except TranscriptionScheduleError:
        await update.message.reply_text(
            msgs["transcription_enqueue_error"], reply_markup=build_transcription_keyboard(lang)
        )
        return False

    session = await session_repo.get(update.effective_user.id) or SessionData(
        user_id=update.effective_user.id
    )
    session.reset()
    await session_repo.save(session)
    await update.message.reply_text(
        msgs["transcription_queued"].format(count=len(batch.items)),
        reply_markup=build_main_menu_keyboard(lang),
    )
    await record_usage_event(
        context,
        "transcription.batch_queued",
        user_id=update.effective_user.id,
        metadata={"item_count": len(batch.items), "duration_s": batch.total_duration_seconds},
    )
    return True


async def handle_transcription_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> bool:
    if not update.effective_user or not update.message:
        return False
    session_repo = get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.TRANSCRIPTION_COLLECTING:
        return False

    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = MESSAGES_RU if lang == "ru" else MESSAGES_EN
    repo = get_transcription_batch_repo(context)
    batch_id = str(session.temp_data.get("transcription_batch_id", ""))
    if not repo or not batch_id:
        session.reset()
        if session_repo:
            await session_repo.save(session)
        return False

    if text in {BUTTONS_RU["cancel"], BUTTONS_EN["cancel"]}:
        await repo.cancel(update.effective_user.id, batch_id)
        session.reset()
        await session_repo.save(session)
        await update.message.reply_text(
            msgs["transcription_cancelled"], reply_markup=build_main_menu_keyboard(lang)
        )
        return True
    if text in {BUTTONS_RU["transcription_clear"], BUTTONS_EN["transcription_clear"]}:
        await repo.clear(
            update.effective_user.id, batch_id, get_settings_from_context(context).session_ttl_minutes
        )
        await update.message.reply_text(
            msgs["transcription_cleared"], reply_markup=build_transcription_keyboard(lang)
        )
        return True
    if text in {BUTTONS_RU["transcription_finish"], BUTTONS_EN["transcription_finish"]}:
        await _submit_batch(update, context, batch_id)
        return True

    await update.message.reply_text(
        msgs["transcription_collecting_only"], reply_markup=build_transcription_keyboard(lang)
    )
    return True


async def handle_transcription_media(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    if not update.effective_user or not update.message:
        return False
    session_repo = get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.TRANSCRIPTION_COLLECTING:
        return False

    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = MESSAGES_RU if lang == "ru" else MESSAGES_EN
    settings = get_settings_from_context(context)
    media = extract_supported_media(update.message)
    if media is None:
        await update.message.reply_text(msgs["transcription_collecting_only"])
        return True
    if media.file_size > settings.transcription_max_file_bytes:
        await update.message.reply_text(msgs["transcription_too_large"])
        log_event(
            "transcription.item_rejected",
            user_id=update.effective_user.id,
            reason="file_too_large",
        )
        return True

    repo = get_transcription_batch_repo(context)
    batch_id = str(session.temp_data.get("transcription_batch_id", ""))
    if repo is None or not batch_id:
        return False
    item = TranscriptionBatchItem(
        message_id=update.message.message_id,
        file_id=media.file_id,
        file_unique_id=media.file_unique_id,
        media_type=media.media_type,
        file_format=media.file_format,
        mime_type=media.mime_type,
        file_size=media.file_size,
        duration_seconds=media.duration_seconds,
    )
    result = await repo.append_item(
        update.effective_user.id,
        batch_id,
        item,
        max_items=settings.transcription_max_items,
        max_duration_seconds=settings.transcription_max_duration_seconds,
        ttl_minutes=settings.session_ttl_minutes,
    )
    error_keys = {
        "duplicate": "transcription_duplicate",
        "duration_limit": "transcription_duration_limit",
        "full": "transcription_full",
        "expired": "transcription_cancelled",
        "not_collecting": "transcription_processing",
    }
    if result.code != "accepted":
        if result.code == "expired":
            await repo.cancel(update.effective_user.id, batch_id)
            session.reset()
            await session_repo.save(session)
            await update.message.reply_text(
                msgs["transcription_cancelled"], reply_markup=build_main_menu_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                msgs[error_keys.get(result.code, "transcription_enqueue_error")]
            )
        log_event(
            "transcription.item_rejected",
            user_id=update.effective_user.id,
            reason=result.code,
        )
        return True

    count = len(result.batch.items)
    await update.message.reply_text(
        msgs["transcription_added"].format(
            count=count,
            max_items=settings.transcription_max_items,
            duration=_duration_text(result.batch.total_duration_seconds),
        ),
        reply_markup=build_transcription_keyboard(lang),
    )
    await record_usage_event(
        context,
        "transcription.item_accepted",
        user_id=update.effective_user.id,
        metadata={"media_type": media.media_type.value, "duration_s": media.duration_seconds},
    )
    if count >= settings.transcription_max_items:
        await _submit_batch(update, context, batch_id)
    return True
