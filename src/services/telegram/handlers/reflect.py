from datetime import datetime
import re

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import DEFAULT_REFLECTION_QUESTIONS, MESSAGES_EN, MESSAGES_RU
from src.models.entry import ReflectionEntry
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, SheetAccessError, SheetWriteError
from src.models.user import CustomQuestion
from src.models.session import ConversationState, SessionData
from src.services.telegram.keyboards import build_confirmation_keyboard
from src.services.llm.extractors.reflection_extractor import ReflectionExtractor
from src.services.telegram.utils import resolve_user_timezone
from src.services.telegram.utils import resolve_user_timezone
import json


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        context.application.bot_data.get("session_repo"),
        context.application.bot_data.get("user_repo"),
        context.application.bot_data.get("sheets_client"),
        context.application.bot_data.get("llm_client"),
    )


async def reflect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Begin reflection flow."""

    if not update.effective_user or not update.message:
        return
    session_repo, user_repo, _, llm_client = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    questions = [q for q in (profile.custom_questions if profile else []) if q.active]
    if not questions:
        if profile is None:
            await update.message.reply_text("Нет вопросов для размышлений. Добавь их в /config.")
            return
        profile.custom_questions = [
            CustomQuestion(**q, language=profile.language) for q in DEFAULT_REFLECTION_QUESTIONS
        ]
        await user_repo.update(profile)
        questions = [q for q in profile.custom_questions if q.active]
        await update.message.reply_text(_messages(update)["reflect_seeded"])
    sheet_id = profile.sheet_id if profile else None
    if not sheet_id:
        await update.message.reply_text(_messages(update)["sheet_not_configured"])
        return
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None:
        session = SessionData(user_id=update.effective_user.id)
    session.state = ConversationState.REFLECT_ANSWERING_QUESTIONS
    session.current_question_index = None
    session.reflection_answers = {}
    session.temp_data = session.temp_data or {}
    session.temp_data["reflect_questions"] = [q.text for q in questions]
    await session_repo.save(session)
    question_lines = "\n".join(f"{idx+1}. {q.text}" for idx, q in enumerate(questions))
    await update.message.reply_text(_messages(update)["reflect_intro"].format(questions=question_lines))


async def handle_reflect_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Handle reflection answers. Returns True if handled."""

    if not update.effective_user or not update.message:
        return False
    session_repo, user_repo, sheets_client, llm_client = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.REFLECT_ANSWERING_QUESTIONS:
        return False

    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    questions = session.temp_data.get("reflect_questions") if session and session.temp_data else []
    if not questions:
        questions = [q.text for q in (profile.custom_questions if profile else []) if q.active]
    if not questions:
        await update.message.reply_text(_messages(update)["error_occurred"])
        return True

    lang = "ru" if (update.effective_user and (update.effective_user.language_code or "").lower().startswith("ru")) else "en"
    answers = {}
    if llm_client:
        try:
            extractor = ReflectionExtractor(llm_client)
            answers = await extractor.extract(text, questions, language=lang)
        except ExternalTimeoutError:
            await update.message.reply_text(_messages(update)["external_timeout_error"])
            answers = {}
        except ExternalResponseError:
            await update.message.reply_text(_messages(update)["external_response_error"])
            answers = {}
        except Exception:
            answers = {}

    normalized: dict[str, str] = {}
    for q in questions:
        val = ""
        if isinstance(answers, dict):
            val = answers.get(q, "")
        if val is None or (isinstance(val, str) and not val.strip()):
            val = text
        normalized[q] = str(val)
    answers = normalized

    # Heuristic split for two-question flows when LLM returns the same blob
    if len(questions) == 2 and all(v == text for v in answers.values()):
        parts = re.split(r"\s+а\s+", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) != 2:
            parts = re.split(r"\s+and\s+", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            answers[questions[0]] = parts[0].strip()
            answers[questions[1]] = parts[1].strip()

    user_tz = resolve_user_timezone(profile)
    entry = ReflectionEntry(timestamp=datetime.now(user_tz), answers=answers)
    session.pending_entry = entry.model_dump(mode="json")
    session.state = ConversationState.REFLECT_AWAITING_CONFIRMATION
    session.current_question_index = None
    session.reflection_answers = answers
    if session_repo:
        await session_repo.save(session)
    preview = json.dumps(entry.model_dump(), ensure_ascii=False, indent=2, default=str)
    await update.message.reply_text(
        _messages(update)["confirm_generic"].format(preview=preview),
        reply_markup=build_confirmation_keyboard(prefix="reflect"),
        parse_mode="Markdown",
    )
    return True


async def handle_reflect_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("reflect_confirm:"):
        return

    session_repo, user_repo, sheets_client, _ = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.REFLECT_AWAITING_CONFIRMATION or not session.pending_entry:
        await query.answer()
        await query.edit_message_text(_messages(update)["error_occurred"])
        return

    decision = data.split(":", 1)[1]
    if decision == "yes":
        profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
        sheet_id = profile.sheet_id if profile else None
        if sheet_id and sheets_client:
            entry = ReflectionEntry(**session.pending_entry)
            try:
                await sheets_client.append_reflection_entry(sheet_id, entry)
            except SheetAccessError:
                await query.edit_message_text(_messages(update)["sheet_permission_error"])
                session.state = ConversationState.IDLE
                session.pending_entry = None
                session.reflection_answers = {}
                if session_repo:
                    await session_repo.save(session)
                await query.answer()
                return
            except ExternalTimeoutError:
                await query.edit_message_text(_messages(update)["external_timeout_error"])
                session.state = ConversationState.IDLE
                session.pending_entry = None
                session.reflection_answers = {}
                if session_repo:
                    await session_repo.save(session)
                await query.answer()
                return
            except SheetWriteError:
                await query.edit_message_text(_messages(update)["sheet_write_error"])
                session.state = ConversationState.IDLE
                session.pending_entry = None
                session.reflection_answers = {}
                if session_repo:
                    await session_repo.save(session)
                await query.answer()
                return
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=_messages(update)["reflect_done"]
            )
        else:
            await query.edit_message_text(_messages(update)["sheet_not_configured"])
    else:
        await query.edit_message_text(_messages(update)["cancelled"])

    session.state = ConversationState.IDLE
    session.pending_entry = None
    session.reflection_answers = {}
    if session_repo:
        await session_repo.save(session)
    await query.answer()
