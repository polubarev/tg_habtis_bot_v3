from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.config.constants import DEFAULT_HABIT_SCHEMA, MESSAGES_EN, MESSAGES_RU
from src.models.habit import HabitFieldConfig
from src.models.session import ConversationState


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
            InlineKeyboardButton("➕ Добавить", callback_data="habit_cfg:add"),
            InlineKeyboardButton("➖ Удалить", callback_data="habit_cfg:remove"),
        ],
        [
            InlineKeyboardButton("↩️ Сбросить", callback_data="habit_cfg:reset"),
            InlineKeyboardButton("✖ Отмена", callback_data="habit_cfg:cancel"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _format_fields(profile) -> str:
    fields = profile.habit_schema.fields if profile and profile.habit_schema else {}
    if not fields:
        return "нет"
    return ", ".join(fields.keys())


async def habits_config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current habit fields and present options."""

    if not update.effective_user or not update.message:
        return
    session_repo, user_repo = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if profile is None:
        return
    if session_repo:
        session = await session_repo.get(update.effective_user.id)
        if session:
            session.state = ConversationState.CONFIG_EDITING_HABITS
            session.temp_data = {"habit_action": None}
            await session_repo.save(session)
    msg = _messages(update)["habit_config_intro"].format(fields=_format_fields(profile))
    await update.message.reply_text(msg, reply_markup=_keyboard())


async def handle_habits_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle habit config inline buttons."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("habit_cfg:"):
        return
    action = data.split(":", 1)[1]

    session_repo, user_repo = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if session:
        session.state = ConversationState.CONFIG_EDITING_HABITS
        session.temp_data = {"habit_action": action}
        await session_repo.save(session)

    if action == "add":
        await query.edit_message_text(_messages(update)["habit_add_prompt"])
    elif action == "remove":
        await query.edit_message_text(_messages(update)["habit_remove_prompt"])
    elif action == "reset":
        if profile and user_repo:
            profile.habit_schema = DEFAULT_HABIT_SCHEMA
            await user_repo.update(profile)
        await query.edit_message_text(_messages(update)["habit_reset"])
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


async def handle_habits_config_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input for habit config add/remove."""

    if not update.effective_user or not update.message:
        return False
    session_repo, user_repo = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.CONFIG_EDITING_HABITS:
        return False

    action = (session.temp_data or {}).get("habit_action")
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if profile is None:
        return False

    text = update.message.text or ""
    if action == "add":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 2:
            await update.message.reply_text(_messages(update)["habit_add_prompt"])
            return True
        name, description = parts[0], parts[1]
        type_hint = parts[2].lower() if len(parts) > 2 else "string"
        type_value = "string"
        if type_hint in {"int", "integer"}:
            type_value = "integer"
        elif type_hint in {"bool", "boolean"}:
            type_value = "boolean"
        profile.habit_schema.fields[name] = HabitFieldConfig(
            type=type_value,
            description=description,
            required=True,
        )
        await user_repo.update(profile)
        await update.message.reply_text(_messages(update)["habit_added"].format(name=name))
    elif action == "remove":
        name = text.strip()
        if name in profile.habit_schema.fields:
            profile.habit_schema.fields.pop(name)
            await user_repo.update(profile)
            await update.message.reply_text(_messages(update)["habit_removed"].format(name=name))
        else:
            await update.message.reply_text(_messages(update)["habit_remove_prompt"])
            return True
    else:
        await update.message.reply_text(_messages(update)["cancelled_config"])

    session.state = ConversationState.IDLE
    session.temp_data = {}
    if session_repo:
        await session_repo.save(session)
    return True
