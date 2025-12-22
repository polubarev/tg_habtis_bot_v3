from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import (
    DEFAULT_REFLECTION_QUESTIONS_EN,
    DEFAULT_REFLECTION_QUESTIONS_RU,
    MESSAGES_EN,
    MESSAGES_RU,
)
from src.models.habit import HabitSchema
from src.models.session import ConversationState, SessionData
from src.models.user import CustomQuestion, UserProfile
from src.services.telegram.keyboards import build_config_keyboard, build_language_keyboard, build_main_menu_keyboard
from src.services.telegram.utils import resolve_language


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        context.application.bot_data.get("session_repo"),
        context.application.bot_data.get("user_repo"),
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to choose interface language."""

    if not update.message or not update.effective_user:
        return
    session_repo, user_repo = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    lang = resolve_language(profile)

    if session_repo:
        session = await session_repo.get(update.effective_user.id) or SessionData(user_id=update.effective_user.id)
        session.state = ConversationState.CONFIG_LANGUAGE
        await session_repo.save(session)

    msgs = _messages_for_lang(lang)
    await update.message.reply_text(msgs["language_prompt"], reply_markup=build_language_keyboard())


async def handle_language_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline language selection."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("lang_select:"):
        return

    selected = data.split(":", 1)[1].strip().lower()
    if selected not in {"en", "ru"}:
        await query.answer()
        return

    session_repo, user_repo = _get_repos(context)
    if user_repo is None:
        await query.answer()
        return
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    was_onboarding = bool(session and session.state == ConversationState.ONBOARDING_LANGUAGE) or bool(
        profile and not profile.onboarding_completed
    )

    if profile is None:
        profile = UserProfile(
            telegram_user_id=update.effective_user.id,
            telegram_username=update.effective_user.username,
            habit_schema=HabitSchema(fields={}),
            custom_questions=[],
            onboarding_completed=False,
            language=selected,
        )
        await user_repo.create(profile)

    profile.language = selected
    if not profile.custom_questions:
        defaults = DEFAULT_REFLECTION_QUESTIONS_RU if selected == "ru" else DEFAULT_REFLECTION_QUESTIONS_EN
        profile.custom_questions = [CustomQuestion(**q, language=selected) for q in defaults]
    profile.onboarding_completed = True
    if user_repo:
        await user_repo.update(profile)

    msgs = _messages_for_lang(selected)
    try:
        await query.edit_message_text(msgs["language_saved"])
    except Exception:
        pass

    if was_onboarding:
        if session and session_repo:
            session.state = ConversationState.IDLE
            await session_repo.save(session)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msgs["welcome"],
            reply_markup=build_main_menu_keyboard(selected),
        )
        if not profile.sheet_id:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=msgs["sheet_reminder"],
            )
    else:
        if session and session_repo:
            session.state = ConversationState.IDLE
            await session_repo.save(session)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msgs["config_menu"],
            reply_markup=build_config_keyboard(selected),
        )

    await query.answer()
