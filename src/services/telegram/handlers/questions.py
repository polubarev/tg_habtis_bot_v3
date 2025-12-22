from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config.constants import (
    DEFAULT_REFLECTION_QUESTIONS_EN,
    DEFAULT_REFLECTION_QUESTIONS_RU,
    INLINE_BUTTONS_EN,
    INLINE_BUTTONS_RU,
    MESSAGES_EN,
    MESSAGES_RU,
)
from src.models.session import ConversationState
from src.models.user import CustomQuestion
from src.services.telegram.keyboards import build_main_menu_keyboard
from src.services.telegram.utils import resolve_language


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        context.application.bot_data.get("session_repo"),
        context.application.bot_data.get("user_repo"),
    )


def _keyboard(lang: str):
    btns = INLINE_BUTTONS_RU if lang == "ru" else INLINE_BUTTONS_EN
    buttons = [
        [
            InlineKeyboardButton(btns["question_add"], callback_data="q_cfg:add"),
            InlineKeyboardButton(btns["question_remove"], callback_data="q_cfg:remove"),
        ],
        [
            InlineKeyboardButton(btns["question_reset"], callback_data="q_cfg:reset"),
            InlineKeyboardButton(btns["question_cancel"], callback_data="q_cfg:cancel"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def _format_questions(profile, lang: str) -> str:
    questions = profile.custom_questions if profile else []
    if not questions:
        return _messages_for_lang(lang)["empty_value"]
    return "\n".join(f"- {q.id}: {q.text}" for q in questions)


async def questions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current questions and options."""

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
            session.state = ConversationState.CONFIG_ADDING_QUESTION
            session.temp_data = {"q_action": None}
            await session_repo.save(session)
    msg = _messages_for_lang(lang)["question_intro"].format(questions=_format_questions(profile, lang))
    await update.message.reply_text(msg, reply_markup=_keyboard(lang))


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
    lang = resolve_language(profile)
    if session:
        session.state = ConversationState.CONFIG_ADDING_QUESTION
        session.temp_data = {"q_action": action}
        await session_repo.save(session)

    if action == "add":
        if session:
            session.temp_data.update({"q_add_stage": "id", "q_new": {}})
            await session_repo.save(session)
        await query.edit_message_text(
            _messages_for_lang(lang)["question_add_id_prompt"]
            + "\n\n"
            + _messages_for_lang(lang)["question_add_json_example"],
            parse_mode=ParseMode.MARKDOWN,
        )
    elif action == "remove":
        await query.edit_message_text(_messages_for_lang(lang)["question_remove_prompt"])
    elif action == "reset":
        if profile and user_repo:
            defaults = DEFAULT_REFLECTION_QUESTIONS_RU if lang == "ru" else DEFAULT_REFLECTION_QUESTIONS_EN
            profile.custom_questions = [CustomQuestion(**q, language=lang) for q in defaults]
            await user_repo.update(profile)
        await query.edit_message_text(_messages_for_lang(lang)["question_reset"])
        if session_repo and session:
            session.state = ConversationState.IDLE
            session.temp_data = {}
            await session_repo.save(session)
    elif action == "cancel":
        await query.edit_message_text(_messages_for_lang(lang)["cancelled_config"])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_messages_for_lang(lang)["cancelled_config"],
            reply_markup=build_main_menu_keyboard(lang)
        )
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
    lang = resolve_language(profile)

    text = update.message.text or ""
    if action == "add":
        temp = session.temp_data or {}
        stage = temp.get("q_add_stage") or "id"
        q_new = temp.get("q_new") or {}

        async def _finish():
            session.state = ConversationState.IDLE
            session.temp_data = {}
            if session_repo:
                await session_repo.save(session)

        def _try_parse_json(raw: str):
            import json

            try:
                data = json.loads(raw)
            except Exception:
                return None
            if not isinstance(data, dict):
                return None
            q_id_val = str(data.get("id", "")).strip()
            if not q_id_val or " " in q_id_val:
                return None
            if any(q.id == q_id_val for q in profile.custom_questions):
                return None
            lang_val = str(data.get("language") or profile.language or "en").lower()
            if lang_val not in {"en", "ru"}:
                return None
            active_val = bool(data.get("active", True))
            q_text_val = str(data.get("text", "")).strip()
            if not q_text_val:
                return None
            return CustomQuestion(id=q_id_val, text=q_text_val, language=lang_val, active=active_val)

        if stage == "id":
            parsed = _try_parse_json(text)
            if parsed:
                profile.custom_questions.append(parsed)
                await user_repo.update(profile)
                await update.message.reply_text(_messages_for_lang(lang)["question_added"].format(id=parsed.id))
                await _finish()
                return True
            q_id = text.strip()
            if not q_id or " " in q_id:
                await update.message.reply_text(_messages_for_lang(lang)["question_add_id_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            if any(q.id == q_id for q in profile.custom_questions):
                await update.message.reply_text(_messages_for_lang(lang)["question_add_id_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            q_new["id"] = q_id
            session.temp_data = {"q_action": "add", "q_add_stage": "text", "q_new": q_new}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(_messages_for_lang(lang)["question_add_text_prompt"], parse_mode=ParseMode.MARKDOWN)
            return True

        if stage == "text":
            q_text = text.strip()
            if not q_text:
                await update.message.reply_text(_messages_for_lang(lang)["question_add_text_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            q_new["text"] = q_text
            session.temp_data = {"q_action": "add", "q_add_stage": "lang", "q_new": q_new}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(_messages_for_lang(lang)["question_add_lang_prompt"], parse_mode=ParseMode.MARKDOWN)
            return True

        if stage == "lang":
            lang_value = text.strip().lower() or profile.language or "en"
            if lang_value not in {"en", "ru"}:
                await update.message.reply_text(_messages_for_lang(lang)["question_add_lang_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            q_new["language"] = lang_value
            session.temp_data = {"q_action": "add", "q_add_stage": "active", "q_new": q_new}
            if session_repo:
                await session_repo.save(session)
            await update.message.reply_text(_messages_for_lang(lang)["question_add_active_prompt"], parse_mode=ParseMode.MARKDOWN)
            return True

        if stage == "active":
            ans = text.strip().lower()
            active = True
            if ans in {"no", "n", "false", "0"}:
                active = False
            elif ans in {"yes", "y", "true", "1", ""}:
                active = True
            else:
                await update.message.reply_text(_messages_for_lang(lang)["question_add_active_prompt"], parse_mode=ParseMode.MARKDOWN)
                return True
            q_new["active"] = active
            profile.custom_questions.append(
                CustomQuestion(
                    id=q_new.get("id"),
                    text=q_new.get("text"),
                    language=q_new.get("language", profile.language),
                    active=active,
                )
            )
            await user_repo.update(profile)
            await update.message.reply_text(_messages_for_lang(lang)["question_added"].format(id=q_new.get("id")))
            await _finish()
            return True
    elif action == "remove":
        q_id = text.strip()
        before = len(profile.custom_questions)
        profile.custom_questions = [q for q in profile.custom_questions if q.id != q_id]
        if len(profile.custom_questions) == before:
            await update.message.reply_text(_messages_for_lang(lang)["question_remove_prompt"])
            return True
        await user_repo.update(profile)
        await update.message.reply_text(_messages_for_lang(lang)["question_removed"].format(id=q_id))
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
