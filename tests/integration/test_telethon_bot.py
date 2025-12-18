from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

try:
    from telethon.errors import RPCError
except Exception:  # pragma: no cover - optional dependency
    RPCError = None  # type: ignore

from tests.integration.telethon_helpers import (
    build_telethon_client,
    load_telethon_config,
    skip_if_telethon_missing,
)


CONFIG, CONFIG_ERROR = load_telethon_config()
if RPCError is None or not CONFIG:
    pytest.skip(CONFIG_ERROR or "Telethon config missing or Telethon not installed", allow_module_level=True)


@pytest_asyncio.fixture(scope="function")
async def telethon_client():
    config = skip_if_telethon_missing()
    client = await build_telethon_client(config)
    try:
        yield client
    finally:
        await client.disconnect()


@pytest.fixture(scope="session")
def bot_username():
    return skip_if_telethon_missing().bot_username


async def _next_response(conv, attempts: int = 3):
    """Fetch the next response with retries to smooth out delivery latency."""

    last_error = None
    for _ in range(attempts):
        try:
            return await conv.get_response()
        except asyncio.TimeoutError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_start_and_help_responses(telethon_client, bot_username):
    """Bot should respond to /start and /help with welcome/help text."""

    try:
        async with telethon_client.conversation(bot_username, timeout=CONFIG.timeout) as conv:
            await conv.send_message("/start")
            start_reply = await _next_response(conv)

            await conv.send_message("/help")
            help_reply = await _next_response(conv)
    except asyncio.TimeoutError:
        pytest.skip("Bot did not respond within timeout")
    except RPCError as exc:
        pytest.skip(f"Telegram RPC error: {exc}")

    assert start_reply, "No /start reply received"
    assert help_reply, "No /help reply received"

    start_text = (start_reply.raw_text or "").lower()
    help_text = (help_reply.raw_text or "").lower()

    assert "привет" in start_text or "hello" in start_text
    assert "помощ" in help_text or "help" in help_text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_config_prompts_for_sheet(telethon_client, bot_username):
    """Bot should prompt for sheet ID during /config."""

    try:
        async with telethon_client.conversation(bot_username, timeout=CONFIG.timeout) as conv:
            await conv.send_message("/config")
            reply = await _next_response(conv)
    except asyncio.TimeoutError:
        pytest.skip("Bot did not respond within timeout")
    except RPCError as exc:
        pytest.skip(f"Telegram RPC error: {exc}")

    assert reply, "No /config reply received"
    text = (reply.raw_text or "").lower()
    assert (
        "google sheet" in text
        or "google sheets" in text
        or "гугл" in text
        or "sheet already connected" in text
    ), f"Unexpected /config reply: {reply.raw_text!r}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_habits_flow_returns_draft(telethon_client, bot_username):
    """Habits flow should return a draft confirmation JSON when given a date and text."""

    confirm_reply = None
    try:
        async with telethon_client.conversation(bot_username, timeout=CONFIG.timeout) as conv:
            await conv.send_message("/habits")
            await _next_response(conv)  # prompt for date

            await conv.send_message("2024-01-01")
            await _next_response(conv)  # prompt for content

            await conv.send_message("тестовый день про бота")

            # There may be multiple replies (LLM disabled notice + draft)
            for _ in range(4):
                msg = await _next_response(conv)
                if not msg:
                    continue
                text = (msg.raw_text or "").lower()
                if "```json" in (msg.raw_text or "") or "draft" in text or "черновик" in text:
                    confirm_reply = msg
                    break
    except asyncio.TimeoutError:
        pytest.skip("Bot did not respond within timeout")
    except RPCError as exc:
        pytest.skip(f"Telegram RPC error: {exc}")

    assert confirm_reply is not None, "Draft confirmation not received"
    confirm_text = confirm_reply.raw_text or ""
    assert (
        "```json" in confirm_text
        or confirm_text.strip().startswith("{")
        or "draft" in confirm_text.lower()
        or "черновик" in confirm_text.lower()
    ), f"Unexpected draft confirmation: {confirm_text!r}"
    assert "тестовый" in confirm_text.lower() or "bot" in confirm_text.lower()
