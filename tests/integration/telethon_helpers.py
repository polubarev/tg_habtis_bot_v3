from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pytest

try:  # Telethon is optional; skip gracefully if not installed.
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except Exception:  # pragma: no cover - optional dependency
    TelegramClient = None  # type: ignore
    StringSession = None  # type: ignore


REQUIRED_ENV_VARS = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELETHON_SESSION", "TELEGRAM_BOT_USERNAME"]


@dataclass
class TelethonConfig:
    """Configuration for Telethon integration tests."""

    api_id: int
    api_hash: str
    session: str
    bot_username: str
    timeout: int = 25


def load_telethon_config() -> tuple[Optional[TelethonConfig], Optional[str]]:
    """Load Telethon test configuration from environment variables."""

    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        return None, f"Missing env vars for Telethon tests: {', '.join(missing)}"

    try:
        return TelethonConfig(
            api_id=int(os.environ["TELEGRAM_API_ID"]),
            api_hash=os.environ["TELEGRAM_API_HASH"],
            session=os.environ["TELETHON_SESSION"],
            bot_username=os.environ["TELEGRAM_BOT_USERNAME"],
        ), None
    except Exception as exc:
        return None, f"Invalid Telethon env configuration: {exc}"


def skip_if_telethon_missing() -> TelethonConfig:
    """Skip the test suite if Telethon env is not configured."""

    if TelegramClient is None or StringSession is None:
        pytest.skip("Telethon not installed", allow_module_level=True)

    config, error = load_telethon_config()
    if not config:
        pytest.skip(error or "Telethon config missing", allow_module_level=True)
    return config


async def build_telethon_client(config: TelethonConfig) -> TelegramClient:
    """Create and connect a Telethon client from configuration."""

    if TelegramClient is None or StringSession is None:
        pytest.skip("Telethon not installed", allow_module_level=True)

    client = TelegramClient(StringSession(config.session), config.api_id, config.api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        pytest.skip("Telethon session is not authorized", allow_module_level=True)
    return client
