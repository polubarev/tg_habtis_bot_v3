## 1. Telethon harness
- [x] 1.1 Add Telethon test dependency (dev/extra) and helper to create a client from env vars (bot token, test user ID, optional API ID/hash).
- [x] 1.2 Add fixtures/utilities to spin up the FastAPI/Telegram application for tests and expose webhook URL/secret for incoming updates.

## 2. Integration tests
- [x] 2.1 Add Telethon-based integration tests for happy-path `/start` and `/help` responses.
- [x] 2.2 Add Telethon-based integration tests for `/config` and `/habits` draft confirmation (with stubbed LLM/STT and Sheets).
- [x] 2.3 Ensure tests are skipped gracefully when required env vars are missing or network is unavailable.

## 3. Validation & docs
- [x] 3.1 Document how to run Telethon integration tests locally/CI (env vars, bot setup, secrets).
- [x] 3.2 Run `openspec validate add-telethon-integration-tests --strict` and fix any issues.
