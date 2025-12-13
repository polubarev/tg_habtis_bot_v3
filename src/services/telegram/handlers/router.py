from telegram import Update
from telegram.ext import ContextTypes

from src.services.telegram.handlers.config import handle_config_text, config_command, handle_timezone_text
from src.services.telegram.handlers.habits_config import handle_habits_config_text, habits_config_command
from src.services.telegram.handlers.questions import handle_questions_text, questions_command
from src.services.telegram.handlers.dream import handle_dream_text, dream_command
from src.services.telegram.handlers.habits import handle_habits_text, habits_command, handle_habits_date_text
from src.services.telegram.handlers.reflect import handle_reflect_text, reflect_command
from src.services.telegram.handlers.thought import handle_thought_text, thought_command
from src.services.telegram.handlers.help import help_command
from src.services.telegram.keyboards import build_main_menu_keyboard, build_config_keyboard
from src.services.transcription.whisper import WhisperClient
from src.models.session import ConversationState
from src.models.enums import InputType
from src.config.constants import MESSAGES_EN, MESSAGES_RU, BUTTONS_RU, BUTTONS_EN


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


async def route_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text_override: str | None = None) -> None:
    """Route plain text messages based on conversation state."""

    text = text_override or (update.message.text if update.message else None)
    if not text:
        return

    # Helper to check against all languages
    def matched(key: str) -> bool:
        return text in (BUTTONS_RU.get(key), BUTTONS_EN.get(key))

    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    lang = "ru" if code.startswith("ru") else "en"

    # 1. Global Cancel
    if matched("cancel"):
        # Reset session
        session_repo = context.application.bot_data.get("session_repo")
        if session_repo and update.effective_user:
            session = await session_repo.get(update.effective_user.id)
            if session:
                session.reset()
                await session_repo.save(session)
        
        await update.message.reply_text(
            _messages(update)["cancelled"],
            reply_markup=build_main_menu_keyboard(lang)
        )
        return

    # 2. Navigation
    if matched("back"):
        await update.message.reply_text(
            _messages(update)["help"],
            reply_markup=build_main_menu_keyboard(lang)
        )
        return

    if matched("config"):
        await update.message.reply_text(
            _messages(update)["help"],
            reply_markup=build_config_keyboard(lang)
        )
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
    if matched("reflect_config"):
        await questions_command(update, context)
    if matched("reflect_config"):
        await questions_command(update, context)
        return
    if matched("timezone"):
        # Prompt for new timezone
        await update.message.reply_text(
            _messages(update)["timezone_prompt"].format(tz=context.application.bot_data.get("user_repo") and await context.application.bot_data.get("user_repo").get_by_telegram_id(update.effective_user.id) and (await context.application.bot_data.get("user_repo").get_by_telegram_id(update.effective_user.id)).timezone or "Europe/Moscow"),
            reply_markup=build_main_menu_keyboard(lang)
        )
        # Set state
        session_repo = context.application.bot_data.get("session_repo")
        if session_repo:
            session = await session_repo.get(update.effective_user.id) or SessionData(user_id=update.effective_user.id)
            session.state = ConversationState.CONFIG_TIMEZONE
            await session_repo.save(session)
        return

    handled = False
    # Order matters: config first, then active flows.
    for handler in (
        handle_config_text,
        handle_timezone_text,
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
        code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
        lang = "ru" if code.startswith("ru") else "en"
        await update.message.reply_text(_messages(update)["help"], reply_markup=build_main_menu_keyboard(lang))


async def route_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route voice messages: transcribe then reuse text handlers."""

    if not update.message or not update.message.voice:
        return
    whisper_client: WhisperClient | None = context.application.bot_data.get("whisper_client")
    if whisper_client is None:
        await update.message.reply_text(_messages(update)["voice_disabled"])
        return

    # Download audio bytes from Telegram.
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)
    data = await tg_file.download_as_bytearray()
    result = await whisper_client.transcribe(bytes(data), format="ogg")
    if not result.text:
        return
    # Echo transcription to user
    await update.message.reply_text(_messages(update)["voice_transcribed"].format(text=result.text))

    # Route with preference: habits voice handling first.
    session_repo = context.application.bot_data.get("session_repo")
    session = await session_repo.get(update.effective_user.id) if session_repo and update.effective_user else None
    if session and session.state == ConversationState.HABITS_AWAITING_CONTENT:
        await handle_habits_text(update, context, result.text, input_type=InputType.VOICE)  # type: ignore[arg-type]
        return
    await route_text(update, context, text_override=result.text)
