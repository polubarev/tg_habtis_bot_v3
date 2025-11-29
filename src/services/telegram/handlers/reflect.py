from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import DEFAULT_REFLECTION_QUESTIONS, MESSAGES_EN, MESSAGES_RU
from src.models.entry import ReflectionEntry
from src.models.user import CustomQuestion
from src.models.session import ConversationState, SessionData


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        context.application.bot_data.get("session_repo"),
        context.application.bot_data.get("user_repo"),
        context.application.bot_data.get("sheets_client"),
    )


async def reflect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Begin reflection flow."""

    if not update.effective_user or not update.message:
        return
    session_repo, user_repo, _ = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    questions = profile.custom_questions if profile else []
    if not questions:
        if profile is None:
            await update.message.reply_text("Нет вопросов для размышлений. Добавь их в /config.")
            return
        profile.custom_questions = [
            CustomQuestion(**q, language=profile.language) for q in DEFAULT_REFLECTION_QUESTIONS
        ]
        await user_repo.update(profile)
        questions = profile.custom_questions
        await update.message.reply_text(_messages(update)["reflect_seeded"])
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None:
        session = SessionData(user_id=update.effective_user.id)
    session.state = ConversationState.REFLECT_ANSWERING_QUESTIONS
    session.current_question_index = 0
    session.reflection_answers = {}
    await session_repo.save(session)
    await update.message.reply_text(_messages(update)["reflect_intro"])
    await _ask_current_question(update, session, questions)


async def _ask_current_question(update: Update, session, questions) -> None:
    idx = session.current_question_index or 0
    if idx < len(questions):
        await update.message.reply_text(questions[idx].text)


async def handle_reflect_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Handle reflection answers. Returns True if handled."""

    if not update.effective_user or not update.message:
        return False
    session_repo, user_repo, sheets_client = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.REFLECT_ANSWERING_QUESTIONS:
        return False

    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    questions = profile.custom_questions if profile else []
    idx = session.current_question_index or 0
    if idx < len(questions):
        q = questions[idx]
        session.reflection_answers[q.id] = text
        session.current_question_index = idx + 1
        await session_repo.save(session)

    if session.current_question_index is not None and session.current_question_index >= len(questions):
        # finalize
        sheet_id = profile.sheet_id if profile else None
        if not sheet_id:
            await update.message.reply_text(_messages(update)["sheet_not_configured"])
        else:
            entry = ReflectionEntry(date=date.today(), answers=session.reflection_answers.copy())
            if sheets_client:
                await sheets_client.append_reflection_entry(sheet_id, entry)
            await update.message.reply_text(_messages(update)["reflect_done"])
        session.state = ConversationState.IDLE
        session.current_question_index = None
        session.reflection_answers = {}
        await session_repo.save(session)
        return True

    # ask next
    await _ask_current_question(update, session, questions)
    return True
