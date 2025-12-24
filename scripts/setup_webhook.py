#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register Telegram webhook.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Use *_DEBUG values from .env (overrides DEBUG flag).",
    )
    return parser.parse_args()


def load_settings(debug_override: bool | None = None) -> Settings:
    """Load settings from .env at the repo root (falls back to env vars)."""

    env_file = repo_root / ".env"
    overrides = {}
    if debug_override is not None:
        overrides["debug"] = debug_override
    if env_file.exists():
        return Settings(_env_file=env_file, **overrides)
    return Settings(**overrides)


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
    args = _parse_args()
    settings = load_settings(debug_override=True if args.debug else None)
    debug_mode = bool(settings.debug)

    bot_token = settings.get_telegram_bot_token()
    webhook_base = settings.get_telegram_webhook_url()

    if not bot_token:
        missing_token = "TELEGRAM_BOT_TOKEN_DEBUG" if debug_mode else "TELEGRAM_BOT_TOKEN"
        print(f"{missing_token} is missing in .env or environment.")
        return 1
    if not webhook_base:
        missing_url = "TELEGRAM_WEBHOOK_URL_DEBUG" if debug_mode else "TELEGRAM_WEBHOOK_URL"
        print(f"{missing_url} is missing in .env or environment.")
        return 1

    webhook_url = build_webhook_url(webhook_base)

    try:
        await set_webhook(
            webhook_url=webhook_url,
            bot_token=bot_token,
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
