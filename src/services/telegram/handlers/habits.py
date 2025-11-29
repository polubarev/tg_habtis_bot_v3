import json
from datetime import date
from typing import Any, Dict

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.models.session import ConversationState, SessionData
from src.services.telegram.keyboards import build_confirmation_keyboard, build_date_keyboard
from src.utils.date_parser import parse_relative_date


def _get_lang(update: Update) -> str:
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return "ru" if code.startswith("ru") else "en"


def _messages(update: Update) -> Dict[str, str]:
    return MESSAGES_RU if _get_lang(update) == "ru" else MESSAGES_EN


def _get_session_repo(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("session_repo")


async def habits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for the /habits flow."""

    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    session_repo = _get_session_repo(context)
    session = await session_repo.get(user_id) if session_repo else None
    if session is None:
        session = SessionData(user_id=user_id)
    session.state = ConversationState.HABITS_AWAITING_DATE
    session.selected_date = None
    if session_repo:
        await session_repo.save(session)

    msgs = _messages(update)
    await update.message.reply_text(msgs["select_date"], reply_markup=build_date_keyboard())


async def handle_habits_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle date selection callbacks."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if data == "habits_cancel":
        await query.answer()
        await query.edit_message_text(_messages(update)["cancelled"])
        return
    if not data.startswith("habits_date:"):
        return

    session_repo = _get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None:
        session = SessionData(user_id=update.effective_user.id)

    label = data.split(":", 1)[1]
    selected = parse_relative_date(label)
    session.selected_date = selected
    session.state = ConversationState.HABITS_AWAITING_CONTENT
    if session_repo:
        await session_repo.save(session)

    msgs = _messages(update)
    await query.answer()
    await query.edit_message_text(msgs["describe_day"].format(date=selected.isoformat()))


async def handle_habits_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input during habits flow."""

    if not update.message or not update.effective_user:
        return
    session_repo = _get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.HABITS_AWAITING_CONTENT:
        return

    raw_text = update.message.text or ""
    selected_date = session.selected_date or date.today()

    entry_data: Dict[str, Any] = {
        "date": selected_date.isoformat(),
        "raw_diary": raw_text,
        "diary": raw_text,
    }
    session.pending_entry = entry_data
    session.state = ConversationState.HABITS_AWAITING_CONFIRMATION
    if session_repo:
        await session_repo.save(session)

    msgs = _messages(update)
    preview = json.dumps(entry_data, ensure_ascii=False, indent=2)
    await update.message.reply_text(
        msgs["confirm_entry"].format(json_data=preview),
        reply_markup=build_confirmation_keyboard(prefix="habits"),
    )


async def handle_habits_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation callback for habits entry."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("habits_confirm:"):
        return

    session_repo = _get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or not session.pending_entry:
        await query.answer()
        await query.edit_message_text(_messages(update)["error_occurred"])
        return

    decision = data.split(":", 1)[1]
    if decision == "yes":
        await query.edit_message_text(_messages(update)["saved_success"])
    else:
        await query.edit_message_text(_messages(update)["cancelled"])

    session.reset()
    if session_repo:
        await session_repo.save(session)
    await query.answer()
