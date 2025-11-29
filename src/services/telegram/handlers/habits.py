from datetime import date
from typing import Any, Dict

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import HABITS_SHEET_COLUMNS, MESSAGES_EN, MESSAGES_RU
from src.models.session import ConversationState, SessionData
from src.services.telegram.keyboards import build_confirmation_keyboard, build_date_keyboard
from src.utils.date_parser import parse_relative_date
from src.models.entry import HabitEntry
from src.models.enums import InputType
from datetime import datetime


def _get_lang(update: Update) -> str:
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return "ru" if code.startswith("ru") else "en"


def _messages(update: Update) -> Dict[str, str]:
    return MESSAGES_RU if _get_lang(update) == "ru" else MESSAGES_EN


def _get_session_repo(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("session_repo")


def _get_user_repo(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("user_repo")


def _get_sheets_client(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("sheets_client")


def _get_llm_client(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("llm_client")


def _parse_custom_date(text: str) -> date | None:
    """Try parsing user-provided date."""

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m"):
        try:
            parsed = datetime.strptime(text.strip(), fmt).date()
            # if year missing, assume current year
            if fmt == "%d.%m" and parsed.year == 1900:
                parsed = parsed.replace(year=date.today().year)
            return parsed
        except ValueError:
            continue
    try:
        return parse_relative_date(text)
    except Exception:
        return None


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
    if label == "custom":
        session.state = ConversationState.HABITS_AWAITING_DATE
        if session_repo:
            await session_repo.save(session)
        await query.answer()
        await query.edit_message_text("Введи дату в формате YYYY-MM-DD (или dd.mm.yyyy).")
        return

    selected = parse_relative_date(label)
    session.selected_date = selected
    session.state = ConversationState.HABITS_AWAITING_CONTENT
    if session_repo:
        await session_repo.save(session)

    msgs = _messages(update)
    await query.answer()
    await query.edit_message_text(msgs["describe_day"].format(date=selected.isoformat()))


async def handle_habits_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Handle manual date input when awaiting date selection."""

    if not update.effective_user or not text:
        return False
    session_repo = _get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.HABITS_AWAITING_DATE:
        return False

    parsed = _parse_custom_date(text)
    if not parsed:
        await update.message.reply_text("Не понял дату. Используй YYYY-MM-DD или dd.mm.yyyy")
        return True

    session.selected_date = parsed
    session.state = ConversationState.HABITS_AWAITING_CONTENT
    if session_repo:
        await session_repo.save(session)

    msgs = _messages(update)
    await update.message.reply_text(msgs["describe_day"].format(date=parsed.isoformat()))
    return True


async def handle_habits_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str | None = None,
    input_type: InputType = InputType.TEXT,
) -> bool:
    """Handle text input during habits flow. Returns True if handled."""

    if not update.effective_user:
        return False
    session_repo = _get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.HABITS_AWAITING_CONTENT:
        return False

    raw_text = text or (update.message.text if update.message else "") or ""
    selected_date = session.selected_date or date.today()
    diary_text = raw_text

    llm_client = _get_llm_client(context)
    if llm_client:
        try:
            diary_text = await llm_client.model.apredict(
                "Summarize the day briefly, keep language as input. Text:\n\n" + raw_text
            )
        except Exception:
            diary_text = raw_text
    else:
        if update.message:
            await update.message.reply_text(_messages(update)["llm_disabled"])

    entry_data: Dict[str, Any] = {
        "date": selected_date.isoformat(),
        "raw_diary": raw_text,
        "diary": diary_text,
        "input_type": input_type.value,
    }
    session.pending_entry = entry_data
    session.state = ConversationState.HABITS_AWAITING_CONFIRMATION
    if session_repo:
        await session_repo.save(session)

    msgs = _messages(update)
    preview = msgs["confirm_entry"].format(
        date=entry_data["date"],
        raw=entry_data["raw_diary"].replace("{", "{{").replace("}", "}}"),
        diary=(entry_data["diary"] or "").replace("{", "{{").replace("}", "}}"),
    )
    if update.message:
        await update.message.reply_text(
            preview,
            reply_markup=build_confirmation_keyboard(prefix="habits"),
        )
    return True


async def handle_habits_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation callback for habits entry."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("habits_confirm:"):
        return

    session_repo = _get_session_repo(context)
    user_repo = _get_user_repo(context)
    sheets_client = _get_sheets_client(context)
    field_order = HABITS_SHEET_COLUMNS[1:]
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or not session.pending_entry:
        await query.answer()
        await query.edit_message_text(_messages(update)["error_occurred"])
        return

    decision = data.split(":", 1)[1]
    if decision == "yes":
        profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
        sheet_id = profile.sheet_id if profile else None
        if sheet_id and sheets_client:
            if profile and profile.habit_schema and profile.habit_schema.fields:
                extra = [f for f in profile.habit_schema.fields.keys() if f not in field_order]
                field_order = field_order + extra
            entry = HabitEntry(
                date=date.fromisoformat(session.pending_entry.get("date")),
                raw_diary=session.pending_entry.get("raw_diary", ""),
                diary=session.pending_entry.get("diary"),
                extra_fields={
                    k: v for k, v in session.pending_entry.items() if k not in {"date", "raw_diary", "diary"}
                },
                input_type=InputType(session.pending_entry.get("input_type") or InputType.TEXT),
            )
            await sheets_client.append_habit_entry(sheet_id, HABITS_SHEET_COLUMNS[1:], entry)
            await query.edit_message_text(_messages(update)["saved_success"])
        else:
            await query.edit_message_text(_messages(update)["sheet_not_configured"])
    else:
        await query.edit_message_text(_messages(update)["cancelled"])

    session.reset()
    if session_repo:
        await session_repo.save(session)
    await query.answer()
