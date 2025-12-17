# Telethon Integration Tests

These tests drive the bot like a real Telegram user via Telethon. They are **opt-in** and skipped unless credentials are provided.

## Required environment
- `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` — Telegram app credentials.
- `TELETHON_SESSION` — Telethon string session for a test user account (authorized).
- `TELEGRAM_BOT_USERNAME` — Username of the bot under test (e.g., `@my_bot`).

Optional:
- `TELEGRAM_BOT_TOKEN` — Useful for managing webhooks separately but not required to run the tests.
- `TELEGRAM_WEBHOOK_URL` — If set, tests will use this webhook target (should point to your running bot).
- `START_TELEGRAM_WEBHOOK_SERVER` — Set to `1` to start a local uvicorn server for manual webhook delivery (`TELEGRAM_TEST_WEBHOOK_PORT` optional, default 8085).

## Running locally
1) Ensure your bot webhook points to a reachable URL that runs this codebase (ngrok/Cloud Run/etc.).
2) Export the env vars above.
3) Run:
```bash
pytest tests/integration/test_telethon_bot.py -m integration
```

If the bot is unreachable or credentials are missing, the suite will skip gracefully.

## Notes
- The habits flow test uses text-only input (date string + text) and expects a draft JSON confirmation; LLM/STT/Sheets may remain disabled.
- Keep a dedicated test user/bot to avoid polluting real chats.
