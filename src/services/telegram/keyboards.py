from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.config.constants import BUTTONS_RU, BUTTONS_EN


def build_date_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for choosing date quickly."""

    buttons = [
        [
            InlineKeyboardButton("Сегодня", callback_data="habits_date:today"),
            InlineKeyboardButton("Вчера", callback_data="habits_date:yesterday"),
        ],
        [InlineKeyboardButton("Другая дата", callback_data="habits_date:custom")],
        [InlineKeyboardButton("Отмена", callback_data="habits_cancel")],
    ]
    return InlineKeyboardMarkup(buttons)


def build_confirmation_keyboard(prefix: str = "habits") -> InlineKeyboardMarkup:
    """Confirmation keyboard for saving entry."""

    buttons = [
        [
            InlineKeyboardButton("✅ Да", callback_data=f"{prefix}_confirm:yes"),
            InlineKeyboardButton("✖ Нет", callback_data=f"{prefix}_confirm:no"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def build_main_menu_keyboard(language: str = "ru") -> ReplyKeyboardMarkup:
    """Main menu 2x2 grid + Config + Help + Cancel."""
    btns = BUTTONS_RU if language == "ru" else BUTTONS_EN
    
    keyboard = [
        [btns["habits"], btns["dream"]],
        [btns["thought"], btns["reflect"]],
        [btns["config"], btns["help"]],
        [btns["cancel"]]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_config_keyboard(language: str = "ru") -> ReplyKeyboardMarkup:
    """Config submenu."""
    btns = BUTTONS_RU if language == "ru" else BUTTONS_EN
    
    keyboard = [
        [btns["sheet_config"]],
        [btns["habits_config"], btns["reflect_config"]],
        [btns["reset"]],
        [btns["timezone"]],
        [btns["back"], btns["cancel"]]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
