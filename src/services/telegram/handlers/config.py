import asyncio
import re

from telegram import Update
from telegram.ext import ContextTypes

from src.services.telegram.keyboards import build_main_menu_keyboard, build_confirmation_keyboard

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.config.settings import get_settings
from src.core.exceptions import ExternalTimeoutError, SheetAccessError, SheetWriteError
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile
from zoneinfo import ZoneInfo
from src.services.telegram.utils import resolve_language, resolve_user_profile

def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


_OP_TIMEOUT = get_settings().operation_timeout_seconds


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        context.application.bot_data.get("session_repo"),
        context.application.bot_data.get("user_repo"),
        context.application.bot_data.get("sheets_client"),
    )


async def _get_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    profile = await resolve_user_profile(update, context)
    return resolve_language(profile)


def _extract_sheet_id(text: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        return match.group(1)
    return text.strip()


def _has_extra_sheet_params(text: str) -> bool:
    """Detect if link contains query/fragment/extra path after the sheet id."""

    match = re.search(r"/spreadsheets/d/[a-zA-Z0-9-_]+(.*)$", text)
    if not match:
        return False
    tail = match.group(1)
    return bool(tail and tail not in {"/", ""})


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt the user to confirm reset of their stored settings."""

    if not update.message:
        return
    lang = await _get_lang(update, context)
    await update.message.reply_text(
        _messages_for_lang(lang)["reset_prompt"],
        reply_markup=build_confirmation_keyboard(prefix="reset", language=lang),
    )


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask user for Google Sheet link or ID."""

    if not update.effective_user or not update.message:
        return
    session_repo, user_repo, _ = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    lang = resolve_language(profile)
    sheets_client = context.application.bot_data.get("sheets_client")
    service_email = getattr(sheets_client, "service_email", None)
    is_ru = lang == "ru"

    if profile and profile.sheet_id:
        if is_ru:
            msg = "Таблица уже подключена. Хочешь заменить? Отправь новую ссылку или /cancel."
            msg += "\nТребуемый доступ: \"Общий доступ → Ограничен\" и дать редактора боту."
        else:
            msg = "Sheet already connected. Do you want to change it? Send new link or /cancel."
            msg += "\nRequired sharing: \"General access → Restricted\" and grant the bot Editor access."
        if service_email:
            if is_ru:
                msg += f"\nДай доступ редактора: {service_email}."
            else:
                msg += f"\nGrant Editor access to: {service_email}."
        await update.message.reply_text(msg)
    else:
        msg_parts = []
        if service_email:
            if is_ru:
                msg_parts.append(f"⚠️ Дай доступ редактора: {service_email}.")
            else:
                msg_parts.append(f"⚠️ Grant Editor access to: {service_email}.")
        msg_parts.append(_messages_for_lang(lang)["ask_sheet"])
        example_label = "Пример" if is_ru else "Example"
        msg_parts.append(f"{example_label}: https://docs.google.com/spreadsheets/d/1AbCDefGh1234567890")
        msg = "\n".join(msg_parts)
        await update.message.reply_text(msg)

    if session_repo:
        session = await session_repo.get(update.effective_user.id) or SessionData(user_id=update.effective_user.id)
        session.state = ConversationState.CONFIG_AWAITING_SHEET_URL
        await session_repo.save(session)


async def handle_config_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle sheet URL/ID submission. Returns True if handled."""

    if not update.effective_user or not update.message:
        return False
    lang = await _get_lang(update, context)
    sheet_text = (update.message.text or "").strip()
    if sheet_text.lower() in {"/cancel", "cancel", "отмена"}:
        session_repo, *_ = _get_repos(context)
        session = await session_repo.get(update.effective_user.id) if session_repo else None
        if session:
            session.state = ConversationState.IDLE
            await session_repo.save(session)
        await update.message.reply_text(
            _messages_for_lang(lang)["config_cancelled"],
            reply_markup=build_main_menu_keyboard(lang)
        )
        return True
    session_repo, user_repo, sheets_client = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    # Only handle sheet URL when in the correct config state
    if session is None or session.state != ConversationState.CONFIG_AWAITING_SHEET_URL:
        return False
    looks_like_sheet = bool(re.search(r"spreadsheets/d/[A-Za-z0-9-_]+", sheet_text))
    if not looks_like_sheet and "/" not in sheet_text:
        return False

    sheet_id = _extract_sheet_id(sheet_text)
    has_extra_params = _has_extra_sheet_params(sheet_text)
    cleaned_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    if user_repo:
        profile = await user_repo.get_by_telegram_id(update.effective_user.id)
        if profile is None:
            profile = UserProfile(
                telegram_user_id=update.effective_user.id,
                telegram_username=update.effective_user.username,
            )
        profile.sheet_id = sheet_id
        profile.sheet_url = cleaned_url
        profile.sheets_validated = False
        await user_repo.update(profile)

    if sheets_client:
        try:
            if update.message:
                await update.message.reply_text(_messages_for_lang(lang)["processing"])
            await asyncio.wait_for(sheets_client.ensure_tabs(sheet_id), timeout=_OP_TIMEOUT)
        except SheetAccessError:  # pragma: no cover - external dependency
            await update.message.reply_text(_messages_for_lang(lang)["sheet_permission_error"])
            return True
        except asyncio.TimeoutError:  # pragma: no cover - external dependency
            await update.message.reply_text(_messages_for_lang(lang)["external_timeout_error"])
            return True
        except ExternalTimeoutError:  # pragma: no cover - external dependency
            await update.message.reply_text(_messages_for_lang(lang)["external_timeout_error"])
            return True
        except SheetWriteError:  # pragma: no cover - external dependency
            await update.message.reply_text(_messages_for_lang(lang)["sheet_write_error"])
            return True
        if user_repo and profile:
            profile.sheets_validated = True
            await user_repo.update(profile)

    if session:
        session.state = ConversationState.IDLE
        if session_repo:
            await session_repo.save(session)

    msg = _messages_for_lang(lang)["sheet_saved"]
    if has_extra_params:
        msg += "\n" + _messages_for_lang(lang)["sheet_base_url_notice"].format(url=cleaned_url)
    await update.message.reply_text(msg)
    return True


async def handle_timezone_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle timezone input."""

    if not update.effective_user or not update.message:
        return False
    lang = await _get_lang(update, context)
    text = (update.message.text or "").strip()
    session_repo, user_repo, _ = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    
    # Handle cancel
    if text.lower() in {"/cancel", "cancel", "отмена"}:
        if session:
            session.state = ConversationState.IDLE
            if session_repo:
                await session_repo.save(session)
        await update.message.reply_text(
            _messages_for_lang(lang)["cancelled_config"],
            reply_markup=build_main_menu_keyboard(lang)
        )
        return True

    # Check state
    if session is None or session.state != ConversationState.CONFIG_TIMEZONE:
        return False

    # Validate timezone
    try:
        ZoneInfo(text)
    except Exception:
         await update.message.reply_text(_messages_for_lang(lang)["timezone_error"])
         return True

    # Save
    if user_repo:
        profile = await user_repo.get_by_telegram_id(update.effective_user.id)
        if profile:
            profile.timezone = text
            await user_repo.update(profile)

    if session_repo:
        session = await session_repo.get(update.effective_user.id)
        if session:
            session.state = ConversationState.IDLE
            await session_repo.save(session)

    await update.message.reply_text(
        _messages_for_lang(lang)["timezone_saved"].format(tz=text),
        reply_markup=build_main_menu_keyboard(lang)
    )
    return True


async def handle_reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation for wiping user data."""

    query = update.callback_query
    if not query or not query.data:
        return
    if not query.data.startswith("reset_confirm:"):
        return

    await query.answer()
    choice = query.data.split(":", 1)[1]
    user_id = (update.effective_user.id if update.effective_user else None) or (query.from_user.id if query.from_user else None)
    lang = await _get_lang(update, context)

    session_repo, user_repo, _ = _get_repos(context)
    if choice == "yes" and user_id:
        if user_repo:
            await user_repo.delete(user_id)
        if session_repo:
            await session_repo.delete(user_id)
        await query.message.reply_text(
            _messages_for_lang(lang)["reset_done"],
            reply_markup=build_main_menu_keyboard(lang),
        )
    else:
        await query.message.reply_text(
            _messages_for_lang(lang)["reset_cancelled"],
            reply_markup=build_main_menu_keyboard(lang),
        )
