from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.models.entry import ThoughtEntry
from src.models.session import ConversationState, SessionData


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


def _get_repos(context: ContextTypes.DEFAULT_TYPE):
    return (
        context.application.bot_data.get("session_repo"),
        context.application.bot_data.get("user_repo"),
        context.application.bot_data.get("sheets_client"),
    )


async def thought_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start thought flow."""

    if not update.effective_user or not update.message:
        return
    session_repo, _, _ = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None:
        session = SessionData(user_id=update.effective_user.id)
    session.state = ConversationState.THOUGHT_AWAITING_CONTENT
    await session_repo.save(session)
    await update.message.reply_text(_messages(update)["thought_prompt"])


async def handle_thought_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Handle thought submission. Returns True if handled."""

    if not update.effective_user:
        return False
    session_repo, user_repo, sheets_client = _get_repos(context)
    session = await session_repo.get(update.effective_user.id) if session_repo else None
    if session is None or session.state != ConversationState.THOUGHT_AWAITING_CONTENT:
        return False

    profile = await user_repo.get_by_telegram_id(update.effective_user.id) if user_repo else None
    sheet_id = profile.sheet_id if profile else None
    if not sheet_id:
        await update.message.reply_text(_messages(update)["sheet_not_configured"])
        session.state = ConversationState.IDLE
        if session_repo:
            await session_repo.save(session)
        return True

    entry = ThoughtEntry(
        timestamp=datetime.now(timezone.utc),
        raw_text=text,
    )
    if sheets_client:
        await sheets_client.append_thought_entry(sheet_id, entry)

    session.state = ConversationState.IDLE
    if session_repo:
        await session_repo.save(session)
    await update.message.reply_text(_messages(update)["thought_saved"])
    return True
