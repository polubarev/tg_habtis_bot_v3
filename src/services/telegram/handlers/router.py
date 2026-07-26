import asyncio
import time
from datetime import timedelta

from telegram import Update
from telegram.constants import FileSizeLimit, ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from src.services.telegram.handlers.config import (
    handle_config_text,
    config_command,
    handle_timezone_text,
    reset_command,
    reminder_command,
    handle_reminder_text,
    handle_on_this_day_text,
    handle_smart_nudges_rollover_text,
    handle_smart_nudges_times_text,
    looks_like_sheet_input,
)
from src.services.telegram.handlers.habits_config import handle_habits_config_text, habits_config_command
from src.services.telegram.handlers.questions import handle_questions_text, questions_command
from src.services.telegram.handlers.dream import handle_dream_text, dream_command
from src.services.telegram.handlers.habits import handle_habits_text, habits_command, handle_habits_date_text
from src.services.telegram.handlers.reflect import handle_reflect_text, reflect_command
from src.services.telegram.handlers.thought import handle_thought_text, thought_command
from src.services.telegram.handlers.help import help_command
from src.services.telegram.handlers.feedback import feedback_command, handle_feedback_text
from src.services.telegram.handlers.week_analysis import week_analysis_command
from src.services.telegram.handlers.on_this_day import on_this_day_command
from src.services.telegram.handlers.admin import handle_admin_broadcast_text, handle_admin_text
from src.services.telegram.keyboards import build_main_menu_keyboard, build_config_keyboard
from src.services.transcription.whisper import WhisperClient
from src.models.session import ConversationState, SessionData
from src.models.enums import InputType
from src.config.constants import MESSAGES_EN, MESSAGES_RU, BUTTONS_RU, BUTTONS_EN
from src.core.analytics import log_event
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, TranscriptionError
from src.core.logging import get_logger
from src.services.telegram.handlers.language import language_command
from src.services.telegram.utils import (
    get_settings_from_context,
    get_session_repo,
    get_whisper_client,
    record_usage_event,
    reply_text_chunked,
    resolve_language,
    resolve_user_profile,
    safe_delete_message,
)


logger = get_logger(__name__)


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


async def route_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_override: str | None = None) -> None:
    """Route plain text messages based on conversation state."""

    if not update.message or not update.effective_user:
        return
    text = text_override or update.message.text
    if not text:
        return
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = _messages_for_lang(lang)

    # Helper to check against all languages
    def matched(key: str) -> bool:
        return text in (BUTTONS_RU.get(key), BUTTONS_EN.get(key))

    # 1. Global Cancel
    if matched("cancel"):
        # Reset session
        session_repo = get_session_repo(context)
        if session_repo and update.effective_user:
            session = await session_repo.get(update.effective_user.id)
            if session:
                session.reset()
                await session_repo.save(session)
        
        await update.message.reply_text(msgs["cancelled"], reply_markup=build_main_menu_keyboard(lang))
        return

    # 2. Navigation
    if matched("back"):
        await update.message.reply_text(msgs["main_menu"], reply_markup=build_main_menu_keyboard(lang))
        return

    if matched("config"):
        await update.message.reply_text(msgs["config_menu"], reply_markup=build_config_keyboard(lang))
        return

    # 3. Main Action Buttons
    if matched("habits"):
        await habits_command(update, context)
        return
    if matched("dream"):
        await dream_command(update, context)
        return
    if matched("thought"):
        await thought_command(update, context)
        return
    if matched("reflect"):
        await reflect_command(update, context)
        return
    if matched("week_analysis"):
        await week_analysis_command(update, context)
        return
    if matched("on_this_day"):
        await on_this_day_command(update, context)
        return
    if matched("help"):
        await help_command(update, context)
        return

    # 4. Config Sub-buttons
    if matched("sheet_config"):
        await config_command(update, context)
        return
    if matched("habits_config"):
        await habits_config_command(update, context)
        return
    if matched("reset"):
        await reset_command(update, context)
        return
    if matched("reflect_config"):
        await questions_command(update, context)
        return
    if matched("timezone"):
        # Prompt for new timezone
        await update.message.reply_text(
            msgs["timezone_prompt"].format(tz=(profile.timezone if profile else "Europe/Moscow")),
            reply_markup=build_main_menu_keyboard(lang),
        )
        # Set state
        session_repo = get_session_repo(context)
        if session_repo:
            session = await session_repo.get(update.effective_user.id) or SessionData(user_id=update.effective_user.id)
            session.state = ConversationState.CONFIG_TIMEZONE
            await session_repo.save(session)
        return
    if matched("reminders"):
        await reminder_command(update, context)
        return
    if matched("language"):
        await language_command(update, context)
        return
    if matched("feedback"):
        await feedback_command(update, context)
        return

    if await handle_admin_text(update, context):
        return

    if await handle_admin_broadcast_text(update, context):
        return

    if looks_like_sheet_input(text):
        session_repo = get_session_repo(context)
        session = await session_repo.get(update.effective_user.id) if session_repo and update.effective_user else None
        should_prompt = session is None or session.state != ConversationState.CONFIG_AWAITING_SHEET_URL
        if session_repo and update.effective_user:
            session = session or SessionData(user_id=update.effective_user.id)
            session.state = ConversationState.CONFIG_AWAITING_SHEET_URL
            await session_repo.save(session)
        if should_prompt and update.message:
            await update.message.reply_text(msgs["sheet_detected"])
        if await handle_config_text(update, context):
            return

    session_repo = get_session_repo(context)
    session = (
        await session_repo.get(update.effective_user.id)
        if session_repo and update.effective_user
        else None
    )

    handled = False
    # Route active conversations by their persisted state. This prevents unrelated
    # handlers (for example Sheet configuration) from consuming habit dates.
    if session:
        state = session.state
        if state == ConversationState.CONFIG_TIMEZONE:
            handled = await handle_timezone_text(update, context)
        elif state == ConversationState.CONFIG_REMINDER_TIME:
            handled = await handle_reminder_text(update, context)
        elif state == ConversationState.CONFIG_ON_THIS_DAY_TIME:
            handled = await handle_on_this_day_text(update, context)
        elif state == ConversationState.CONFIG_SMART_NUDGES_TIMES:
            handled = await handle_smart_nudges_times_text(update, context)
        elif state == ConversationState.CONFIG_SMART_NUDGES_ROLLOVER:
            handled = await handle_smart_nudges_rollover_text(update, context)
        elif state == ConversationState.CONFIG_AWAITING_SHEET_URL:
            handled = await handle_config_text(update, context)
        elif state == ConversationState.CONFIG_FEEDBACK:
            handled = await handle_feedback_text(update, context)
        elif state == ConversationState.CONFIG_EDITING_HABITS:
            handled = await handle_habits_config_text(update, context)
        elif state == ConversationState.CONFIG_ADDING_QUESTION:
            handled = await handle_questions_text(update, context)
        elif state == ConversationState.HABITS_AWAITING_DATE:
            handled = await handle_habits_date_text(update, context, text)
        elif state == ConversationState.HABITS_AWAITING_CONTENT:
            handled = await handle_habits_text(update, context, text)
        elif state == ConversationState.DREAM_AWAITING_CONTENT:
            handled = await handle_dream_text(update, context, text)
        elif state == ConversationState.THOUGHT_AWAITING_CONTENT:
            handled = await handle_thought_text(update, context, text)
        elif state == ConversationState.REFLECT_ANSWERING_QUESTIONS:
            handled = await handle_reflect_text(update, context, text)

    if not handled and update.message:
        await update.message.reply_text(
            msgs["help"],
            reply_markup=build_main_menu_keyboard(lang),
            parse_mode=ParseMode.MARKDOWN,
        )


async def route_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route voice messages: transcribe then reuse text handlers."""

    if not update.message or not update.message.voice or not update.effective_user:
        return
    voice = update.message.voice
    duration = voice.duration
    duration_seconds = (
        int(duration.total_seconds())
        if isinstance(duration, timedelta)
        else duration
    )
    log_event(
        "voice.received",
        user_id=update.effective_user.id if update.effective_user else None,
        duration_s=duration_seconds,
        file_size=voice.file_size,
    )
    await record_usage_event(
        context,
        "voice.received",
        user_id=update.effective_user.id if update.effective_user else None,
        metadata={
            "duration_s": duration_seconds,
            **({"file_size": voice.file_size} if voice.file_size is not None else {}),
        },
    )
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = _messages_for_lang(lang)
    settings = get_settings_from_context(context)
    whisper_client: WhisperClient | None = get_whisper_client(context)
    if whisper_client is None:
        await update.message.reply_text(msgs["voice_disabled"])
        return

    progress_message = await update.message.reply_text(msgs["processing"])
    if voice.file_size and voice.file_size > int(FileSizeLimit.FILESIZE_DOWNLOAD):
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["voice_too_large"])
        return

    async def download_voice() -> bytearray:
        timeout = settings.telegram_download_timeout_seconds
        tg_file = await context.bot.get_file(
            voice.file_id,
            read_timeout=timeout,
            write_timeout=timeout,
            connect_timeout=timeout,
            pool_timeout=timeout,
        )
        return await tg_file.download_as_bytearray(
            read_timeout=timeout,
            write_timeout=timeout,
            connect_timeout=timeout,
            pool_timeout=timeout,
        )

    download_started = time.monotonic()
    try:
        data = await asyncio.wait_for(
            download_voice(),
            timeout=settings.telegram_download_timeout_seconds,
        )
        log_event(
            "voice.download",
            user_id=update.effective_user.id,
            latency_ms=int((time.monotonic() - download_started) * 1000),
            audio_bytes=len(data),
            ok=True,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Voice download timed out",
            user_id=update.effective_user.id,
            file_size=voice.file_size,
        )
        log_event(
            "voice.download",
            user_id=update.effective_user.id,
            latency_ms=int((time.monotonic() - download_started) * 1000),
            audio_bytes=voice.file_size,
            ok=False,
            error="timeout",
        )
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except TelegramError as exc:
        logger.warning(
            "Voice download failed",
            user_id=update.effective_user.id,
            error=type(exc).__name__,
        )
        log_event(
            "voice.download",
            user_id=update.effective_user.id,
            latency_ms=int((time.monotonic() - download_started) * 1000),
            audio_bytes=voice.file_size,
            ok=False,
            error=type(exc).__name__,
        )
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["voice_download_error"])
        return
    except Exception as exc:
        logger.exception(
            "Unexpected voice download failure",
            user_id=update.effective_user.id,
            error=type(exc).__name__,
        )
        log_event(
            "voice.download",
            user_id=update.effective_user.id,
            latency_ms=int((time.monotonic() - download_started) * 1000),
            audio_bytes=voice.file_size,
            ok=False,
            error=type(exc).__name__,
        )
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["voice_download_error"])
        return

    try:
        result = await asyncio.wait_for(
            whisper_client.transcribe(bytes(data), format="ogg"),
            timeout=settings.transcription_timeout_seconds,
        )
    except asyncio.TimeoutError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except ExternalTimeoutError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except (ExternalResponseError, TranscriptionError):
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["voice_transcription_error"])
        return
    if not result.text:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["voice_transcription_error"])
        return
    await safe_delete_message(progress_message)
    try:
        await reply_text_chunked(
            update.message,
            msgs["voice_transcribed"].format(text=result.text),
        )
    except Exception as exc:
        logger.warning(
            "Failed to display voice transcription; continuing routing",
            user_id=update.effective_user.id,
            error=type(exc).__name__,
        )

    # Route with preference: habits voice handling first.
    session_repo = get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session and session.state == ConversationState.HABITS_AWAITING_CONTENT:
        await handle_habits_text(update, context, result.text, input_type=InputType.VOICE)
        return
    await route_text(update, context, text_override=result.text)
