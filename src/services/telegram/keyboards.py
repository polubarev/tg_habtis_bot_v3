from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_date_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for choosing date quickly."""

    buttons = [
        [
            InlineKeyboardButton("Сегодня", callback_data="habits_date:today"),
            InlineKeyboardButton("Вчера", callback_data="habits_date:yesterday"),
        ],
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
