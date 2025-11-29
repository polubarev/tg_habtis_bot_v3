from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.config.constants import DEFAULT_REFLECTION_QUESTIONS, MESSAGES_EN, MESSAGES_RU
from src.models.session import ConversationState
from src.models.user import CustomQuestion


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        context.application.bot_data.get("session_repo"),
        context.application.bot_data.get("user_repo"),
    )


def _keyboard():
    buttons = [
        [
            InlineKeyboardButton("➕ Add", callback_data="q_cfg:add"),
            InlineKeyboardButton("➖ Remove", callback_data="q_cfg:remove"),
        ],
        [
            InlineKeyboardButton("↩️ Reset", callback_data="q_cfg:reset"),
            InlineKeyboardButton("✖ Cancel", callback_data="q_cfg:cancel"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _format_questions(profile) -> str:
    questions = profile.custom_questions if profile else []
    if not questions:
        return "none"
    return ", ".join(f"{q.id}" for q in questions)


async def questions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current questions and options."""

    if not update.effective_user or not update.message:
        return
    session_repo, user_repo = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if profile is None:
        return
    if session_repo:
        session = await session_repo.get(update.effective_user.id)
        if session:
            session.state = ConversationState.CONFIG_ADDING_QUESTION
            session.temp_data = {"q_action": None}
            await session_repo.save(session)
    msg = _messages(update)["question_intro"].format(questions=_format_questions(profile))
    await update.message.reply_text(msg, reply_markup=_keyboard())


async def handle_questions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle question config inline buttons."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("q_cfg:"):
        return
    action = data.split(":", 1)[1]

    session_repo, user_repo = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if session:
        session.state = ConversationState.CONFIG_ADDING_QUESTION
        session.temp_data = {"q_action": action}
        await session_repo.save(session)

    if action == "add":
        await query.edit_message_text(_messages(update)["question_add_prompt"])
    elif action == "remove":
        await query.edit_message_text(_messages(update)["question_remove_prompt"])
    elif action == "reset":
        if profile and user_repo:
            profile.custom_questions = [CustomQuestion(**q, language=profile.language) for q in DEFAULT_REFLECTION_QUESTIONS]
            await user_repo.update(profile)
        await query.edit_message_text(_messages(update)["question_reset"])
        if session_repo and session:
            session.state = ConversationState.IDLE
            session.temp_data = {}
            await session_repo.save(session)
    elif action == "cancel":
        await query.edit_message_text(_messages(update)["cancelled_config"])
        if session_repo and session:
            session.state = ConversationState.IDLE
            session.temp_data = {}
            await session_repo.save(session)


async def handle_questions_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input for questions add/remove."""

    if not update.effective_user or not update.message:
        return False
    session_repo, user_repo = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.CONFIG_ADDING_QUESTION:
        return False

    action = (session.temp_data or {}).get("q_action")
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if profile is None:
        return False

    text = update.message.text or ""
    if action == "add":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 2:
            await update.message.reply_text(_messages(update)["question_add_prompt"])
            return True
        q_id, q_text = parts[0], parts[1]
        profile.custom_questions.append(CustomQuestion(id=q_id, text=q_text, language=profile.language))
        await user_repo.update(profile)
        await update.message.reply_text(_messages(update)["question_added"].format(id=q_id))
    elif action == "remove":
        q_id = text.strip()
        before = len(profile.custom_questions)
        profile.custom_questions = [q for q in profile.custom_questions if q.id != q_id]
        if len(profile.custom_questions) == before:
            await update.message.reply_text(_messages(update)["question_remove_prompt"])
            return True
        await user_repo.update(profile)
        await update.message.reply_text(_messages(update)["question_removed"].format(id=q_id))
    else:
        await update.message.reply_text(_messages(update)["cancelled_config"])

    session.state = ConversationState.IDLE
    session.temp_data = {}
    if session_repo:
        await session_repo.save(session)
    return True
