import asyncio
import json
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.config.settings import get_settings
from src.core.exceptions import ExternalResponseError, ExternalTimeoutError, SheetAccessError, SheetWriteError
from src.services.llm.prompts.weekly_analysis import (
    WEEKLY_ANALYSIS_SYSTEM_PROMPT_EN,
    WEEKLY_ANALYSIS_SYSTEM_PROMPT_RU,
)
from src.services.telegram.utils import (
    get_llm_client,
    get_sheets_client,
    resolve_language,
    resolve_user_profile,
    resolve_user_timezone,
    safe_delete_message,
)


_OP_TIMEOUT = get_settings().operation_timeout_seconds


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


def _weekly_prompt(lang: str) -> str:
    return WEEKLY_ANALYSIS_SYSTEM_PROMPT_RU if lang == "ru" else WEEKLY_ANALYSIS_SYSTEM_PROMPT_EN


async def week_analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    msgs = _messages_for_lang(lang)

    sheet_id = profile.sheet_id if profile else None
    if not sheet_id:
        await update.message.reply_text(msgs["sheet_not_configured"])
        return

    sheets_client = get_sheets_client(context)
    if sheets_client is None:
        await update.message.reply_text(msgs["sheet_not_configured"])
        return

    llm_client = get_llm_client(context)
    if llm_client is None or getattr(llm_client, "_model", None) is None:
        await update.message.reply_text(msgs["llm_disabled"])
        return

    user_tz = resolve_user_timezone(profile)
    today = datetime.now(user_tz).date()
    end_date = today - timedelta(days=1)
    target_dates = [end_date - timedelta(days=offset) for offset in range(6, -1, -1)]

    progress_message = await update.message.reply_text(msgs["processing"])
    try:
        habits_entries, dreams_entries, thoughts_entries, reflection_entries = await asyncio.wait_for(
            asyncio.gather(
                sheets_client.get_habit_entries_for_dates(sheet_id, target_dates),
                sheets_client.get_dream_entries_for_dates(sheet_id, target_dates),
                sheets_client.get_thought_entries_for_dates(sheet_id, target_dates),
                sheets_client.get_reflection_entries_for_dates(sheet_id, target_dates),
            ),
            timeout=_OP_TIMEOUT,
        )
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

    if len(habits_entries) < 7:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["week_analysis_not_enough"].format(count=len(habits_entries)))
        return

    cleaned_habits = []
    for entry in habits_entries:
        cleaned = {
            key: value
            for key, value in entry.items()
            if key not in {"raw_record", "timestamp"}
        }
        cleaned_habits.append(cleaned)

    cleaned_dreams = [entry for entry in dreams_entries if entry.get("record")]
    cleaned_thoughts = [entry for entry in thoughts_entries if entry.get("record")]
    cleaned_reflections = []
    for entry in reflection_entries:
        reflections_value = entry.get("reflections")
        if isinstance(reflections_value, str):
            try:
                reflections_value = json.loads(reflections_value)
            except Exception:
                pass
        cleaned_reflections.append({**entry, "reflections": reflections_value})

    payload_obj = {
        "habits": cleaned_habits,
        "dreams": cleaned_dreams,
        "thoughts": cleaned_thoughts,
        "reflections": cleaned_reflections,
    }
    payload = json.dumps(payload_obj, ensure_ascii=False, indent=2)
    date_range = f"{target_dates[0].isoformat()} — {target_dates[-1].isoformat()}"
    user_content = (
        f"Language: {lang}\n"
        f"Date range (last 7 completed days): {date_range}\n"
        "Entries (JSON with habits per day plus dreams, thoughts, reflections):\n"
        f"{payload}"
    )

    try:
        messages = [
            SystemMessage(content=_weekly_prompt(lang)),
            HumanMessage(content=user_content),
        ]
        result = await asyncio.wait_for(llm_client.model.ainvoke(messages), timeout=_OP_TIMEOUT)
    except asyncio.TimeoutError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except ExternalTimeoutError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_timeout_error"])
        return
    except ExternalResponseError:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_response_error"])
        return
    except Exception:
        await safe_delete_message(progress_message)
        await update.message.reply_text(msgs["external_response_error"])
        return

    await safe_delete_message(progress_message)
    content = getattr(result, "content", None) or str(result)
    message = f"{msgs['week_analysis_title']}\n\n{content}"
    try:
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        safe_message = message.replace("_", "\\_")
        try:
            await update.message.reply_text(safe_message, parse_mode=ParseMode.MARKDOWN)
        except BadRequest:
            await update.message.reply_text(message)
