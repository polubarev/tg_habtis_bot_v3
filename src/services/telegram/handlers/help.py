from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config.constants import MESSAGES_EN, MESSAGES_RU
from src.services.telegram.keyboards import build_main_menu_keyboard
from src.services.telegram.utils import resolve_language, resolve_user_profile


def _messages_for_lang(lang: str):
    return MESSAGES_RU if lang == "ru" else MESSAGES_EN


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands."""

    if not update.message:
        return

    profile = await resolve_user_profile(update, context)
    lang = resolve_language(profile)
    keyboard = build_main_menu_keyboard(lang)
    await update.message.reply_text(
        _messages_for_lang(lang)["help"],
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )
