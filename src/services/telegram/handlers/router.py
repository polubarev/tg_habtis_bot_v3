import asyncio

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config.settings import get_settings
from src.services.telegram.handlers.config import handle_config_text, config_command, handle_timezone_text, reset_command
from src.services.telegram.handlers.habits_config import handle_habits_config_text, habits_config_command
from src.services.telegram.handlers.questions import handle_questions_text, questions_command
from src.services.telegram.handlers.dream import handle_dream_text, dream_command
from src.services.telegram.handlers.habits import handle_habits_text, habits_command, handle_habits_date_text
from src.services.telegram.handlers.reflect import handle_reflect_text, reflect_command
from src.services.telegram.handlers.thought import handle_thought_text, thought_command
from src.services.telegram.handlers.help import help_command
from src.services.telegram.keyboards import build_main_menu_keyboard, build_config_keyboard
from src.services.transcription.whisper import WhisperClient
from src.models.session import ConversationState, SessionData
from src.models.enums import InputType
from src.config.constants import MESSAGES_EN, MESSAGES_RU, BUTTONS_RU, BUTTONS_EN
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, TranscriptionError
from src.services.telegram.handlers.language import language_command
from src.services.telegram.utils import resolve_language, resolve_user_profile


_OP_TIMEOUT = get_settings().operation_timeout_seconds


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


async def route_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_override: str | None = None) -> None:
    """Route plain text messages based on conversation state."""

    text = text_override or (update.message.text if update.message else None)
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
        session_repo = context.application.bot_data.get("session_repo")
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
        session_repo = context.application.bot_data.get("session_repo")
        if session_repo:
            session = await session_repo.get(update.effective_user.id) or SessionData(user_id=update.effective_user.id)
            session.state = ConversationState.CONFIG_TIMEZONE
            await session_repo.save(session)
        return
    if matched("language"):
        await language_command(update, context)
        return

    handled = False
    # Order matters: config first, then active flows.
    for handler in (
        handle_timezone_text,
        handle_config_text,
        handle_habits_config_text,
        handle_habits_config_text,
        handle_questions_text,
        lambda u, c: handle_habits_date_text(u, c, text),
        lambda u, c: handle_habits_text(u, c, text),
        lambda u, c: handle_dream_text(u, c, text),
        lambda u, c: handle_thought_text(u, c, text),
        lambda u, c: handle_reflect_text(u, c, text),
    ):
        if await handler(update, context):
            handled = True
            break

    if not handled and update.message:
        await update.message.reply_text(
            msgs["help"],
            reply_markup=build_main_menu_keyboard(lang),
            parse_mode=ParseMode.MARKDOWN,
        )


async def route_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route voice messages: transcribe then reuse text handlers."""

    if not update.message or not update.message.voice:
        return
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = _messages_for_lang(lang)
    whisper_client: WhisperClient | None = context.application.bot_data.get("whisper_client")
    if whisper_client is None:
        await update.message.reply_text(msgs["voice_disabled"])
        return

    # Download audio bytes from Telegram.
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)
    data = await tg_file.download_as_bytearray()
    try:
        await update.message.reply_text(msgs["processing"])
        result = await asyncio.wait_for(
            whisper_client.transcribe(bytes(data), format="ogg"),
            timeout=_OP_TIMEOUT,
        )
    except asyncio.TimeoutError:
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except ExternalTimeoutError:
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except (ExternalResponseError, TranscriptionError):
        await update.message.reply_text(msgs["voice_transcription_error"])
        return
    if not result.text:
        await update.message.reply_text(msgs["voice_transcription_error"])
        return
    # Echo transcription to user
    await update.message.reply_text(msgs["voice_transcribed"].format(text=result.text))

    # Route with preference: habits voice handling first.
    session_repo = context.application.bot_data.get("session_repo")
    session = await session_repo.get(update.effective_user.id) if session_repo and update.effective_user else None
    if session and session.state == ConversationState.HABITS_AWAITING_CONTENT:
        await handle_habits_text(update, context, result.text, input_type=InputType.VOICE)  # type: ignore[arg-type]
        return
    await route_text(update, context, text_override=result.text)
