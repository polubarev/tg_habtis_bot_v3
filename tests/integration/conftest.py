from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from typing import Optional

import pytest
import uvicorn

from src.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async integration tests."""

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@dataclass
class WebhookTarget:
    url: Optional[str]
    secret: str


async def _start_uvicorn_server(port: int) -> uvicorn.Server:
    """Start a uvicorn server in the background for local webhook delivery."""

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server startup
    for _ in range(20):
        if server.started:
            break
        await asyncio.sleep(0.1)
    return server


@pytest.fixture(scope="session")
def webhook_target(event_loop) -> WebhookTarget:
    """
    Provide a webhook target (URL + secret) for integration tests.

    - If TELEGRAM_WEBHOOK_URL is set, return it directly.
    - If START_TELEGRAM_WEBHOOK_SERVER=1, start a local uvicorn server for manual testing.
    - Otherwise, return a placeholder with url=None so tests can skip when needed.
    """

    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    url = os.getenv("TELEGRAM_WEBHOOK_URL")
    server: uvicorn.Server | None = None

    if not url and os.getenv("START_TELEGRAM_WEBHOOK_SERVER") == "1":
        port = int(os.getenv("TELEGRAM_TEST_WEBHOOK_PORT", "8085"))
        server = event_loop.run_until_complete(_start_uvicorn_server(port))
        url = f"http://127.0.0.1:{port}/telegram/webhook"

    target = WebhookTarget(url=url, secret=secret)
    yield target

    if server:
        server.should_exit = True
