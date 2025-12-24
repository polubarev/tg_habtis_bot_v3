from datetime import datetime
import asyncio
import json

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.config.settings import get_settings
from src.models.entry import DreamEntry
from src.core.exceptions import ExternalTimeoutError, SheetAccessError, SheetWriteError
from src.models.session import ConversationState, SessionData
from src.services.telegram.keyboards import build_confirmation_keyboard
from src.services.telegram.utils import (
    get_session_repo,
    get_sheets_client,
    get_user_repo,
    resolve_language,
    resolve_user_profile,
    resolve_user_timezone,
    safe_delete_message,
)


_OP_TIMEOUT = get_settings().operation_timeout_seconds


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        get_session_repo(context),
        get_user_repo(context),
        get_sheets_client(context),
    )


async def _safe_edit_message(query, text: str) -> None:
    try:
        await query.edit_message_text(text)
    except Exception:
        return None


async def dream_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start dream logging flow."""

    if not update.effective_user or not update.message:
        return
    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    session_repo, _, _ = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None:
        session = SessionData(user_id=update.effective_user.id)
    session.state = ConversationState.DREAM_AWAITING_CONTENT
    if session_repo:
        await session_repo.save(session)
    await update.message.reply_text(_messages_for_lang(lang)["dream_prompt"])


async def handle_dream_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Handle dream text/voice. Returns True if handled."""

    if not update.effective_user:
        return False
    session_repo, user_repo, sheets_client = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.DREAM_AWAITING_CONTENT:
        return False

    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    lang = resolve_language(profile)
    sheet_id = profile.sheet_id if profile else None
    if not sheet_id:
        await update.message.reply_text(_messages_for_lang(lang)["sheet_not_configured"])
        session.state = ConversationState.IDLE
        session.pending_entry = None
        if session_repo:
            await session_repo.save(session)
        return True

    user_tz = resolve_user_timezone(profile)
    entry = DreamEntry(timestamp=datetime.now(user_tz), record=text)
    session.pending_entry = entry.model_dump(mode="json")
    session.state = ConversationState.DREAM_AWAITING_CONFIRMATION
    if session_repo:
        await session_repo.save(session)

    preview = json.dumps(entry.model_dump(), ensure_ascii=False, indent=2, default=str)
    await update.message.reply_text(
        _messages_for_lang(lang)["confirm_generic"].format(preview=preview),
        reply_markup=build_confirmation_keyboard(prefix="dream", language=lang),
        parse_mode="Markdown",
    )
    return True


async def handle_dream_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_user:
        return
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("dream_confirm:"):
        return

    session_repo, user_repo, sheets_client = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.DREAM_AWAITING_CONFIRMATION or not session.pending_entry:
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
            entry = DreamEntry(**session.pending_entry)
            error_key = None
            try:
                await _safe_edit_message(query, _messages_for_lang(lang)["saving_data"])
                await asyncio.wait_for(
                    sheets_client.append_dream_entry(sheet_id, entry),
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
                text=_messages_for_lang(lang)["dream_saved"]
            )
        else:
            await query.edit_message_text(_messages_for_lang(lang)["sheet_not_configured"])
    else:
        lang = resolve_language(await resolve_user_profile(update, context))
        await query.edit_message_text(_messages_for_lang(lang)["cancelled"])

    session.state = ConversationState.IDLE
    session.pending_entry = None
    if session_repo:
        await session_repo.save(session)
    await query.answer()
