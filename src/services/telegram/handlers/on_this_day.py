"""`/on_this_day` command: show diary entries from past years on this date."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.config.settings import get_settings
from src.core.exceptions import ExternalTimeoutError, SheetAccessError, SheetWriteError
from src.models.user import UserProfile
from src.services.on_this_day import (
    OnThisDayPayload,
    assemble_payloads,
    compute_on_this_day_dates,
    format_on_this_day_message,
)
from src.services.telegram.utils import (
    get_sheets_client,
    resolve_language,
    resolve_user_profile,
    resolve_user_timezone,
    safe_delete_message,
)


_OP_TIMEOUT = get_settings().operation_timeout_seconds


def _messages_for_lang(lang: str) -> dict[str, str]:
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


async def collect_on_this_day_payloads(
    sheets_client: Any,
    sheet_id: str,
    profile: UserProfile,
) -> tuple[list[OnThisDayPayload], Any]:
    """Fetch all on-this-day data for a user.

    Returns `(payloads, today_local)`. `payloads` is empty if the user is
    under a year old, has no sheet, or simply has no historical entries.
    Raises the usual Sheets exceptions for the caller to handle.
    """

    user_tz = resolve_user_timezone(profile)
    today = datetime.now(user_tz).date()
    target_dates = compute_on_this_day_dates(today, profile.created_at)
    if not target_dates:
        return [], today

    habits_entries, dreams_entries, thoughts_entries, reflection_entries = await asyncio.wait_for(
        asyncio.gather(
            sheets_client.get_habit_entries_for_dates(sheet_id, target_dates),
            sheets_client.get_dream_entries_for_dates(sheet_id, target_dates),
            sheets_client.get_thought_entries_for_dates(sheet_id, target_dates),
            sheets_client.get_reflection_entries_for_dates(sheet_id, target_dates),
        ),
        timeout=_OP_TIMEOUT,
    )
    payloads = assemble_payloads(
        target_dates,
        habits_entries,
        dreams_entries,
        thoughts_entries,
        reflection_entries,
    )
    return payloads, today


async def on_this_day_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = _messages_for_lang(lang)

    if profile is None:
        await update.message.reply_text(msgs["sheet_not_configured"])
        return

    sheet_id = profile.sheet_id
    if not sheet_id:
        await update.message.reply_text(msgs["sheet_not_configured"])
        return

    sheets_client = get_sheets_client(context)
    if sheets_client is None:
        await update.message.reply_text(msgs["sheet_not_configured"])
        return

    progress_message = await update.message.reply_text(msgs["processing"])
    try:
        payloads, today = await collect_on_this_day_payloads(sheets_client, sheet_id, profile)
    except SheetAccessError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["sheet_permission_error"])
        return
    except ExternalTimeoutError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except asyncio.TimeoutError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except SheetWriteError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["sheet_write_error"])
        return

    await safe_delete_message(progress_message)

    if not payloads:
        await update.message.reply_text(msgs["on_this_day_empty"])
        return

    text = format_on_this_day_message(today, payloads, lang)
    try:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        safe_text = text.replace("_", "\\_")
        try:
            await update.message.reply_text(safe_text, parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            await update.message.reply_text(text)
