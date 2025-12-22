from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.models.habit import HabitSchema
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from src.services.telegram.keyboards import build_language_keyboard, build_main_menu_keyboard
from src.services.telegram.utils import resolve_language


def _get_user_repo(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("user_repo")


def _get_session_repo(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("session_repo")


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome users and hint available commands."""

    if not update.message:
        return

    user_repo = _get_user_repo(context)
    session_repo = _get_session_repo(context)
    sheet_missing = True
    profile = None
    if user_repo and update.effective_user:
        profile = await user_repo.get_by_telegram_id(update.effective_user.id)
        if profile is None:
            profile = UserProfile(
                telegram_user_id=update.effective_user.id,
                telegram_username=update.effective_user.username,
                habit_schema=HabitSchema(fields={}),  # start empty; user config adds fields
                custom_questions=[],
                onboarding_completed=False,
                language="en",
            )
            await user_repo.create(profile)
        elif profile.language not in {"en", "ru"}:
            profile.language = "en"
            await user_repo.update(profile)
        sheet_missing = not bool(profile.sheet_id)
    lang = resolve_language(profile)

    if profile and not profile.onboarding_completed:
        if session_repo and update.effective_user:
            session = await session_repo.get(update.effective_user.id) or SessionData(user_id=update.effective_user.id)
            session.state = ConversationState.ONBOARDING_LANGUAGE
            await session_repo.save(session)
        await update.message.reply_text(
            MESSAGES_EN["language_prompt"],
            reply_markup=build_language_keyboard(),
        )
        return

    msgs = _messages_for_lang(lang)
    keyboard = build_main_menu_keyboard(lang)
    await update.message.reply_text(msgs["welcome"], reply_markup=keyboard)
    if sheet_missing:
        await update.message.reply_text(msgs["sheet_reminder"])
