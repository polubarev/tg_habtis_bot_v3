from datetime import date, datetime
import html
import asyncio
from typing import Any, Dict

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config.constants import HABITS_SHEET_COLUMNS, MESSAGES_EN, MESSAGES_RU
from src.config.settings import get_settings
from src.models.habit import HabitSchema
from src.models.session import ConversationState, SessionData
from src.services.telegram.keyboards import (
    build_confirmation_keyboard,
    build_date_keyboard,
    build_existing_habits_keyboard,
)
from src.utils.date_parser import parse_relative_date
from src.models.entry import HabitEntry
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, SheetAccessError, SheetWriteError
from src.models.enums import InputType
from src.services.llm.extractors.habit_extractor import HabitExtractor
from src.services.telegram.utils import (
    get_llm_client,
    get_session_repo,
    get_sheets_client,
    get_user_repo,
    increment_usage_stat,
    resolve_language,
    resolve_user_profile,
    resolve_user_timezone,
    safe_delete_message,
)


BASE_HABIT_FIELDS = set(HABITS_SHEET_COLUMNS)
_OP_TIMEOUT = get_settings().operation_timeout_seconds


def _messages_for_lang(lang: str) -> Dict[str, str]:
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


def _bool_label(value: bool, lang: str) -> str:
    if lang == "ru":
        return "да" if value else "нет"
    return "yes" if value else "no"


def _normalize_field_types(field_type: str | list[str] | None) -> set[str]:
    if not field_type:
        return set()
    if isinstance(field_type, list):
        return {str(item).lower() for item in field_type}
    return {str(field_type).lower()}


def _compact_text(text: str) -> str:
    return " ".join(text.split())


def _truncate_text(text: str, max_len: int) -> str:
    compact = _compact_text(text)
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + "..."


def _field_label(field_name: str, lang: str) -> str:
    if lang == "ru":
        return {
            "date": "дата",
            "diary": "дневник",
            "raw_record": "исходный текст",
        }.get(field_name, field_name)
    return {
        "raw_record": "raw record",
    }.get(field_name, field_name)


def _format_habit_value(value: Any, lang: str, field_type: str | list[str] | None) -> str:
    if value is None:
        return ""
    types = _normalize_field_types(field_type)
    if "bool" in types or isinstance(value, bool):
        bool_value = None
        if isinstance(value, bool):
            bool_value = value
        elif isinstance(value, (int, float)) and value in (0, 1):
            bool_value = bool(value)
        elif isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1", "да"}:
                bool_value = True
            elif normalized in {"false", "no", "0", "нет"}:
                bool_value = False
        if bool_value is not None:
            return _bool_label(bool_value, lang)
    if isinstance(value, (list, tuple)):
        return ", ".join(_format_habit_value(item, lang, None) for item in value)
    return str(value)


def _coerce_bool_value(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)) and value in (0, 1):
        return int(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "да"}:
            return 1
        if normalized in {"false", "no", "0", "нет"}:
            return 0
    if isinstance(value, (list, tuple)):
        coerced = []
        for item in value:
            coerced_item = _coerce_bool_value(item)
            if isinstance(coerced_item, list):
                coerced.extend(coerced_item)
            else:
                coerced.append(coerced_item)
        return ", ".join(str(item) for item in coerced)
    return value


def _coerce_entry_for_sheet(entry_data: Dict[str, Any], habit_schema: HabitSchema | None) -> Dict[str, Any]:
    if not habit_schema or not habit_schema.fields:
        return dict(entry_data)
    coerced = dict(entry_data)
    for field_name, config in habit_schema.fields.items():
        if field_name not in coerced:
            continue
        field_type = config.type if hasattr(config, "type") else config.get("type")
        types = _normalize_field_types(field_type)
        if "bool" in types or "boolean" in types:
            coerced[field_name] = _coerce_bool_value(coerced[field_name])
    return coerced


def _format_habit_preview(entry_data: Dict[str, Any], habit_schema: HabitSchema | None, lang: str) -> str:
    exclude = {"input_type", "field_order", "timestamp", "raw_record"}
    field_order = entry_data.get("field_order") or []
    keys: list[str] = []
    include_diary = habit_schema.include_diary if habit_schema else True
    for key in ("date",):
        if key in entry_data and key not in exclude:
            keys.append(key)
    if include_diary and "diary" in entry_data and "diary" not in exclude:
        keys.insert(1, "diary")
    for key in field_order:
        if key == "diary" and not include_diary:
            continue
        if key in entry_data and key not in exclude and key not in keys:
            keys.append(key)
    for key in entry_data:
        if key == "diary" and not include_diary:
            continue
        if key in exclude or key in keys:
            continue
        keys.append(key)

    date_line = None
    diary_block = None
    rest_lines = []
    for key in keys:
        value = entry_data.get(key)
        if key == "raw_record" and isinstance(value, str):
            value = _truncate_text(value, 280)
        field_type = habit_schema.fields[key].type if habit_schema and key in habit_schema.fields else None
        label = html.escape(_field_label(key, lang))
        formatted_value = _format_habit_value(value, lang, field_type)
        formatted_value = formatted_value if formatted_value else "—"
        formatted_value = html.escape(formatted_value)
        if key == "date":
            date_line = f"<b>{label}</b>: {formatted_value}"
        elif key == "diary":
            diary_block = f"<b>{label}</b>:\n{formatted_value}"
        else:
            rest_lines.append(f"<b>{label}</b>: {formatted_value}")
    sections = []
    if date_line:
        sections.append(date_line)
    if diary_block:
        sections.append(diary_block)
    if rest_lines:
        sections.append("\n".join(rest_lines))
    return "\n\n".join(sections)


def _format_habit_field_lines(field_config: Any, lang: str) -> list[str]:
    description = None
    if hasattr(field_config, "description"):
        description = field_config.description
    elif isinstance(field_config, dict):
        description = field_config.get("description")

    lines = []
    if description:
        desc_label = "Описание" if lang == "ru" else "Description"
        compact = _compact_text(str(description))
        lines.append(f"  {desc_label}: {html.escape(compact)}")
    return lines


def _expected_habit_fields(profile, lang: str) -> list[str]:
    if not profile or not profile.habit_schema:
        return []
    schema = profile.habit_schema
    include_diary = schema.include_diary
    fields = schema.fields or {}
    names = []
    for name, config in fields.items():
        if name in BASE_HABIT_FIELDS:
            continue
        if name == "diary" and not include_diary:
            continue
        label = html.escape(_field_label(name, lang))
        names.append(f"• <b>{label}</b>")
        names.extend(_format_habit_field_lines(config, lang))
    return names


def _habit_fields_hint(profile, lang: str) -> str:
    fields = _expected_habit_fields(profile, lang)
    if not fields:
        return _messages_for_lang(lang)["habit_fields_hint_empty"]
    formatted = "\n".join(fields)
    return _messages_for_lang(lang)["habit_fields_hint"].format(fields=formatted)


def _get_session_repo(context: ContextTypes.DEFAULT_TYPE):
    return get_session_repo(context)


def _get_user_repo(context: ContextTypes.DEFAULT_TYPE):
    return get_user_repo(context)


def _get_sheets_client(context: ContextTypes.DEFAULT_TYPE):
    return get_sheets_client(context)


def _get_llm_client(context: ContextTypes.DEFAULT_TYPE):
    return get_llm_client(context)


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


async def _safe_edit_message(query, text: str) -> None:
    """Best-effort edit for progress or error updates."""

    try:
        await query.edit_message_text(text)
    except Exception:
        return None


async def _maybe_prompt_existing_entry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: SessionData,
    selected: date,
    lang: str,
) -> bool:
    sheet_client = _get_sheets_client(context)
    session_repo = _get_session_repo(context)
    profile = await resolve_user_profile(update, context)
    habit_schema = profile.habit_schema if profile else None
    sheet_id = profile.sheet_id if profile else None
    if not sheet_id or not sheet_client:
        return False
    try:
        existing = await asyncio.wait_for(
            sheet_client.find_latest_habit_entry(sheet_id, selected),
            timeout=_OP_TIMEOUT,
        )
    except (SheetAccessError, ExternalTimeoutError, SheetWriteError, asyncio.TimeoutError):
        return False
    if not existing:
        return False

    if session.temp_data is None:
        session.temp_data = {}
    session.temp_data["existing_row_index"] = existing.row_index
    session.temp_data["existing_raw_record"] = existing.raw_record
    session.temp_data["existing_entry_action"] = None
    session.selected_date = selected
    session.state = ConversationState.HABITS_AWAITING_EXISTING_CHOICE
    if session_repo:
        await session_repo.save(session)

    prompt = _messages_for_lang(lang)["habits_existing_prompt"].format(date=selected.isoformat())
    preview = None
    if existing.entry_data:
        preview = _format_habit_preview(existing.entry_data, habit_schema, lang)
        prompt = f"{prompt}\n\n{preview}"
    parse_mode = ParseMode.HTML if preview else None
    keyboard = build_existing_habits_keyboard(lang)
    if update.callback_query:
        _safe_answer(update.callback_query)
        try:
            await update.callback_query.edit_message_text(
                prompt,
                reply_markup=keyboard,
                parse_mode=parse_mode,
            )
        except Exception:
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=prompt,
                    reply_markup=keyboard,
                    parse_mode=parse_mode,
                )
    elif update.message:
        await update.message.reply_text(prompt, reply_markup=keyboard, parse_mode=parse_mode)
    return True


async def habits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for the /habits flow."""

    if not update.effective_user or not update.message:
        return
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
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

    msgs = _messages_for_lang(lang)
    await update.message.reply_text(msgs["select_date"], reply_markup=build_date_keyboard(lang))


async def handle_habits_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle date selection callbacks."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if data == "habits_cancel":
        _safe_answer(query)
        lang = resolve_language(await resolve_user_profile(update, context))
        await query.edit_message_text(_messages_for_lang(lang)["cancelled"])
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
        lang = resolve_language(await resolve_user_profile(update, context))
        await query.edit_message_text(_messages_for_lang(lang)["date_custom_prompt"])
        return

    selected = parse_relative_date(label)
    session.selected_date = selected
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    if await _maybe_prompt_existing_entry(update, context, session, selected, lang):
        return

    session.state = ConversationState.HABITS_AWAITING_CONTENT
    if session_repo:
        await session_repo.save(session)
    msgs = _messages_for_lang(lang)
    try:
        _safe_answer(query)
    except Exception:
        pass
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_habit_fields_hint(profile, lang),
            parse_mode=ParseMode.HTML,
        )
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
        lang = resolve_language(await resolve_user_profile(update, context))
        await update.message.reply_text(_messages_for_lang(lang)["date_parse_error"])
        return True

    session.selected_date = parsed
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    if await _maybe_prompt_existing_entry(update, context, session, parsed, lang):
        return True

    session.state = ConversationState.HABITS_AWAITING_CONTENT
    if session_repo:
        await session_repo.save(session)
    msgs = _messages_for_lang(lang)
    await update.message.reply_text(
        _habit_fields_hint(profile, lang),
        parse_mode=ParseMode.HTML,
    )
    await update.message.reply_text(msgs["describe_day"].format(date=parsed.isoformat()))
    return True


async def handle_habits_existing_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle append/rewrite choice for existing habits entries."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("habits_existing:"):
        return
    action = data.split(":", 1)[1]
    if action not in {"append", "rewrite"}:
        return

    session_repo = _get_session_repo(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.HABITS_AWAITING_EXISTING_CHOICE:
        _safe_answer(query)
        return

    if session.temp_data is None:
        session.temp_data = {}
    session.temp_data["existing_entry_action"] = action
    session.state = ConversationState.HABITS_AWAITING_CONTENT
    if session_repo:
        await session_repo.save(session)

    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    selected_date = session.selected_date or date.today()
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    _safe_answer(query)
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_habit_fields_hint(profile, lang),
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_messages_for_lang(lang)["describe_day"].format(date=selected_date.isoformat()),
        )


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
    previous_raw = (session.temp_data or {}).get("previous_raw_record")
    existing_action = (session.temp_data or {}).get("existing_entry_action")
    existing_raw = (
        (session.temp_data or {}).get("existing_raw_record")
        if existing_action == "append"
        else None
    )
    combined_text = raw_text
    if previous_raw:
        combined_text = f"{previous_raw}\n\n[Update]\n{raw_text}"
    elif existing_raw:
        combined_text = f"{existing_raw}\n\n[Update]\n{raw_text}"

    llm_client = _get_llm_client(context)
    extraction: Dict[str, Any] = {}
    profile = await _get_user_repo(context).get_by_telegram_id(update.effective_user.id) if _get_user_repo(context) else None
    lang = resolve_language(profile)
    user_tz = resolve_user_timezone(profile)
    habit_schema = profile.habit_schema if profile else None
    include_diary = habit_schema.include_diary if habit_schema else True
    schema_fields: list[str] = (
        list(habit_schema.fields.keys()) if habit_schema and habit_schema.fields else []
    )
    # If schema matches the baked-in default, treat it as empty until user customizes.
    # keep schema_fields as-is; diary is now part of default schema
    field_order = [f for f in schema_fields if f not in BASE_HABIT_FIELDS]
    if llm_client:
        progress_message = None
        try:
            if update.message:
                progress_message = await update.message.reply_text(_messages_for_lang(lang)["processing"])
            extractor = HabitExtractor(llm_client)
            extraction = await asyncio.wait_for(
                extractor.extract(combined_text, language=lang, schema=habit_schema or None),
                timeout=_OP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            if update.message:
                await update.message.reply_text(_messages_for_lang(lang)["external_timeout_error"])
            extraction = {}
        except ExternalTimeoutError:
            if update.message:
                await update.message.reply_text(_messages_for_lang(lang)["external_timeout_error"])
            extraction = {}
        except ExternalResponseError:
            if update.message:
                await update.message.reply_text(_messages_for_lang(lang)["external_response_error"])
            extraction = {}
        except Exception:
            extraction = {}
        finally:
            await safe_delete_message(progress_message)
    else:
        if update.message:
            await update.message.reply_text(_messages_for_lang(lang)["llm_disabled"])

    diary_text = None
    if include_diary:
        diary_text = extraction.get("diary") or combined_text

    entry_data: Dict[str, Any] = {
        "timestamp": datetime.now(user_tz).isoformat(),
        "date": selected_date.isoformat(),
        "raw_record": combined_text,
        "input_type": input_type.value,
        "field_order": field_order,
    }
    if include_diary:
        entry_data["diary"] = diary_text
    for k, v in extraction.items():
        if k not in {"timestamp", "date", "raw_record", "diary", "input_type"}:
            entry_data[k] = v
    session.pending_entry = entry_data
    session.state = ConversationState.HABITS_AWAITING_CONFIRMATION
    if session_repo:
        await session_repo.save(session)

    msgs = _messages_for_lang(lang)
    preview = _format_habit_preview(entry_data, habit_schema, lang)
    if update.message:
        await update.message.reply_text(
            msgs["confirm_entry"]
            + "\n\n"
            + preview,
            reply_markup=build_confirmation_keyboard(prefix="habits", language=lang),
            parse_mode=ParseMode.HTML,
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
        lang = resolve_language(await resolve_user_profile(update, context))
        await query.edit_message_text(_messages_for_lang(lang)["error_occurred"])
        return

    decision = data.split(":", 1)[1]
    if decision == "yes":
        profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
        lang = resolve_language(profile)
        habit_schema = profile.habit_schema if profile else None
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
            coerced_entry = _coerce_entry_for_sheet(session.pending_entry, habit_schema)
            entry = HabitEntry(
                date=date.fromisoformat(coerced_entry.get("date")),
                raw_record=coerced_entry.get("raw_record", ""),
                diary=coerced_entry.get("diary"),
                extra_fields={
                    k: v
                    for k, v in coerced_entry.items()
                    if k not in base_fields | {"input_type", "field_order"}
                    and v is not None
                },
                input_type=InputType(coerced_entry.get("input_type") or InputType.TEXT),
                created_at=created_at,
            )
            error_key = None
            try:
                existing_action = (session.temp_data or {}).get("existing_entry_action")
                existing_row_index = (session.temp_data or {}).get("existing_row_index")
                if existing_action in {"append", "rewrite"} and existing_row_index:
                    await asyncio.wait_for(
                        sheets_client.update_habit_entry(
                            sheet_id,
                            int(existing_row_index),
                            field_order,
                            entry,
                        ),
                        timeout=_OP_TIMEOUT,
                    )
                else:
                    await asyncio.wait_for(
                        sheets_client.append_habit_entry(sheet_id, field_order, entry),
                        timeout=_OP_TIMEOUT,
                    )
            except SheetAccessError:
                error_key = "sheet_permission_error"
            except asyncio.TimeoutError:
                error_key = "external_timeout_error"
            except ExternalTimeoutError:
                error_key = "external_timeout_error"
            except SheetWriteError:
                error_key = "sheet_write_error"
            if error_key:
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except Exception:
                    pass
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=_messages_for_lang(lang)[error_key],
                )
                session.reset()
                if session_repo:
                    await session_repo.save(session)
                _safe_answer(query)
                return
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=_messages_for_lang(lang)["saved_success"]
            )
            await increment_usage_stat(profile, user_repo, "habits")
        else:
            await query.edit_message_text(_messages_for_lang(lang)["sheet_not_configured"])
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
        lang = resolve_language(await resolve_user_profile(update, context))
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_messages_for_lang(lang)["habits_update_prompt"],
        )
        _safe_answer(query)
        return

    session.reset()
    if session_repo:
        await session_repo.save(session)
    _safe_answer(query)
