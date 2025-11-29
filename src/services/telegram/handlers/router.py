from telegram import Update
from telegram.ext import ContextTypes

from src.services.telegram.handlers.config import handle_config_text
from src.services.telegram.handlers.habits_config import handle_habits_config_text
from src.services.telegram.handlers.questions import handle_questions_text
from src.services.telegram.handlers.dream import handle_dream_text
from src.services.telegram.handlers.habits import handle_habits_text
from src.services.telegram.handlers.habits import handle_habits_date_text
from src.services.telegram.handlers.reflect import handle_reflect_text
from src.services.telegram.handlers.thought import handle_thought_text
from src.services.transcription.whisper import WhisperClient
from src.models.session import ConversationState
from src.models.enums import InputType
from src.config.constants import MESSAGES_EN, MESSAGES_RU


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


async def route_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route plain text messages based on conversation state."""

    text = update.message.text if update.message else None
    if not text:
        return

    handled = False
    # Order matters: config first, then active flows.
    for handler in (
        handle_config_text,
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
        await update.message.reply_text(_messages(update)["help"])


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

    # Reuse the text routing to respect active flow.
    update.message.text = result.text

    # Route with preference: habits voice handling first.
    session_repo = context.application.bot_data.get("session_repo")
    session = await session_repo.get(update.effective_user.id) if session_repo and update.effective_user else None
    if session and session.state == ConversationState.HABITS_AWAITING_CONTENT:
        await handle_habits_text(update, context, result.text, input_type=InputType.VOICE)  # type: ignore[arg-type]
        return

    await route_text(update, context)
