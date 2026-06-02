from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.error import NetworkError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.config.settings import Settings
from src.core.rate_limit import SlidingWindowRateLimiter
from src.models.usage_event import UsageEvent
from src.services.telegram.handlers.habits import (
    habits_command,
    handle_habits_confirm,
    handle_habits_date_callback,
    handle_habits_existing_choice,
)
from src.services.telegram.handlers.dream import dream_command, handle_dream_confirm
from src.services.telegram.handlers.thought import thought_command, handle_thought_confirm
from src.services.telegram.handlers.reflect import reflect_command, handle_reflect_confirm
from src.services.telegram.handlers.help import help_command
from src.services.telegram.handlers.on_this_day import on_this_day_command
from src.services.telegram.handlers.admin import admin_command, handle_admin_broadcast_callback
from src.services.telegram.handlers.config import config_command, handle_reset_confirm
from src.services.telegram.handlers.config import handle_reminders_menu_callback, handle_smart_nudges_callback
from src.services.telegram.handlers.language import handle_language_select
from src.services.telegram.handlers.router import route_text, route_voice
from src.services.telegram.handlers.habits_config import (
    habits_config_command,
    handle_habits_config_callback,
    handle_habit_edit_attr_callback,
    handle_habit_field_callback,
    handle_habit_list_mode_callback,
    handle_habit_type_callback,
)
from src.services.telegram.handlers.questions import (
    handle_question_field_callback,
    handle_questions_callback,
    questions_command,
)
from src.services.telegram.deps import DependencyProvider
from src.services.telegram.handlers.start import start_command

logger = logging.getLogger(__name__)


def _extract_update_user_id(update_payload: dict[str, Any]) -> int | None:
    """Return the Telegram user id for update types that carry one."""

    for key in (
        "message",
        "edited_message",
        "callback_query",
        "inline_query",
        "chosen_inline_result",
        "shipping_query",
        "pre_checkout_query",
        "poll_answer",
        "my_chat_member",
        "chat_member",
        "chat_join_request",
    ):
        value = update_payload.get(key)
        if not isinstance(value, dict):
            continue
        user = value.get("from") or value.get("user")
        if isinstance(user, dict) and isinstance(user.get("id"), int):
            return user["id"]
    return None


class TelegramBotService:
    """Wraps python-telegram-bot Application lifecycle for FastAPI webhooks."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.app: Application | None = None
        self.deps = DependencyProvider(settings)
        self._rate_limiter = SlidingWindowRateLimiter(
            settings.rate_limit_requests_per_minute,
            window_seconds=60,
        )

    async def _ensure_app(self) -> None:
        if self.app:
            if not getattr(self.app, "_initialized", False):
                try:
                    await self.app.initialize()
                except NetworkError as exc:
                    logger.warning("Telegram init failed (network)", error=str(exc))
                    return
                except Exception:
                    logger.exception("Telegram init failed")
                    return
            return
        token = self.settings.get_telegram_bot_token()
        if not token:
            logger.warning("Telegram bot token not configured; update handling is disabled.")
            return
        self.app = (
            ApplicationBuilder()
            .token(token)
            .build()
        )
        # share services with handlers via bot_data
        self.app.bot_data["deps"] = self.deps
        self.app.add_handler(CommandHandler("start", start_command))
        self.app.add_handler(CommandHandler("habits", habits_command))
        self.app.add_handler(CommandHandler("dream", dream_command))
        self.app.add_handler(CommandHandler("thought", thought_command))
        self.app.add_handler(CommandHandler("reflect", reflect_command))
        self.app.add_handler(CommandHandler("config", config_command))
        self.app.add_handler(CommandHandler("habits_config", habits_config_command))
        self.app.add_handler(CommandHandler("reflect_config", questions_command))
        self.app.add_handler(CommandHandler("on_this_day", on_this_day_command))
        self.app.add_handler(CommandHandler("help", help_command))
        self.app.add_handler(CommandHandler("admin", admin_command))
        self.app.add_handler(
            CallbackQueryHandler(handle_habits_date_callback, pattern="^habits_date:|^habits_cancel$")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_habits_existing_choice, pattern="^habits_existing:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_habits_confirm, pattern="^habits_confirm:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_habits_config_callback, pattern="^habit_cfg:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_habit_field_callback, pattern="^habit_field:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_habit_edit_attr_callback, pattern="^habit_edit_attr:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_habit_type_callback, pattern="^habit_type:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_habit_list_mode_callback, pattern="^habit_list_mode:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_questions_callback, pattern="^q_cfg:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_question_field_callback, pattern="^question_field:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_reset_confirm, pattern="^reset_confirm:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_reminders_menu_callback, pattern="^reminders_menu:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_smart_nudges_callback, pattern="^smart_nudges:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_dream_confirm, pattern="^dream_confirm:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_thought_confirm, pattern="^thought_confirm:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_reflect_confirm, pattern="^reflect_confirm:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_language_select, pattern="^lang_select:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_admin_broadcast_callback, pattern="^admin_broadcast:")
        )
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, route_text)
        )
        self.app.add_handler(
            MessageHandler(filters.VOICE, route_voice)
        )
        try:
            await self.app.initialize()
        except NetworkError as exc:
            logger.warning("Telegram init failed (network)", error=str(exc))
            self.app = None
            return
        except Exception:
            logger.exception("Telegram init failed")
            self.app = None
            return

    async def handle_update(self, update_payload: dict[str, Any]) -> None:
        user_id = _extract_update_user_id(update_payload)
        if user_id is not None and not self._rate_limiter.allow(user_id):
            logger.warning("Telegram update rate limited for user %s", user_id)
            return

        await self._ensure_app()
        if not self.app:
            logger.debug("No Telegram application initialized; skipping update.")
            return
        update = Update.de_json(update_payload, self.app.bot)
        await self._record_command_usage(update)
        await self.app.process_update(update)

    async def _record_command_usage(self, update: Update) -> None:
        if not update.effective_user or not update.message or not update.message.text:
            return
        text = update.message.text.strip()
        if not text.startswith("/"):
            return
        command = text.split()[0].split("@", 1)[0].lstrip("/").lower()
        if not command:
            return
        try:
            await self.deps.usage_event_repo().create(
                UsageEvent.create(
                    "command.used",
                    user_id=update.effective_user.id,
                    feature=command,
                )
            )
        except Exception:
            logger.debug("Failed to record command usage", exc_info=True)


async def build_bot_application(settings: Settings) -> Application | None:
    service = TelegramBotService(settings)
    await service._ensure_app()
    return service.app
