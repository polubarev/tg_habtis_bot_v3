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
from src.services.storage.firestore.session_repo import SessionRepository
from src.services.telegram.handlers.habits import (
    habits_command,
    handle_habits_confirm,
    handle_habits_date_callback,
)
from src.services.telegram.handlers.start import start_command
from src.services.telegram.handlers.dream import dream_command, handle_dream_confirm
from src.services.telegram.handlers.thought import thought_command, handle_thought_confirm
from src.services.telegram.handlers.reflect import reflect_command, handle_reflect_confirm
from src.services.telegram.handlers.help import help_command
from src.services.telegram.handlers.config import config_command, handle_reset_confirm
from src.services.telegram.handlers.router import route_text, route_voice
from src.services.telegram.handlers.habits_config import habits_config_command, handle_habits_config_callback
from src.services.telegram.handlers.questions import questions_command, handle_questions_callback
from src.services.storage.firestore.user_repo import UserRepository
from src.services.storage.sheets.client import SheetsClient
from src.services.llm.client import LLMClient
from src.services.transcription.whisper import WhisperClient
from src.services.telegram.handlers.start import start_command
from src.services.storage.firestore.client import FirestoreClient

logger = logging.getLogger(__name__)


class TelegramBotService:
    """Wraps python-telegram-bot Application lifecycle for FastAPI webhooks."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.app: Application | None = None
        self.firestore_client = FirestoreClient(settings.google_credentials_path, settings.gcp_project_id)
        self.session_repo = SessionRepository(self.firestore_client)
        self.user_repo = UserRepository(self.firestore_client)
        self.sheets_client = SheetsClient(settings.google_credentials_path)
        try:
            self.llm_client = LLMClient()
        except Exception:
            self.llm_client = None
        try:
            self.whisper_client = WhisperClient()
        except Exception:
            self.whisper_client = None

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
        self.app.bot_data["user_repo"] = self.user_repo
        self.app.bot_data["sheets_client"] = self.sheets_client
        self.app.bot_data["llm_client"] = self.llm_client
        self.app.bot_data["whisper_client"] = self.whisper_client
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
