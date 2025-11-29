import re

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.models.session import ConversationState, SessionData
from src.models.user import UserProfile

def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        context.application.bot_data.get("session_repo"),
        context.application.bot_data.get("user_repo"),
        context.application.bot_data.get("sheets_client"),
    )


def _extract_sheet_id(text: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        return match.group(1)
    return text.strip()


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask user for Google Sheet link or ID."""

    if not update.effective_user or not update.message:
        return
    session_repo, user_repo, _ = _get_repos(context)
    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    sheets_client = context.application.bot_data.get("sheets_client")
    service_email = getattr(sheets_client, "service_email", None)

    if profile and profile.sheet_id:
        msg = "Sheet already connected. Do you want to change it? Send new link or /cancel."
        if service_email:
            msg += f"\n⚠️ Share the sheet with {service_email} (Editor) if not already."
        await update.message.reply_text(msg)
    else:
        msg = (
            _messages(update)["ask_sheet"]
            + "\nПример: https://docs.google.com/spreadsheets/d/1AbCDefGh1234567890"
        )
        if service_email:
            msg += f"\n⚠️ Перед этим дай доступ Editor: {service_email}"
        await update.message.reply_text(msg)

    if session_repo:
        session = await session_repo.get(update.effective_user.id) or SessionData(user_id=update.effective_user.id)
        session.state = ConversationState.CONFIG_AWAITING_SHEET_URL
        await session_repo.save(session)


async def handle_config_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle sheet URL/ID submission. Returns True if handled."""

    if not update.effective_user or not update.message:
        return False
    sheet_text = (update.message.text or "").strip()
    if sheet_text.lower() in {"/cancel", "cancel", "отмена"}:
        session_repo, *_ = _get_repos(context)
        session = await session_repo.get(update.effective_user.id) if session_repo else None
        if session:
            session.state = ConversationState.IDLE
            await session_repo.save(session)
        await update.message.reply_text(_messages(update)["config_cancelled"])
        return True
    session_repo, user_repo, sheets_client = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    looks_like_sheet = bool(re.search(r"spreadsheets/d/[A-Za-z0-9-_]+", sheet_text))
    if session is None or session.state != ConversationState.CONFIG_AWAITING_SHEET_URL:
        if not looks_like_sheet and "/" not in sheet_text:
            return False
        session = SessionData(user_id=update.effective_user.id)
        session.state = ConversationState.CONFIG_AWAITING_SHEET_URL

    sheet_id = _extract_sheet_id(sheet_text)

    if user_repo:
        profile = await user_repo.get_by_telegram_id(update.effective_user.id)
        if profile is None:
            profile = UserProfile(
                telegram_user_id=update.effective_user.id,
                telegram_username=update.effective_user.username,
            )
        profile.sheet_id = sheet_id
        profile.sheet_url = sheet_text
        profile.sheets_validated = True
        await user_repo.update(profile)

    if sheets_client:
        try:
            await sheets_client.ensure_tabs(sheet_id)
        except Exception as exc:  # pragma: no cover - external dependency
            msg = str(exc)
            service_email = getattr(sheets_client, "service_email", "")
            if "permission" in msg.lower():
                await update.message.reply_text(
                    f"Нет доступа к таблице. Поделись ей с {service_email} (Editor) и попробуй снова."
                )
                return True
            raise

    session.state = ConversationState.IDLE
    if session_repo:
        await session_repo.save(session)

    await update.message.reply_text(_messages(update)["sheet_saved"])
    return True
