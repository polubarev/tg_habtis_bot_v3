from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.config.constants import BUTTONS_RU, BUTTONS_EN, INLINE_BUTTONS_RU, INLINE_BUTTONS_EN


def build_date_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    """Inline keyboard for choosing date quickly."""

    btns = INLINE_BUTTONS_RU if language == "ru" else INLINE_BUTTONS_EN
    buttons = [
        [
            InlineKeyboardButton(btns["today"], callback_data="habits_date:today"),
            InlineKeyboardButton(btns["yesterday"], callback_data="habits_date:yesterday"),
        ],
        [InlineKeyboardButton(btns["custom_date"], callback_data="habits_date:custom")],
        [InlineKeyboardButton(btns["cancel"], callback_data="habits_cancel")],
    ]
    return InlineKeyboardMarkup(buttons)


def build_confirmation_keyboard(prefix: str = "habits", language: str = "en") -> InlineKeyboardMarkup:
    """Confirmation keyboard for saving entry."""

    btns = INLINE_BUTTONS_RU if language == "ru" else INLINE_BUTTONS_EN
    buttons = [
        [
            InlineKeyboardButton(btns["confirm_yes"], callback_data=f"{prefix}_confirm:yes"),
            InlineKeyboardButton(btns["confirm_no"], callback_data=f"{prefix}_confirm:no"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def build_main_menu_keyboard(language: str = "en") -> ReplyKeyboardMarkup:
    """Main menu 2x2 grid + Config + Help + Cancel."""
    btns = BUTTONS_RU if language == "ru" else BUTTONS_EN
    
    keyboard = [
        [btns["habits"], btns["dream"]],
        [btns["thought"], btns["reflect"]],
        [btns["config"], btns["help"]],
        [btns["cancel"]]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_config_keyboard(language: str = "en") -> ReplyKeyboardMarkup:
    """Config submenu."""
    btns = BUTTONS_RU if language == "ru" else BUTTONS_EN
    
    keyboard = [
        [btns["sheet_config"]],
        [btns["habits_config"], btns["reflect_config"]],
        [btns["reminders"]],
        [btns["language"], btns["timezone"]],
        [btns["reset"]],
        [btns["back"], btns["cancel"]]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_language_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for selecting language."""

    buttons = [
        [
            InlineKeyboardButton(INLINE_BUTTONS_EN["language_en"], callback_data="lang_select:en"),
            InlineKeyboardButton(INLINE_BUTTONS_RU["language_ru"], callback_data="lang_select:ru"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def build_habit_type_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    """Inline keyboard for selecting habit field type."""

    btns = INLINE_BUTTONS_RU if language == "ru" else INLINE_BUTTONS_EN
    buttons = [
        [
            InlineKeyboardButton(btns["habit_type_string"], callback_data="habit_type:string"),
            InlineKeyboardButton(btns["habit_type_int"], callback_data="habit_type:int"),
        ],
        [
            InlineKeyboardButton(btns["habit_type_float"], callback_data="habit_type:float"),
            InlineKeyboardButton(btns["habit_type_bool"], callback_data="habit_type:bool"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def build_habit_fields_keyboard(
    fields: list[str],
    action: str,
    language: str = "en",
    per_row: int = 2,
) -> InlineKeyboardMarkup:
    """Inline keyboard for selecting a habit field to edit/remove."""

    btns = INLINE_BUTTONS_RU if language == "ru" else INLINE_BUTTONS_EN
    buttons = []
    row = []
    for name in fields:
        row.append(InlineKeyboardButton(name, callback_data=f"habit_field:{action}:{name}"))
        if len(row) >= per_row:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(btns["habit_cancel"], callback_data="habit_cfg:cancel")])
    return InlineKeyboardMarkup(buttons)


def build_habit_edit_attr_keyboard(language: str = "en") -> InlineKeyboardMarkup:
    """Inline keyboard for selecting which habit field attribute to edit."""

    btns = INLINE_BUTTONS_RU if language == "ru" else INLINE_BUTTONS_EN
    buttons = [
        [
            InlineKeyboardButton(btns["habit_edit_name"], callback_data="habit_edit_attr:name"),
            InlineKeyboardButton(btns["habit_edit_description"], callback_data="habit_edit_attr:description"),
        ],
        [
            InlineKeyboardButton(btns["habit_edit_type"], callback_data="habit_edit_attr:type"),
            InlineKeyboardButton(btns["habit_edit_min"], callback_data="habit_edit_attr:min"),
            InlineKeyboardButton(btns["habit_edit_max"], callback_data="habit_edit_attr:max"),
        ],
        [InlineKeyboardButton(btns["habit_cancel"], callback_data="habit_cfg:cancel")],
    ]
    return InlineKeyboardMarkup(buttons)
