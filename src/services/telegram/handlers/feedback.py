from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.core.analytics import log_event
from src.models.feedback import FeedbackEntry
from src.models.session import ConversationState, SessionData
from src.services.telegram.keyboards import build_main_menu_keyboard
from src.services.telegram.utils import (
    get_feedback_repo,
    get_session_repo,
    resolve_language,
    resolve_user_profile,
)


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt the user to send feedback from the settings menu."""

    if not update.effective_user or not update.message:
        return
    log_event("command.feedback", user_id=update.effective_user.id)
    session_repo = get_session_repo(context)
    if session_repo:
        session = await session_repo.get(update.effective_user.id) or SessionData(
            user_id=update.effective_user.id
        )
        session.state = ConversationState.CONFIG_FEEDBACK
        await session_repo.save(session)
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    await update.message.reply_text(_messages_for_lang(lang)["feedback_prompt"])


async def handle_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Capture feedback text when awaiting a feedback message."""

    if not update.effective_user or not update.message:
        return False
    text = (update.message.text or "").strip()
    session_repo = get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.CONFIG_FEEDBACK:
        return False

    if text.lower() in {"/cancel", "cancel", "отмена"}:
        session.state = ConversationState.IDLE
        if session_repo:
            await session_repo.save(session)
        profile = await resolve_user_profile(update, context)
        lang = resolve_language(profile)
        await update.message.reply_text(
            _messages_for_lang(lang)["cancelled_config"],
            reply_markup=build_main_menu_keyboard(lang),
        )
        return True

    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    user = update.effective_user
    entry = FeedbackEntry(
        telegram_user_id=user.id,
        telegram_username=user.username,
        telegram_first_name=user.first_name,
        language=lang,
        message=text,
    )
    feedback_repo = get_feedback_repo(context)
    saved = await feedback_repo.create(entry) if feedback_repo else False
    if saved:
        await update.message.reply_text(
            _messages_for_lang(lang)["feedback_saved"],
            reply_markup=build_main_menu_keyboard(lang),
        )
    else:
        await update.message.reply_text(
            _messages_for_lang(lang)["feedback_error"],
            reply_markup=build_main_menu_keyboard(lang),
        )
    session.state = ConversationState.IDLE
    if session_repo:
        await session_repo.save(session)
    return True
