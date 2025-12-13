from datetime import date, datetime
import json
from typing import Any, Dict

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import DEFAULT_HABIT_SCHEMA, HABITS_SHEET_COLUMNS, MESSAGES_EN, MESSAGES_RU
from src.models.session import ConversationState, SessionData
from src.services.telegram.keyboards import build_confirmation_keyboard, build_date_keyboard
from src.utils.date_parser import parse_relative_date
from src.models.entry import HabitEntry
from src.models.enums import InputType
from src.services.llm.extractors.habit_extractor import HabitExtractor
from src.services.telegram.utils import resolve_user_timezone


BASE_HABIT_FIELDS = set(HABITS_SHEET_COLUMNS)


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


def _safe_answer(query) -> None:
    """Best-effort answer to avoid errors on stale callback queries."""

    try:
        return query.answer()
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
    # start fresh to avoid dragging previous raw updates into a new flow
    session.temp_data = {}
    session.pending_entry = None
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
        _safe_answer(query)
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
        _safe_answer(query)
        await query.edit_message_text("Введи дату в формате YYYY-MM-DD (или dd.mm.yyyy).")
        return

    selected = parse_relative_date(label)
    session.selected_date = selected
    session.state = ConversationState.HABITS_AWAITING_CONTENT
    if session_repo:
        await session_repo.save(session)

    msgs = _messages(update)
    try:
        _safe_answer(query)
    except Exception:
        pass
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
    previous_raw = (session.temp_data or {}).get("previous_raw_record")
    combined_text = raw_text
    if previous_raw:
        combined_text = f"{previous_raw}\n\n[Update]\n{raw_text}"

    llm_client = _get_llm_client(context)
    extraction: Dict[str, Any] = {}
    profile = await _get_user_repo(context).get_by_telegram_id(update.effective_user.id) if _get_user_repo(context) else None
    user_tz = resolve_user_timezone(profile)
    habit_schema = profile.habit_schema if profile else None
    schema_fields: list[str] = (
        list(habit_schema.fields.keys()) if habit_schema and habit_schema.fields else []
    )
    # If schema matches the baked-in default, treat it as empty until user customizes.
    # keep schema_fields as-is; diary is now part of default schema
    field_order = [f for f in schema_fields if f not in BASE_HABIT_FIELDS]
    if llm_client:
        try:
            extractor = HabitExtractor(llm_client)
            extraction = await extractor.extract(combined_text, language=_get_lang(update), schema=habit_schema or None)
        except Exception:
            extraction = {}
    else:
        if update.message:
            await update.message.reply_text(_messages(update)["llm_disabled"])

    diary_text = extraction.get("diary") or combined_text

    entry_data: Dict[str, Any] = {
        "timestamp": datetime.now(user_tz).isoformat(),
        "date": selected_date.isoformat(),
        "raw_record": combined_text,
        "diary": diary_text,
        "input_type": input_type.value,
        "field_order": field_order,
    }
    for k, v in extraction.items():
        if k not in {"timestamp", "date", "raw_record", "diary", "input_type"}:
            entry_data[k] = v
    session.pending_entry = entry_data
    session.state = ConversationState.HABITS_AWAITING_CONFIRMATION
    if session_repo:
        await session_repo.save(session)

    msgs = _messages(update)
    preview_obj = {k: v for k, v in entry_data.items() if k not in {"input_type", "field_order"}}
    preview = json.dumps(preview_obj, ensure_ascii=False, indent=2, default=str)
    if update.message:
        await update.message.reply_text(
            msgs["confirm_entry"]
            + "\n\n"
            + "```json\n"
            + preview
            + "\n```",
            reply_markup=build_confirmation_keyboard(prefix="habits"),
            parse_mode="Markdown",
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
    base_fields = BASE_HABIT_FIELDS
    # If user has no schema, keep only base columns.
    default_dynamic: list[str] = []
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or not session.pending_entry:
        _safe_answer(query)
        await query.edit_message_text(_messages(update)["error_occurred"])
        return

    decision = data.split(":", 1)[1]
    if decision == "yes":
        profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
        sheet_id = profile.sheet_id if profile else None
        if sheet_id and sheets_client:
            field_order = (
                [f for f in (profile.habit_schema.fields.keys()) if f not in base_fields]
                if profile and profile.habit_schema and profile.habit_schema.fields
                else default_dynamic
            )
            session_fields = [
                f
                for f in (session.pending_entry.get("field_order") or [])
                if f not in base_fields
            ]
            field_order = session_fields or field_order
            extra_pending_fields = [
                k
                for k in session.pending_entry.keys()
                if k not in base_fields
                and k not in {"input_type", "field_order"}
                and k not in field_order
            ]
            field_order = field_order + extra_pending_fields
            created_at = datetime.fromisoformat(session.pending_entry.get("timestamp")) if session.pending_entry.get("timestamp") else datetime.utcnow()
            entry = HabitEntry(
                date=date.fromisoformat(session.pending_entry.get("date")),
                raw_record=session.pending_entry.get("raw_record", ""),
                diary=session.pending_entry.get("diary"),
                extra_fields={
                    k: v
                    for k, v in session.pending_entry.items()
                    if k not in base_fields | {"input_type", "field_order"}
                },
                input_type=InputType(session.pending_entry.get("input_type") or InputType.TEXT),
                created_at=created_at,
            )
            await sheets_client.append_habit_entry(sheet_id, field_order, entry)
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=_messages(update)["saved_success"]
            )
        else:
            await query.edit_message_text(_messages(update)["sheet_not_configured"])
    else:
        # allow user to resend/correct; keep previous raw for context
        if session.pending_entry:
            if session.temp_data is None:
                session.temp_data = {}
            session.temp_data["previous_raw_record"] = session.pending_entry.get("raw_record", "")
        session.pending_entry = {}
        session.state = ConversationState.HABITS_AWAITING_CONTENT
        if session_repo:
            await session_repo.save(session)
        await query.edit_message_text(_messages(update)["habits_update_prompt"])
        _safe_answer(query)
        return

    session.reset()
    if session_repo:
        await session_repo.save(session)
    _safe_answer(query)
