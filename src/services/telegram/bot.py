from __future__ import annotations

import logging
from typing import Any

from telegram import Update
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
from src.services.storage.firestore.session_repo import SessionRepository
from src.services.telegram.handlers.habits import (
    habits_command,
    handle_habits_confirm,
    handle_habits_date_callback,
    handle_habits_text,
)
from src.services.telegram.handlers.start import start_command

logger = logging.getLogger(__name__)


class TelegramBotService:
    """Wraps python-telegram-bot Application lifecycle for FastAPI webhooks."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.app: Application | None = None
        self.session_repo = SessionRepository()

    async def _ensure_app(self) -> None:
        if self.app:
            return
        if not self.settings.telegram_bot_token:
            logger.warning("Telegram bot token not configured; update handling is disabled.")
            return
        self.app = (
            ApplicationBuilder()
            .token(self.settings.telegram_bot_token)
            .build()
        )
        # share services with handlers via bot_data
        self.app.bot_data["session_repo"] = self.session_repo
        self.app.add_handler(CommandHandler("start", start_command))
        self.app.add_handler(CommandHandler("habits", habits_command))
        self.app.add_handler(
            CallbackQueryHandler(handle_habits_date_callback, pattern="^habits_date:|^habits_cancel$")
        )
        self.app.add_handler(
            CallbackQueryHandler(handle_habits_confirm, pattern="^habits_confirm:")
        )
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_habits_text)
        )
        await self.app.initialize()

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
