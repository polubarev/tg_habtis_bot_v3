## Context
- Goal: end-to-end tests that drive the Telegram bot via Telethon (real Bot API client) to validate conversation flows.
- Constraints: webhook-based bot (FastAPI + python-telegram-bot); local dev may lack public URL; CI may not allow outbound Telegram calls or storing bot credentials.
- Existing tests: only unit-level (parsers/extractors). No specs in `openspec/specs` yet.

## Goals / Non-Goals
- Goals: provide a Telethon harness usable locally/CI with opt-in credentials; cover at least `/start`, `/help`, `/config`, `/habits` happy paths; enable stubbing of LLM/STT/Sheets to make tests deterministic.
- Non-Goals: full Telegram mock server, performance testing, production load tests.

## Decisions
- Telethon client: use Bot token + (optional) user session for expectations; gate on env vars (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELETHON_TEST_USER_ID`).
- Transport: assume public webhook URL available via env (`TELEGRAM_WEBHOOK_URL`) or use local test server with a loopback Bot API server when running locally; document fallback (skip if not reachable).
- Isolation: use dedicated test chat (user ID or group) and clean up messages where possible; prefix test messages to aid cleanup.
- Determinism: stub LLM/STT/Sheets to avoid external calls; use predictable replies for assertions.
- Skips: mark tests with `@pytest.mark.integration` and skip when env/network missing.

## Risks / Trade-offs
- External dependency on Telegram availability; mitigated by skips.
- Managing credentials in CI requires secure secrets handling; documented as pre-req.
- Webhook delivery latency could cause flaky tests; use retries/timeouts in assertions.

## Open Questions
- Should we rely on a local Bot API server (docker) for CI to avoid Internet? (default: no, but can be added later).
- Which flows are highest priority beyond `/habits`? (e.g., `/dream`, `/thought`, `/reflect`).
