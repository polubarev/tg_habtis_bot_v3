from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.config.constants import DEFAULT_REFLECTION_QUESTIONS, MESSAGES_EN, MESSAGES_RU
from src.models.user import CustomQuestion, UserProfile
from src.models.habit import HabitSchema


def _get_user_repo(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("user_repo")


def _messages(update: Update):
    code = (update.effective_user.language_code or "").lower() if update.effective_user else ""
    return MESSAGES_RU if code.startswith("ru") else MESSAGES_EN


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome users and hint available commands."""

    if not update.message:
        return
    msgs = _messages(update)

    user_repo = _get_user_repo(context)
    sheet_missing = True
    if user_repo and update.effective_user:
        profile = await user_repo.get_by_telegram_id(update.effective_user.id)
        if profile is None:
            profile = UserProfile(
                telegram_user_id=update.effective_user.id,
                telegram_username=update.effective_user.username,
                habit_schema=HabitSchema(fields={}),  # start empty; user config adds fields
                custom_questions=[
                    CustomQuestion(**q, language="ru") for q in DEFAULT_REFLECTION_QUESTIONS
                ],
                onboarding_completed=True,
            )
            await user_repo.create(profile)
        sheet_missing = not bool(profile.sheet_id)

    keyboard_rows = [
        ["/habits", "/config"],
        ["/dream", "/thought"],
        ["/reflect", "/reflect_config"],
        ["/habits_config", "/help"],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard_rows, resize_keyboard=True)
    await update.message.reply_text(msgs["welcome"], reply_markup=keyboard)
    if sheet_missing:
        await update.message.reply_text(msgs["sheet_reminder"])
