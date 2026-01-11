import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes

from src.config.constants import (
    DEFAULT_HABIT_SCHEMA,
    INLINE_BUTTONS_EN,
    INLINE_BUTTONS_RU,
    MESSAGES_EN,
    MESSAGES_RU,
)
from src.models.habit import HabitFieldConfig
from src.models.session import ConversationState
from src.services.telegram.keyboards import (
    build_habit_edit_attr_keyboard,
    build_habit_fields_keyboard,
    build_habit_type_keyboard,
    build_main_menu_keyboard,
)
from src.services.telegram.utils import get_session_repo, get_user_repo, resolve_language

PROTECTED_HABIT_FIELDS = {"timestamp", "date", "raw_record"}


def _ensure_diary_field(profile) -> bool:
    if not profile or not profile.habit_schema:
        return False
    schema = profile.habit_schema
    include_diary = getattr(schema, "include_diary", True)
    updated = False
    if include_diary and "diary" not in schema.fields:
        schema.fields["diary"] = DEFAULT_HABIT_SCHEMA.fields["diary"].model_copy(deep=True)
        updated = True
    if not include_diary and "diary" in schema.fields:
        schema.fields.pop("diary", None)
        updated = True
    return updated


def _diary_label(lang: str) -> str:
    return "дневник" if lang == "ru" else "diary"


def _display_field_name(name: str, lang: str, fields: dict[str, HabitFieldConfig] | None = None) -> str:
    if name != "diary":
        return name
    label = _diary_label(lang)
    if fields and label in fields and label != "diary":
        return name
    return label


def _field_label_map(profile, lang: str) -> dict[str, str]:
    fields = profile.habit_schema.fields if profile and profile.habit_schema else {}
    if "diary" not in fields:
        return {}
    label = _display_field_name("diary", lang, fields)
    return {"diary": label} if label != "diary" else {}


def _normalize_field_input(name: str, profile, lang: str) -> str:
    raw = name.strip()
    if not raw or not profile or not profile.habit_schema:
        return raw
    fields = profile.habit_schema.fields
    if raw in fields:
        return raw
    diary_label = _display_field_name("diary", lang, fields)
    if diary_label and raw.casefold() == diary_label.casefold() and "diary" in fields:
        return "diary"
    return raw


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        get_session_repo(context),
        get_user_repo(context),
    )


def _keyboard(lang: str):
    btns = INLINE_BUTTONS_RU if lang == "ru" else INLINE_BUTTONS_EN
    buttons = [
        [
            InlineKeyboardButton(btns["habit_add"], callback_data="habit_cfg:add"),
            InlineKeyboardButton(btns["habit_edit"], callback_data="habit_cfg:edit"),
        ],
        [
            InlineKeyboardButton(btns["habit_remove"], callback_data="habit_cfg:remove"),
            InlineKeyboardButton(btns["habit_json"], callback_data="habit_cfg:json"),
        ],
        [
            InlineKeyboardButton(btns["habit_reset"], callback_data="habit_cfg:reset"),
            InlineKeyboardButton(btns["habit_cancel"], callback_data="habit_cfg:cancel"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _format_fields(profile, lang: str) -> str:
    fields = profile.habit_schema.fields if profile and profile.habit_schema else {}
    custom_fields = {name: cfg for name, cfg in fields.items() if name not in PROTECTED_HABIT_FIELDS}
    if not custom_fields:
        return _messages_for_lang(lang)["empty_value"]
    lines = []
    for name, cfg in custom_fields.items():
        display_name = _display_field_name(name, lang, fields)
        lines.append(f"- {display_name} — {_format_field_type(cfg, lang)}")
    return "\n".join(lines)


def _format_field_type(cfg: HabitFieldConfig, lang: str) -> str:
    type_value = cfg.type[0] if isinstance(cfg.type, list) and cfg.type else cfg.type
    if type_value in {"integer", "number"}:
        label = "число" if lang == "ru" else "number"
        if cfg.minimum is not None and cfg.maximum is not None:
            return f"{label} {cfg.minimum}–{cfg.maximum}"
        if cfg.minimum is not None:
            return f"{label} ≥ {cfg.minimum}"
        if cfg.maximum is not None:
            return f"{label} ≤ {cfg.maximum}"
        return label
    if type_value == "boolean":
        return "да/нет" if lang == "ru" else "yes/no"
    if type_value == "string":
        return "текст" if lang == "ru" else "text"
    return str(type_value or "string")


def _format_field_type_label(cfg: HabitFieldConfig, lang: str) -> str:
    type_value = cfg.type[0] if isinstance(cfg.type, list) and cfg.type else cfg.type
    if type_value == "integer":
        return "целое число" if lang == "ru" else "integer"
    if type_value == "number":
        return "число" if lang == "ru" else "number"
    if type_value == "boolean":
        return "да/нет" if lang == "ru" else "yes/no"
    if type_value == "string":
        return "текст" if lang == "ru" else "text"
    return str(type_value or "string")


def _bool_label(value: bool, lang: str) -> str:
    if lang == "ru":
        return "да" if value else "нет"
    return "yes" if value else "no"


def _base_field_type(type_value) -> str:
    if isinstance(type_value, list):
        for item in type_value:
            if item and item != "null":
                return item
        return type_value[0] if type_value else "string"
    return type_value or "string"


def _parse_bool_value(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "да"}:
            return True
        if normalized in {"false", "no", "0", "нет"}:
            return False
    return None


def _format_default_value(value, cfg: HabitFieldConfig, lang: str) -> str:
    if value is None:
        return _messages_for_lang(lang)["empty_value"]
    base_type = _base_field_type(cfg.type)
    if base_type == "boolean":
        parsed = _parse_bool_value(value)
        if parsed is not None:
            return _bool_label(parsed, lang)
    return str(value)


def _format_limit_value(value, lang: str) -> str:
    if value is None:
        return _messages_for_lang(lang)["empty_value"]
    return str(value)


def _default_prompt(lang: str, type_value, mode: str) -> str:
    base_type = _base_field_type(type_value)
    key_map = {
        "integer": f"habit_{mode}_default_prompt_int",
        "number": f"habit_{mode}_default_prompt_float",
        "boolean": f"habit_{mode}_default_prompt_bool",
        "string": f"habit_{mode}_default_prompt_string",
    }
    return _messages_for_lang(lang)[key_map.get(base_type, key_map["string"])]


def _range_error_for_default(value, cfg: HabitFieldConfig) -> tuple[str | None, dict | None]:
    if value is None:
        return None, None
    minimum = cfg.minimum
    maximum = cfg.maximum
    if minimum is not None and maximum is not None and (value < minimum or value > maximum):
        return "habit_default_error_range_between", {"min": minimum, "max": maximum}
    if minimum is not None and value < minimum:
        return "habit_default_error_range_min", {"min": minimum}
    if maximum is not None and value > maximum:
        return "habit_default_error_range_max", {"max": maximum}
    return None, None


def _parse_default_text(raw: str, cfg: HabitFieldConfig) -> tuple[object | None, str | None, dict | None]:
    raw_value = raw.strip()
    if raw_value in {"", "-"}:
        return None, None, None
    base_type = _base_field_type(cfg.type)
    if base_type == "string":
        return raw_value, None, None
    if base_type == "boolean":
        parsed = _parse_bool_value(raw_value)
        if parsed is None:
            return None, "habit_default_error_bool", None
        return parsed, None, None
    if base_type == "integer":
        try:
            parsed = int(raw_value)
        except ValueError:
            return None, "habit_default_error_number", None
        error_key, error_params = _range_error_for_default(parsed, cfg)
        if error_key:
            return None, error_key, error_params
        return parsed, None, None
    if base_type == "number":
        try:
            parsed = float(raw_value)
        except ValueError:
            return None, "habit_default_error_number", None
        error_key, error_params = _range_error_for_default(parsed, cfg)
        if error_key:
            return None, error_key, error_params
        return parsed, None, None
    return raw_value, None, None


def _normalize_default_value(value, cfg: HabitFieldConfig) -> tuple[object | None, str | None, dict | None]:
    if value is None:
        return None, None, None
    base_type = _base_field_type(cfg.type)
    if base_type == "string":
        return str(value), None, None
    if base_type == "boolean":
        parsed = _parse_bool_value(value)
        if parsed is None:
            return None, "habit_default_error_bool", None
        return parsed, None, None
    if base_type == "integer":
        if isinstance(value, bool):
            return None, "habit_default_error_number", None
        if isinstance(value, int):
            parsed = value
        elif isinstance(value, float) and value.is_integer():
            parsed = int(value)
        elif isinstance(value, str):
            try:
                parsed = int(value)
            except ValueError:
                return None, "habit_default_error_number", None
        else:
            return None, "habit_default_error_number", None
        error_key, error_params = _range_error_for_default(parsed, cfg)
        if error_key:
            return None, error_key, error_params
        return parsed, None, None
    if base_type == "number":
        if isinstance(value, bool):
            return None, "habit_default_error_number", None
        if isinstance(value, (int, float)):
            parsed = float(value)
        elif isinstance(value, str):
            try:
                parsed = float(value)
            except ValueError:
                return None, "habit_default_error_number", None
        else:
            return None, "habit_default_error_number", None
        error_key, error_params = _range_error_for_default(parsed, cfg)
        if error_key:
            return None, error_key, error_params
        return parsed, None, None
    return str(value), None, None


def _format_field_details(
    field_name: str,
    cfg: HabitFieldConfig,
    lang: str,
    fields: dict[str, HabitFieldConfig],
) -> str:
    messages = _messages_for_lang(lang)
    display_name = escape_markdown(_display_field_name(field_name, lang, fields))
    description = escape_markdown(cfg.description or messages["empty_value"])
    type_label = escape_markdown(_format_field_type_label(cfg, lang))
    minimum = escape_markdown(_format_limit_value(cfg.minimum, lang))
    maximum = escape_markdown(_format_limit_value(cfg.maximum, lang))
    default_value = escape_markdown(_format_default_value(cfg.default, cfg, lang))
    return messages["habit_edit_details"].format(
        name=display_name,
        description=description,
        type=type_label,
        minimum=minimum,
        maximum=maximum,
        default=default_value,
    )


def _format_custom_fields(profile, lang: str) -> str:
    fields = profile.habit_schema.fields if profile and profile.habit_schema else {}
    custom = [name for name in fields.keys() if name not in PROTECTED_HABIT_FIELDS]
    if not custom:
        return _messages_for_lang(lang)["empty_value"]
    escaped = [escape_markdown(_display_field_name(name, lang, fields)) for name in custom]
    return "\n".join(f"- {name}" for name in escaped)


def _base_numeric_type(type_value) -> str:
    if isinstance(type_value, list):
        return type_value[0]
    return type_value or "integer"


def _custom_field_names(profile) -> list[str]:
    fields = profile.habit_schema.fields if profile and profile.habit_schema else {}
    return [name for name in fields.keys() if name not in PROTECTED_HABIT_FIELDS]


def _min_prompt(lang: str, type_value) -> str:
    base_type = _base_numeric_type(type_value)
    key = "habit_add_min_prompt_float" if base_type == "number" else "habit_add_min_prompt_int"
    return _messages_for_lang(lang)[key]


def _max_prompt(lang: str, type_value) -> str:
    base_type = _base_numeric_type(type_value)
    key = "habit_add_max_prompt_float" if base_type == "number" else "habit_add_max_prompt_int"
    return _messages_for_lang(lang)[key]


def _edit_min_prompt(lang: str, type_value) -> str:
    base_type = _base_numeric_type(type_value)
    key = "habit_edit_min_prompt_float" if base_type == "number" else "habit_edit_min_prompt_int"
    return _messages_for_lang(lang)[key]


def _edit_max_prompt(lang: str, type_value) -> str:
    base_type = _base_numeric_type(type_value)
    key = "habit_edit_max_prompt_float" if base_type == "number" else "habit_edit_max_prompt_int"
    return _messages_for_lang(lang)[key]


async def habits_config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current habit fields and present options."""

    if not update.effective_user or not update.message:
        return
    session_repo, user_repo = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if profile is None:
        return
    lang = resolve_language(profile)
    if session_repo:
        session = await session_repo.get(update.effective_user.id)
        if session:
            session.state = ConversationState.CONFIG_EDITING_HABITS
            session.temp_data = {"habit_action": None}
            await session_repo.save(session)
    if _ensure_diary_field(profile) and user_repo:
        await user_repo.update(profile)
    msg = _messages_for_lang(lang)["habit_config_intro"].format(fields=_format_fields(profile, lang))
    await update.message.reply_text(msg, reply_markup=_keyboard(lang))


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
    lang = resolve_language(profile)
    if _ensure_diary_field(profile) and user_repo:
        await user_repo.update(profile)
    if session:
        session.state = ConversationState.CONFIG_EDITING_HABITS
        session.temp_data = {"habit_action": action}
        await session_repo.save(session)

    try:
        if action == "add":
            if session:
                session.temp_data.update({"habit_add_stage": "name", "habit_new_field": {}})
                await session_repo.save(session)
            await query.edit_message_text(
                _messages_for_lang(lang)["habit_add_name_prompt"],
                parse_mode=ParseMode.MARKDOWN,
            )
        elif action == "edit":
            custom_fields = _custom_field_names(profile)
            labels = _field_label_map(profile, lang)
            if session:
                session.temp_data.update({"habit_edit_stage": "field"})
                await session_repo.save(session)
            await query.edit_message_text(
                _messages_for_lang(lang)["habit_edit_prompt"],
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_habit_fields_keyboard(custom_fields, "edit", lang, labels=labels),
            )
        elif action == "remove":
            custom_fields = _custom_field_names(profile)
            labels = _field_label_map(profile, lang)
            await query.edit_message_text(
                _messages_for_lang(lang)["habit_remove_prompt"].format(
                    fields=_format_custom_fields(profile, lang)
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_habit_fields_keyboard(custom_fields, "remove", lang, labels=labels),
            )
        elif action == "json":
            await query.edit_message_text(
                _messages_for_lang(lang)["habit_json_prompt"],
                parse_mode=ParseMode.MARKDOWN,
            )
        elif action == "reset":
            if profile and user_repo:
                profile.habit_schema = DEFAULT_HABIT_SCHEMA.model_copy(deep=True)
                await user_repo.update(profile)
            await query.edit_message_text(_messages_for_lang(lang)["habit_reset"])
            if session_repo and session:
                session.state = ConversationState.IDLE
                session.temp_data = {}
                await session_repo.save(session)
        elif action == "cancel":
            await query.edit_message_text(_messages_for_lang(lang)["cancelled_config"])
            # The user might be stuck with an inline keyboard above. We can't easily replace it with a reply keyboard via callback query alone
            # without sending a new message. Sending a new message ("Cancelled") with Main Menu is cleaner.
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=_messages_for_lang(lang)["cancelled_config"],
                reply_markup=build_main_menu_keyboard(lang)
            )
            if session_repo and session:
                session.state = ConversationState.IDLE
                session.temp_data = {}
                await session_repo.save(session)
    except Exception:
        # ignore edit collisions (e.g., message not modified/expired)
        pass


async def handle_habit_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle habit field selection for edit/remove via inline buttons."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("habit_field:"):
        return
    try:
        _, action, field_name = data.split(":", 2)
    except ValueError:
        return

    session_repo, user_repo = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if profile is None:
        return
    lang = resolve_language(profile)

    if field_name in PROTECTED_HABIT_FIELDS or field_name not in profile.habit_schema.fields:
        msg_key = "habit_remove_error" if action == "remove" else "habit_edit_not_found"
        await query.edit_message_text(
            _messages_for_lang(lang)[msg_key],
            reply_markup=_keyboard(lang),
        )
        return

    if action == "remove":
        if field_name == "diary":
            profile.habit_schema.include_diary = False
        profile.habit_schema.fields.pop(field_name, None)
        await user_repo.update(profile)
        display_name = _display_field_name(field_name, lang, profile.habit_schema.fields)
        await query.edit_message_text(
            _messages_for_lang(lang)["habit_removed"].format(name=display_name),
            reply_markup=_keyboard(lang),
        )
        if session_repo and session:
            session.state = ConversationState.IDLE
            session.temp_data = {}
            await session_repo.save(session)
        return

    if action == "edit":
        if session_repo and session:
            session.state = ConversationState.CONFIG_EDITING_HABITS
            session.temp_data = {
                "habit_action": "edit",
                "habit_edit_stage": "attr",
                "habit_edit_field": field_name,
            }
            await session_repo.save(session)
        cfg = profile.habit_schema.fields[field_name]
        details = _format_field_details(field_name, cfg, lang, profile.habit_schema.fields)
        display_name = _display_field_name(field_name, lang, profile.habit_schema.fields)
        prompt = _messages_for_lang(lang)["habit_edit_attr_prompt"].format(name=display_name)
        await query.edit_message_text(
            f"{details}\n\n{prompt}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_habit_edit_attr_keyboard(
                lang,
                allowed={"description"} if field_name == "diary" else None,
            ),
        )
        return


async def handle_habit_edit_attr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle selection of which attribute to edit."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("habit_edit_attr:"):
        return
    attr = data.split(":", 1)[1]

    session_repo, user_repo = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    if profile is None or session is None:
        return
    lang = resolve_language(profile)
    temp = session.temp_data or {}
    if temp.get("habit_action") != "edit":
        return
    field_name = temp.get("habit_edit_field")
    if not field_name or field_name not in profile.habit_schema.fields:
        await query.edit_message_text(
            _messages_for_lang(lang)["habit_edit_not_found"],
            reply_markup=_keyboard(lang),
        )
        return
    if field_name == "diary" and attr != "description":
        display_name = _display_field_name(field_name, lang, profile.habit_schema.fields)
        await query.edit_message_text(
            _messages_for_lang(lang)["habit_edit_attr_prompt"].format(name=display_name),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_habit_edit_attr_keyboard(lang, allowed={"description"}),
        )
        return

    cfg = profile.habit_schema.fields[field_name]
    if attr in {"min", "max"} and _base_numeric_type(cfg.type) not in {"integer", "number"}:
        await query.edit_message_text(
            _messages_for_lang(lang)["habit_edit_min_not_numeric"],
            reply_markup=build_habit_edit_attr_keyboard(
                lang, allowed={"description"} if field_name == "diary" else None
            ),
        )
        return

    session.temp_data = {
        "habit_action": "edit",
        "habit_edit_stage": "value",
        "habit_edit_field": field_name,
        "habit_edit_attr": attr,
    }
    if session_repo:
        await session_repo.save(session)

    if attr == "name":
        display_name = _display_field_name(field_name, lang, profile.habit_schema.fields)
        await query.edit_message_text(
            _messages_for_lang(lang)["habit_edit_name_prompt"].format(name=display_name),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if attr == "description":
        display_name = _display_field_name(field_name, lang, profile.habit_schema.fields)
        await query.edit_message_text(
            _messages_for_lang(lang)["habit_edit_description_prompt"].format(name=display_name),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if attr == "type":
        display_name = _display_field_name(field_name, lang, profile.habit_schema.fields)
        await query.edit_message_text(
            _messages_for_lang(lang)["habit_edit_type_prompt"].format(name=display_name),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_habit_type_keyboard(lang),
        )
        return
    if attr == "min":
        await query.edit_message_text(
            _edit_min_prompt(lang, cfg.type),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if attr == "max":
        await query.edit_message_text(
            _edit_max_prompt(lang, cfg.type),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if attr == "default":
        await query.edit_message_text(
            _default_prompt(lang, cfg.type, mode="edit"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return


async def handle_habit_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle habit field type selection."""

    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("habit_type:"):
        return

    type_key = data.split(":", 1)[1]
    type_map = {
        "string": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
    }
    type_value = type_map.get(type_key)
    if not type_value:
        return

    session_repo, user_repo = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    lang = resolve_language(profile)
    if session is None or session.state != ConversationState.CONFIG_EDITING_HABITS:
        return
    temp = session.temp_data or {}
    if temp.get("habit_action") == "add" and temp.get("habit_add_stage") == "type":
        new_field = temp.get("habit_new_field") or {}
        field_name = new_field.get("name")
        if not field_name:
            return
        new_field["type"] = type_value
        if type_value in {"integer", "number"}:
            session.temp_data = {"habit_action": "add", "habit_add_stage": "min", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await query.edit_message_text(_min_prompt(lang, type_value), parse_mode=ParseMode.MARKDOWN)
            return

        session.temp_data = {"habit_action": "add", "habit_add_stage": "default", "habit_new_field": new_field}
        if session_repo:
            await session_repo.save(session)
        await query.edit_message_text(
            _default_prompt(lang, type_value, mode="add"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if temp.get("habit_action") != "edit" or temp.get("habit_edit_attr") != "type":
        return

    field_name = temp.get("habit_edit_field")
    if not field_name:
        return
    if profile and user_repo and field_name in profile.habit_schema.fields:
        cfg = profile.habit_schema.fields[field_name]
        cfg.type = type_value
        if type_value not in {"integer", "number"}:
            cfg.minimum = None
            cfg.maximum = None
        if cfg.default is not None:
            normalized, error_key, _ = _normalize_default_value(cfg.default, cfg)
            cfg.default = None if error_key else normalized
        profile.habit_schema.fields[field_name] = cfg
        await user_repo.update(profile)
    session.state = ConversationState.IDLE
    session.temp_data = {}
    if session_repo:
        await session_repo.save(session)
    try:
        await query.edit_message_text(
            _messages_for_lang(lang)["habit_updated"].format(
                name=_display_field_name(field_name, lang, profile.habit_schema.fields if profile else None)
            ),
            reply_markup=_keyboard(lang),
        )
    except Exception:
        pass


async def handle_habits_config_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text input for habit config add/remove."""

    if not update.effective_user or not update.message:
        return False
    session_repo, user_repo = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.CONFIG_EDITING_HABITS:
        return False
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    lang = resolve_language(profile)

    def _parse_single_field(data):
        if not isinstance(data, dict):
            return None
        name = str(data.get("name", "")).strip()
        if not name or " " in name:
            return None

        def _map_type(t):
            t_str = str(t).strip().lower()
            if t_str in {"int", "integer"}:
                return "integer"
            if t_str in {"float", "double", "number"}:
                return "number"
            if t_str in {"bool", "boolean"}:
                return "boolean"
            if t_str in {"string", "text", ""}:
                return "string"
            if t_str == "null":
                return "null"
            return None

        type_spec = data.get("type", "string")
        nullable = False
        base_type = None
        type_value = None
        if isinstance(type_spec, list):
            mapped = []
            for item in type_spec:
                m = _map_type(item)
                if not m:
                    return None
                mapped.append(m)
            if "null" in mapped:
                nullable = True
                mapped = [t for t in mapped if t != "null"]
            if len(mapped) != 1:
                return None
            base_type = mapped[0]
            type_value = [base_type, "null"] if nullable else base_type
        else:
            mapped = _map_type(type_spec)
            if not mapped or mapped == "null":
                return None
            base_type = mapped
            type_value = mapped

        minimum = data.get("minimum")
        maximum = data.get("maximum")
        if base_type in {"integer", "number"}:
            try:
                minimum = (
                    int(minimum)
                    if minimum is not None and base_type == "integer"
                    else float(minimum)
                    if minimum is not None
                    else None
                )
                maximum = (
                    int(maximum)
                    if maximum is not None and base_type == "integer"
                    else float(maximum)
                    if maximum is not None
                    else None
                )
            except Exception:
                return None
            if minimum is not None and maximum is not None and maximum < minimum:
                return None
        else:
            minimum = None
            maximum = None
        temp_cfg = HabitFieldConfig(
            type=type_value,
            description=str(data.get("description") or name),
            minimum=minimum,
            maximum=maximum,
            required=bool(data.get("required", True)),
        )
        parsed_default, error_key, _ = _normalize_default_value(data.get("default"), temp_cfg)
        if error_key:
            return None
        temp_cfg.default = parsed_default
        cfg = temp_cfg
        return name, cfg

    def _try_parse_json(raw: str):
        try:
            data = json.loads(raw)
        except Exception:
            return None
        if isinstance(data, list):
            parsed = []
            for item in data:
                result = _parse_single_field(item)
                if not result:
                    return None
                parsed.append(result)
            return parsed
        return [_parse_single_field(data)]

    action = (session.temp_data or {}).get("habit_action")
    if profile is None:
        return False

    text = update.message.text or ""
    # allow cancelling the flow via text
    if text.strip().lower() in {"cancel", "/cancel", "отмена"}:
        session.state = ConversationState.IDLE
        session.temp_data = {}
        if session_repo:
            await session_repo.save(session)
        await update.message.reply_text(
            _messages_for_lang(lang)["cancelled_config"],
            reply_markup=build_main_menu_keyboard(lang)
        )
        return True
    if action == "json":
        parsed = _try_parse_json(text)
        if not parsed or not all(parsed):
            await update.message.reply_text(
                _messages_for_lang(lang)["habit_json_error"],
                parse_mode=ParseMode.MARKDOWN,
            )
            return True
        added, skipped = [], []
        for name, cfg in parsed:
            if not name or name in PROTECTED_HABIT_FIELDS or name in profile.habit_schema.fields:
                skipped.append(name or "?")
                continue
            profile.habit_schema.fields[name] = cfg
            if name == "diary":
                profile.habit_schema.include_diary = True
            added.append(name)
        await user_repo.update(profile)
        session.state = ConversationState.IDLE
        session.temp_data = {}
        if session_repo:
            await session_repo.save(session)
        if added:
            display_added = [
                _display_field_name(name, lang, profile.habit_schema.fields) for name in added
            ]
            msg = _messages_for_lang(lang)["habit_json_result_added"].format(added=", ".join(display_added))
        else:
            msg = _messages_for_lang(lang)["habit_json_result_none"]
        if skipped:
            msg += "\n" + _messages_for_lang(lang)["habit_json_result_skipped"].format(skipped=", ".join(skipped))
        await update.message.reply_text(msg, reply_markup=_keyboard(lang))
        return True
    if action == "remove":
        name = _normalize_field_input(text, profile, lang)
        if not name:
            await update.message.reply_text(
                _messages_for_lang(lang)["habit_remove_prompt"].format(
                    fields=_format_custom_fields(profile, lang)
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_habit_fields_keyboard(
                    _custom_field_names(profile),
                    "remove",
                    lang,
                    labels=_field_label_map(profile, lang),
                ),
            )
            return True
        removed = False
        if name in profile.habit_schema.fields and name not in PROTECTED_HABIT_FIELDS:
            if name == "diary":
                profile.habit_schema.include_diary = False
            profile.habit_schema.fields.pop(name, None)
            removed = True
            await user_repo.update(profile)
        display_name = _display_field_name(name, lang, profile.habit_schema.fields)
        await update.message.reply_text(
            _messages_for_lang(lang)["habit_removed"].format(name=display_name)
            if removed
            else _messages_for_lang(lang)["habit_remove_error"]
        )
        # Reset state after a remove attempt to avoid loops.
        session.state = ConversationState.IDLE
        session.temp_data = {}
        if session_repo:
            await session_repo.save(session)
        return True

    if action == "edit":
        temp = session.temp_data or {}
        stage = temp.get("habit_edit_stage") or "field"
        field_name = temp.get("habit_edit_field")
        attr = temp.get("habit_edit_attr")
        custom_fields = _custom_field_names(profile)
        labels = _field_label_map(profile, lang)

        async def _finish_and_reset(updated_name: str):
            session.state = ConversationState.IDLE
            session.temp_data = {}
            if session_repo:
                await session_repo.save(session)
            display_name = _display_field_name(updated_name, lang, profile.habit_schema.fields)
            await update.message.reply_text(
                _messages_for_lang(lang)["habit_updated"].format(name=display_name),
                reply_markup=_keyboard(lang),
            )

        if stage == "field":
            name = _normalize_field_input(text, profile, lang)
            if not name:
                await update.message.reply_text(
                    _messages_for_lang(lang)["habit_edit_prompt"],
                    reply_markup=build_habit_fields_keyboard(custom_fields, "edit", lang, labels=labels),
                )
                return True
            if name in PROTECTED_HABIT_FIELDS or name not in profile.habit_schema.fields:
                await update.message.reply_text(
                    _messages_for_lang(lang)["habit_edit_not_found"],
                    reply_markup=build_habit_fields_keyboard(custom_fields, "edit", lang, labels=labels),
                )
                return True
            session.temp_data = {
                "habit_action": "edit",
                "habit_edit_stage": "attr",
                "habit_edit_field": name,
            }
            if session_repo:
                await session_repo.save(session)
            cfg = profile.habit_schema.fields[name]
            details = _format_field_details(name, cfg, lang, profile.habit_schema.fields)
            display_name = _display_field_name(name, lang, profile.habit_schema.fields)
            prompt = _messages_for_lang(lang)["habit_edit_attr_prompt"].format(name=display_name)
            await update.message.reply_text(
                f"{details}\n\n{prompt}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_habit_edit_attr_keyboard(
                    lang,
                    allowed={"description"} if name == "diary" else None,
                ),
            )
            return True

        if stage == "attr":
            name = field_name or ""
            cfg = profile.habit_schema.fields.get(name) if name else None
            details = (
                _format_field_details(name, cfg, lang, profile.habit_schema.fields)
                if cfg
                else ""
            )
            prompt = _messages_for_lang(lang)["habit_edit_attr_prompt"].format(
                name=_display_field_name(name, lang, profile.habit_schema.fields)
            )
            await update.message.reply_text(
                f"{details}\n\n{prompt}" if details else prompt,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_habit_edit_attr_keyboard(
                    lang,
                    allowed={"description"} if name == "diary" else None,
                ),
            )
            return True

        if stage == "value":
            if not field_name or field_name not in profile.habit_schema.fields:
                await update.message.reply_text(
                    _messages_for_lang(lang)["habit_edit_not_found"],
                    reply_markup=_keyboard(lang),
                )
                session.state = ConversationState.IDLE
                session.temp_data = {}
                if session_repo:
                    await session_repo.save(session)
                return True

            cfg = profile.habit_schema.fields[field_name]
            raw = text.strip()
            if field_name == "diary" and attr != "description":
                await update.message.reply_text(
                    _messages_for_lang(lang)["habit_edit_attr_prompt"].format(
                        name=_display_field_name(field_name, lang, profile.habit_schema.fields)
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=build_habit_edit_attr_keyboard(lang, allowed={"description"}),
                )
                return True

            if attr == "name":
                new_name = raw
                if not new_name or " " in new_name:
                    await update.message.reply_text(_messages_for_lang(lang)["habit_edit_name_invalid"])
                    return True
                if new_name in PROTECTED_HABIT_FIELDS:
                    await update.message.reply_text(_messages_for_lang(lang)["habit_edit_name_reserved"])
                    return True
                if new_name != field_name and new_name in profile.habit_schema.fields:
                    await update.message.reply_text(_messages_for_lang(lang)["habit_edit_name_taken"])
                    return True
                cfg = profile.habit_schema.fields.pop(field_name)
                profile.habit_schema.fields[new_name] = cfg
                await user_repo.update(profile)
                await _finish_and_reset(new_name)
                return True

            if attr == "description":
                if not raw:
                    await update.message.reply_text(_messages_for_lang(lang)["habit_edit_description_error"])
                    return True
                cfg.description = raw
                profile.habit_schema.fields[field_name] = cfg
                await user_repo.update(profile)
                await _finish_and_reset(field_name)
                return True

            if attr == "type":
                type_hint = raw.lower() or "string"
                type_value = None
                if type_hint in {"int", "integer"}:
                    type_value = "integer"
                elif type_hint in {"float", "double", "number"}:
                    type_value = "number"
                elif type_hint in {"bool", "boolean"}:
                    type_value = "boolean"
                elif type_hint in {"string", "text", ""}:
                    type_value = "string"
                if not type_value:
                    await update.message.reply_text(
                        _messages_for_lang(lang)["habit_add_type_error"],
                        reply_markup=build_habit_type_keyboard(lang),
                    )
                    return True
                cfg.type = type_value
                if type_value not in {"integer", "number"}:
                    cfg.minimum = None
                    cfg.maximum = None
                if cfg.default is not None:
                    normalized, error_key, _ = _normalize_default_value(cfg.default, cfg)
                    cfg.default = None if error_key else normalized
                profile.habit_schema.fields[field_name] = cfg
                await user_repo.update(profile)
                await _finish_and_reset(field_name)
                return True

            if attr == "default":
                parsed, error_key, error_params = _parse_default_text(raw, cfg)
                if error_key:
                    msg = _messages_for_lang(lang)[error_key]
                    if error_params:
                        msg = msg.format(**error_params)
                    await update.message.reply_text(msg)
                    return True
                cfg.default = parsed
                profile.habit_schema.fields[field_name] = cfg
                await user_repo.update(profile)
                await _finish_and_reset(field_name)
                return True

            if attr in {"min", "max"}:
                if _base_numeric_type(cfg.type) not in {"integer", "number"}:
                    await update.message.reply_text(_messages_for_lang(lang)["habit_edit_min_not_numeric"])
                    return True
                value = None
                if raw not in {"", "-"}:
                    try:
                        base_type = _base_numeric_type(cfg.type)
                        value = int(raw) if base_type == "integer" else float(raw)
                    except ValueError:
                        error_key = "habit_edit_min_error" if attr == "min" else "habit_edit_max_error"
                        await update.message.reply_text(_messages_for_lang(lang)[error_key])
                        return True
                if attr == "min":
                    if cfg.maximum is not None and value is not None and value > cfg.maximum:
                        await update.message.reply_text(
                            _messages_for_lang(lang)["habit_edit_max_less_than_min"].format(min=value)
                        )
                        return True
                    cfg.minimum = value
                else:
                    if cfg.minimum is not None and value is not None and value < cfg.minimum:
                        await update.message.reply_text(
                            _messages_for_lang(lang)["habit_edit_max_less_than_min"].format(min=cfg.minimum)
                        )
                        return True
                    cfg.maximum = value
                if cfg.default is not None:
                    normalized, error_key, _ = _normalize_default_value(cfg.default, cfg)
                    cfg.default = None if error_key else normalized
                profile.habit_schema.fields[field_name] = cfg
                await user_repo.update(profile)
                await _finish_and_reset(field_name)
                return True

    if action == "add":
        temp = session.temp_data or {}
        stage = temp.get("habit_add_stage") or "name"
        new_field = temp.get("habit_new_field") or {}

        async def _finish_and_reset():
            session.state = ConversationState.IDLE
            session.temp_data = {}
            if session_repo:
                await session_repo.save(session)

        # Stage 1: field name
        if stage == "name":
            name = text.strip()
            if not name:
                await update.message.reply_text(_messages_for_lang(lang)["habit_add_name_invalid"])
                return True
            if " " in name:
                await update.message.reply_text(_messages_for_lang(lang)["habit_add_name_invalid"])
                return True
            if name in PROTECTED_HABIT_FIELDS:
                await update.message.reply_text(_messages_for_lang(lang)["habit_add_name_reserved"])
                return True
            if name in profile.habit_schema.fields:
                await update.message.reply_text(_messages_for_lang(lang)["habit_add_name_taken"])
                return True
            new_field["name"] = name
            session.temp_data = {"habit_action": "add", "habit_add_stage": "description", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(_messages_for_lang(lang)["habit_add_description_prompt"], parse_mode=ParseMode.MARKDOWN)
            return True

        # Stage 2: description
        if stage == "description":
            description = text.strip()
            if not description:
                await update.message.reply_text(_messages_for_lang(lang)["habit_add_description_error"])
                return True
            new_field["description"] = description
            if new_field.get("name") == "diary":
                profile.habit_schema.fields["diary"] = HabitFieldConfig(
                    type="string",
                    description=description,
                    required=False,
                )
                profile.habit_schema.include_diary = True
                await user_repo.update(profile)
                await update.message.reply_text(
                    _messages_for_lang(lang)["habit_added"].format(
                        name=_display_field_name(new_field["name"], lang, profile.habit_schema.fields)
                    ),
                    reply_markup=_keyboard(lang),
                )
                await _finish_and_reset()
                return True
            session.temp_data = {"habit_action": "add", "habit_add_stage": "type", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(
                _messages_for_lang(lang)["habit_add_type_prompt"],
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=build_habit_type_keyboard(lang),
            )
            return True

        # Stage 3: type
        if stage == "type":
            type_hint = text.strip().lower() or "string"
            type_value = None
            if type_hint in {"int", "integer"}:
                type_value = "integer"
            elif type_hint in {"float", "double", "number"}:
                type_value = "number"
            elif type_hint in {"bool", "boolean"}:
                type_value = "boolean"
            elif type_hint in {"string", "text", ""}:
                type_value = "string"
            if not type_value:
                await update.message.reply_text(
                    _messages_for_lang(lang)["habit_add_type_error"],
                    reply_markup=build_habit_type_keyboard(lang),
                )
                return True
            new_field["type"] = type_value
            if type_value in {"integer", "number"}:
                session.temp_data = {"habit_action": "add", "habit_add_stage": "min", "habit_new_field": new_field}
                if session_repo:
                    await session_repo.save(session)
                await update.message.reply_text(_min_prompt(lang, type_value), parse_mode=ParseMode.MARKDOWN)
                return True
            session.temp_data = {"habit_action": "add", "habit_add_stage": "default", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(
                _default_prompt(lang, type_value, mode="add"),
                parse_mode=ParseMode.MARKDOWN,
            )
            return True

        # Stage 4: min for integers
        if stage == "min":
            raw = text.strip()
            min_value = None
            if raw not in {"", "-"}:
                try:
                    base_type = _base_numeric_type(new_field.get("type"))
                    min_value = int(raw) if base_type == "integer" else float(raw)
                except ValueError:
                    await update.message.reply_text(_messages_for_lang(lang)["habit_add_min_error"])
                    return True
            new_field["minimum"] = min_value
            session.temp_data = {"habit_action": "add", "habit_add_stage": "max", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(_max_prompt(lang, new_field.get("type")), parse_mode=ParseMode.MARKDOWN)
            return True

        # Stage 5: max for integers
        if stage == "max":
            raw = text.strip()
            max_value = None
            if raw not in {"", "-"}:
                try:
                    base_type = _base_numeric_type(new_field.get("type"))
                    max_value = int(raw) if base_type == "integer" else float(raw)
                except ValueError:
                    await update.message.reply_text(_messages_for_lang(lang)["habit_add_max_error"])
                    return True
            min_value = new_field.get("minimum")
            if min_value is not None and max_value is not None and max_value < min_value:
                await update.message.reply_text(
                    _messages_for_lang(lang)["habit_add_max_less_than_min"].format(min=min_value)
                )
                return True
            new_field["maximum"] = max_value
            session.temp_data = {"habit_action": "add", "habit_add_stage": "default", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(
                _default_prompt(lang, new_field.get("type"), mode="add"),
                parse_mode=ParseMode.MARKDOWN,
            )
            return True

        # Stage 6: default value
        if stage == "default":
            cfg = HabitFieldConfig(
                type=new_field.get("type", "string"),
                description=new_field.get("description", new_field.get("name", "")),
                minimum=new_field.get("minimum"),
                maximum=new_field.get("maximum"),
                required=True,
            )
            parsed, error_key, error_params = _parse_default_text(text, cfg)
            if error_key:
                msg = _messages_for_lang(lang)[error_key]
                if error_params:
                    msg = msg.format(**error_params)
                await update.message.reply_text(msg)
                return True
            cfg.default = parsed
            profile.habit_schema.fields[new_field["name"]] = cfg
            await user_repo.update(profile)
            await update.message.reply_text(
                _messages_for_lang(lang)["habit_added"].format(
                    name=_display_field_name(new_field["name"], lang, profile.habit_schema.fields)
                ),
                reply_markup=_keyboard(lang),
            )
            await _finish_and_reset()
            return True
    else:
        await update.message.reply_text(
            _messages_for_lang(lang)["cancelled_config"],
            reply_markup=build_main_menu_keyboard(lang)
        )

    session.state = ConversationState.IDLE
    session.temp_data = {}
    if session_repo:
        await session_repo.save(session)
    return True
