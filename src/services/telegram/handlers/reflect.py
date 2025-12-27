from datetime import datetime
import asyncio
import re

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import DEFAULT_REFLECTION_QUESTIONS_EN, DEFAULT_REFLECTION_QUESTIONS_RU, MESSAGES_EN, MESSAGES_RU
from src.config.settings import get_settings
from src.models.entry import ReflectionEntry
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, SheetAccessError, SheetWriteError
from src.models.user import CustomQuestion
from src.models.session import ConversationState, SessionData
from src.services.telegram.keyboards import build_confirmation_keyboard
from src.services.llm.extractors.reflection_extractor import ReflectionExtractor
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
import json


_OP_TIMEOUT = get_settings().operation_timeout_seconds


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        get_session_repo(context),
        get_user_repo(context),
        get_sheets_client(context),
        get_llm_client(context),
    )


async def _safe_edit_message(query, text: str) -> None:
    try:
        await query.edit_message_text(text)
    except Exception:
        return None


async def reflect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Begin reflection flow."""

    if not update.effective_user or not update.message:
        return
    session_repo, user_repo, _, llm_client = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    lang = resolve_language(profile)
    questions = [q for q in (profile.custom_questions if profile else []) if q.active]
    if not questions:
        if profile is None:
            await update.message.reply_text(_messages_for_lang(lang)["no_reflection_questions"])
            return
        defaults = DEFAULT_REFLECTION_QUESTIONS_RU if lang == "ru" else DEFAULT_REFLECTION_QUESTIONS_EN
        profile.custom_questions = [
            CustomQuestion(**q, language=lang) for q in defaults
        ]
        await user_repo.update(profile)
        questions = [q for q in profile.custom_questions if q.active]
        await update.message.reply_text(_messages_for_lang(lang)["reflect_seeded"])
    sheet_id = profile.sheet_id if profile else None
    if not sheet_id:
        await update.message.reply_text(_messages_for_lang(lang)["sheet_not_configured"])
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
    await update.message.reply_text(_messages_for_lang(lang)["reflect_intro"].format(questions=question_lines))


async def handle_reflect_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Handle reflection answers. Returns True if handled."""

    if not update.effective_user or not update.message:
        return False
    session_repo, user_repo, sheets_client, llm_client = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.REFLECT_ANSWERING_QUESTIONS:
        return False

    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    lang = resolve_language(profile)
    questions = session.temp_data.get("reflect_questions") if session and session.temp_data else []
    if not questions:
        questions = [q.text for q in (profile.custom_questions if profile else []) if q.active]
    if not questions:
        await update.message.reply_text(_messages_for_lang(lang)["error_occurred"])
        return True
    answers = {}
    if llm_client:
        progress_message = None
        try:
            extractor = ReflectionExtractor(llm_client)
            progress_message = await update.message.reply_text(_messages_for_lang(lang)["processing"])
            answers = await asyncio.wait_for(
                extractor.extract(text, questions, language=lang),
                timeout=_OP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            await update.message.reply_text(_messages_for_lang(lang)["external_timeout_error"])
            answers = {}
        except ExternalTimeoutError:
            await update.message.reply_text(_messages_for_lang(lang)["external_timeout_error"])
            answers = {}
        except ExternalResponseError:
            await update.message.reply_text(_messages_for_lang(lang)["external_response_error"])
            answers = {}
        except Exception:
            answers = {}
        finally:
            await safe_delete_message(progress_message)

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
        _messages_for_lang(lang)["confirm_generic"].format(preview=preview),
        reply_markup=build_confirmation_keyboard(prefix="reflect", language=lang),
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
        lang = resolve_language(await resolve_user_profile(update, context))
        await query.edit_message_text(_messages_for_lang(lang)["error_occurred"])
        return

    decision = data.split(":", 1)[1]
    if decision == "yes":
        profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
        lang = resolve_language(profile)
        sheet_id = profile.sheet_id if profile else None
        if sheet_id and sheets_client:
            entry = ReflectionEntry(**session.pending_entry)
            error_key = None
            try:
                await _safe_edit_message(query, _messages_for_lang(lang)["saving_data"])
                await asyncio.wait_for(
                    sheets_client.append_reflection_entry(sheet_id, entry),
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
                await safe_delete_message(query.message)
                session.state = ConversationState.IDLE
                session.pending_entry = None
                session.reflection_answers = {}
                if session_repo:
                    await session_repo.save(session)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=_messages_for_lang(lang)[error_key],
                )
                await query.answer()
                return
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            await safe_delete_message(query.message)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=_messages_for_lang(lang)["reflect_done"]
            )
            await increment_usage_stat(profile, user_repo, "reflection")
        else:
            await query.edit_message_text(_messages_for_lang(lang)["sheet_not_configured"])
    else:
        lang = resolve_language(await resolve_user_profile(update, context))
        await query.edit_message_text(_messages_for_lang(lang)["cancelled"])

    session.state = ConversationState.IDLE
    session.pending_entry = None
    session.reflection_answers = {}
    if session_repo:
        await session_repo.save(session)
    await query.answer()
