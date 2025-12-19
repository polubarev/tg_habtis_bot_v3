from telegram import Update
from telegram.constants import ParseMode
from src.services.telegram.keyboards import build_main_menu_keyboard
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands."""

    if not update.message:
        return
    
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    lang = "ru" if code.startswith("ru") else "en"
    
    keyboard = build_main_menu_keyboard(lang)
    await update.message.reply_text(
        _messages(update)["help"],
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )
