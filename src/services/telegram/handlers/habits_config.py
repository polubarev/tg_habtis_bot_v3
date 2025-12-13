from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src.config.constants import DEFAULT_HABIT_SCHEMA, HABITS_SHEET_COLUMNS, MESSAGES_EN, MESSAGES_RU
from src.models.habit import HabitFieldConfig
from src.models.session import ConversationState
import json

BASE_HABIT_FIELDS = set(HABITS_SHEET_COLUMNS)


from src.services.telegram.keyboards import build_main_menu_keyboard

def _get_lang(update: Update) -> str:
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return "ru" if code.startswith("ru") else "en"

def _messages(update: Update):
    return MESSAGES_RU if _get_lang(update) == "ru" else MESSAGES_EN


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

    try:
        if action == "add":
            if session:
                session.temp_data.update({"habit_add_stage": "name", "habit_new_field": {}})
                await session_repo.save(session)
            await query.edit_message_text(
                _messages(update)["habit_add_name_prompt"] + "\n\n" + _messages(update)["habit_add_json_example"],
                parse_mode=ParseMode.MARKDOWN,
            )
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
            # The user might be stuck with an inline keyboard above. We can't easily replace it with a reply keyboard via callback query alone
            # without sending a new message. Sending a new message ("Cancelled") with Main Menu is cleaner.
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=_messages(update)["cancelled_config"],
                reply_markup=build_main_menu_keyboard(_get_lang(update))
            )
            if session_repo and session:
                session.state = ConversationState.IDLE
                session.temp_data = {}
                await session_repo.save(session)
    except Exception:
        # ignore edit collisions (e.g., message not modified/expired)
        pass


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
    # allow cancelling the flow via text
    if text.strip().lower() in {"cancel", "/cancel", "отмена"}:
        session.state = ConversationState.IDLE
        session.temp_data = {}
        if session_repo:
            await session_repo.save(session)
        await update.message.reply_text(
            _messages(update)["cancelled_config"],
            reply_markup=build_main_menu_keyboard(_get_lang(update))
        )
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
            cfg = HabitFieldConfig(
                type=type_value,
                description=str(data.get("description") or name),
                minimum=minimum,
                maximum=maximum,
                required=bool(data.get("required", True)),
            )
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

        # Stage 1: field name
        if stage == "name":
            parsed = _try_parse_json(text)
            if parsed and all(parsed):
                for name, cfg in parsed:
                    profile.habit_schema.fields[name] = cfg
                await user_repo.update(profile)
                added_names = ", ".join(name for name, _ in parsed)
                await update.message.reply_text(_messages(update)["habit_added"].format(name=added_names))
                await _finish_and_reset()
                return True
            name = text.strip()
            if not name:
                await update.message.reply_text(_messages(update)["habit_add_name_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            if " " in name:
                await update.message.reply_text(_messages(update)["habit_add_name_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            if name in BASE_HABIT_FIELDS or name in profile.habit_schema.fields:
                await update.message.reply_text(_messages(update)["habit_add_name_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            new_field["name"] = name
            session.temp_data = {"habit_action": "add", "habit_add_stage": "description", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(_messages(update)["habit_add_description_prompt"], parse_mode=ParseMode.MARKDOWN)
            return True

        # Stage 2: description
        if stage == "description":
            description = text.strip()
            if not description:
                await update.message.reply_text(_messages(update)["habit_add_description_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            new_field["description"] = description
            session.temp_data = {"habit_action": "add", "habit_add_stage": "type", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(_messages(update)["habit_add_type_prompt"], parse_mode=ParseMode.MARKDOWN)
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
                await update.message.reply_text(_messages(update)["habit_add_type_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            new_field["type"] = type_value
            if type_value in {"integer", "number"}:
                session.temp_data = {"habit_action": "add", "habit_add_stage": "min", "habit_new_field": new_field}
                if session_repo:
                    await session_repo.save(session)
                await update.message.reply_text(_messages(update)["habit_add_min_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            # finalize for non-int
            profile.habit_schema.fields[new_field["name"]] = HabitFieldConfig(
                type=type_value,
                description=new_field.get("description", new_field["name"]),
                required=True,
            )
            await user_repo.update(profile)
            await update.message.reply_text(_messages(update)["habit_added"].format(name=new_field["name"]))
            await _finish_and_reset()
            return True

        # Stage 4: min for integers
        if stage == "min":
            raw = text.strip()
            min_value = None
            if raw not in {"", "-"}:
                try:
                    base_type = new_field.get("type")
                    base_type = base_type[0] if isinstance(base_type, list) else base_type
                    min_value = int(raw) if base_type == "integer" else float(raw)
                except ValueError:
                    await update.message.reply_text(_messages(update)["habit_add_min_prompt"], parse_mode=ParseMode.MARKDOWN)
                    return True
            new_field["minimum"] = min_value
            session.temp_data = {"habit_action": "add", "habit_add_stage": "max", "habit_new_field": new_field}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(_messages(update)["habit_add_max_prompt"], parse_mode=ParseMode.MARKDOWN)
            return True

        # Stage 5: max for integers
        if stage == "max":
            raw = text.strip()
            max_value = None
            if raw not in {"", "-"}:
                try:
                    base_type = new_field.get("type")
                    base_type = base_type[0] if isinstance(base_type, list) else base_type
                    max_value = int(raw) if base_type == "integer" else float(raw)
                except ValueError:
                    await update.message.reply_text(_messages(update)["habit_add_max_prompt"], parse_mode=ParseMode.MARKDOWN)
                    return True
            min_value = new_field.get("minimum")
            if min_value is not None and max_value is not None and max_value < min_value:
                await update.message.reply_text(_messages(update)["habit_add_max_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            profile.habit_schema.fields[new_field["name"]] = HabitFieldConfig(
                type=new_field.get("type", "integer"),
                description=new_field.get("description", new_field["name"]),
                minimum=min_value,
                maximum=max_value,
                required=True,
            )
            await user_repo.update(profile)
            await update.message.reply_text(_messages(update)["habit_added"].format(name=new_field["name"]))
            await _finish_and_reset()
            return True
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
        await update.message.reply_text(
            _messages(update)["cancelled_config"],
            reply_markup=build_main_menu_keyboard(_get_lang(update))
        )

    session.state = ConversationState.IDLE
    session.temp_data = {}
    if session_repo:
        await session_repo.save(session)
    return True
