#!/usr/bin/env python
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

from src.config.settings import Settings


def build_webhook_url(raw_url: str) -> str:
    """Ensure the webhook URL ends with /telegram/webhook."""

    trimmed = raw_url.rstrip("/")
    suffix = "/telegram/webhook"
    if trimmed.endswith(suffix):
        return trimmed
    return f"{trimmed}{suffix}"


def load_settings() -> Settings:
    """Load settings from .env at the repo root (falls back to env vars)."""

    repo_root = Path(__file__).resolve().parent.parent
    env_file = repo_root / ".env"
    if env_file.exists():
        return Settings(_env_file=env_file)
    return Settings()


async def set_webhook(
    webhook_url: str,
    bot_token: str,
    secret_token: Optional[str] = None,
) -> None:
    """Call Telegram setWebhook with optional secret token."""

    bot = Bot(token=bot_token)
    kwargs = {}
    if secret_token:
        kwargs["secret_token"] = secret_token

    await bot.set_webhook(url=webhook_url, **kwargs)


async def main() -> int:
    settings = load_settings()

    if not settings.telegram_bot_token:
        print("TELEGRAM_BOT_TOKEN is missing in .env or environment.")
        return 1
    if not settings.telegram_webhook_url:
        print("TELEGRAM_WEBHOOK_URL is missing in .env or environment.")
        return 1

    webhook_url = build_webhook_url(settings.telegram_webhook_url)

    try:
        await set_webhook(
            webhook_url=webhook_url,
            bot_token=settings.telegram_bot_token,
            secret_token=settings.telegram_webhook_secret or None,
        )
    except TelegramError as exc:
        print(f"Failed to set webhook: {exc}")
        return 1

    print(f"Webhook set to {webhook_url}")
    if settings.telegram_webhook_secret:
        print("Secret token configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
