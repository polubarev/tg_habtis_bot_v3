from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome users and hint available commands."""

    if not update.message:
        return
    msgs = _messages(update)
    await update.message.reply_text(msgs["welcome"])