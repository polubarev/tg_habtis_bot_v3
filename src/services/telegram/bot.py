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
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config.settings import Settings
from src.services.telegram.handlers.habits import (
    habits_command,
    handle_habits_confirm,
    handle_habits_date_callback,
)
from src.services.telegram.handlers.dream import dream_command, handle_dream_confirm
from src.services.telegram.handlers.thought import thought_command, handle_thought_confirm
from src.services.telegram.handlers.reflect import reflect_command, handle_reflect_confirm
from src.services.telegram.handlers.help import help_command
from src.services.telegram.handlers.config import config_command, handle_reset_confirm
from src.services.telegram.handlers.language import handle_language_select
from src.services.telegram.handlers.router import route_text, route_voice
from src.services.telegram.handlers.habits_config import (
    habits_config_command,
    handle_habits_config_callback,
    handle_habit_edit_attr_callback,
    handle_habit_field_callback,
    handle_habit_type_callback,
)
from src.services.telegram.handlers.questions import questions_command, handle_questions_callback
from src.services.telegram.deps import DependencyProvider
from src.services.telegram.handlers.start import start_command

logger = logging.getLogger(__name__)


class TelegramBotService:
    """Wraps python-telegram-bot Application lifecycle for FastAPI webhooks."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.app: Application | None = None
        self.deps = DependencyProvider(settings)

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
        self.app.add_handler(CommandHandler("help", help_command))
        self.app.add_handler(
            CallbackQueryHandler(handle_habits_date_callback, pattern="^habits_date:|^habits_cancel$")
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
            CallbackQueryHandler(handle_questions_callback, pattern="^q_cfg:")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_reset_confirm, pattern="^reset_confirm:")
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
        await self._ensure_app()
        if not self.app:
            logger.debug("No Telegram application initialized; skipping update.")
            return
        update = Update.de_json(update_payload, self.app.bot)
        await self.app.process_update(update)


async def build_bot_application(settings: Settings) -> Application | None:
    service = TelegramBotService(settings)
    await service._ensure_app()
    return service.app
