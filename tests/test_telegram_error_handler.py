from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update

from src.config.constants import MESSAGES_EN
from src.config.settings import Settings
from src.services.telegram import bot as bot_module


@pytest.mark.asyncio
async def test_global_error_handler_sends_visible_feedback():
    message = SimpleNamespace(reply_text=AsyncMock())
    update = MagicMock(spec=Update)
    update.effective_message = message
    update.effective_user = SimpleNamespace(id=1)
    context = SimpleNamespace(
        error=RuntimeError("unexpected"),
        application=SimpleNamespace(bot_data={}),
    )

    await bot_module.handle_telegram_error(update, context)

    message.reply_text.assert_awaited_once_with(MESSAGES_EN["error_occurred"])


@pytest.mark.asyncio
async def test_bot_registers_global_error_handler(monkeypatch):
    app = SimpleNamespace(
        bot_data={},
        add_handler=MagicMock(),
        add_error_handler=MagicMock(),
        initialize=AsyncMock(),
    )

    class FakeBuilder:
        def token(self, token: str):
            return self

        def build(self):
            return app

    monkeypatch.setattr(bot_module, "ApplicationBuilder", FakeBuilder)
    service = bot_module.TelegramBotService(
        Settings(_env_file=None, telegram_bot_token="test-token")
    )

    await service._ensure_app()

    app.add_error_handler.assert_called_once_with(bot_module.handle_telegram_error)
