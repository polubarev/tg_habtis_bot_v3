# Project Context

## Purpose
Habits & Diary Telegram Bot that captures daily diaries, habits, dreams, thoughts, and reflection answers (text or voice), extracts structured data with an LLM, and writes everything to a user-configured Google Sheet; optimized for Russian but multilingual, designed for Cloud Run webhook deployments with low idle cost.

## Tech Stack
- Python 3.11, FastAPI webhook (`/telegram/webhook`, `/health`), uvicorn for local dev.
- `python-telegram-bot` 20.x in webhook mode for command routing and keyboards.
- LangChain + OpenRouter (default `anthropic/claude-3-5-sonnet`) for structured extraction; Pydantic v2 schemas drive outputs.
- OpenAI Whisper API (`whisper-1`) for speech-to-text; optional if key absent.
- Google Sheets via `gspread`/`google-api-python-client`; Firestore for users/sessions; fall back to in-memory stores when GCP is unavailable.
- Structlog-based JSON logging (console in debug), tenacity for retries, httpx for HTTP calls.
- Dockerized and intended for Google Cloud Run (env-configured via `.env` or Secret Manager).

## Project Conventions

### Code Style
- PEP 8 with full type hints (Python 3.11 union syntax); Ruff enforced, line length 100.
- Prefer async IO (FastAPI, python-telegram-bot) and small, single-purpose modules.
- Use Pydantic models for settings and domain data; structured logging via `structlog`.
- Keep user-facing text localized (RU/EN dictionaries in `src/config/constants.py`); avoid hardcoding strings elsewhere.

### Architecture Patterns
- FastAPI entrypoint → cached `TelegramBotService` → python-telegram-bot handlers per command (`/habits`, `/dream`, `/thought`, `/reflect`, `/config`, `/help`, etc.).
- Service layers: transcription (Whisper), LLM extraction (LangChain), storage (Sheets + validators, Firestore repos) with graceful degradation to in-memory implementations.
- Repository-style interfaces for user/session data; sheet helpers per tab; prompt builders and schema builders for LLM structured output.
- Configuration through `.env`/env vars (`Settings` in `src/config/settings.py`); structured constants for defaults (habit schema, buttons/messages, sheet column order).

### Testing Strategy
- Pytest + pytest-asyncio; fixtures for sample users/sessions and mocked repos/LLM/STT.
- Unit focus on parsers/formatters/extractors (e.g., date parsing, habit schema builder); mock external services.
- Integration tests marked `@pytest.mark.integration` for real LLM/Sheets/Firestore (skipped without keys); plan e2e conversation flow tests with Telegram-like updates.
- Keep tests deterministic; gate networked tests behind env keys and markers.

### Git Workflow
- Use short-lived feature branches and small PRs; commit in imperative style.
- Follow OpenSpec: create change proposals for new capabilities, architecture, or perf/security shifts; bug fixes/docs/config tweaks can be direct.
- Run `openspec validate --strict` on proposals before implementation; align commits with approved tasks.

## Domain Context
- Commands: `/start` onboarding, `/config` to link Google Sheet, `/habits` diary + habit extraction, `/dream`, `/thought`, `/reflect` (custom questions), `/habits_config` and `/reflect_config` for field/question management, `/help`.
- Per-user habit schema (JSON-like) drives LLM extraction; default schema keeps `raw_record` + optional `diary`, with user-editable fields. Reflection questions are configurable with stable IDs.
- Data goes to user-managed Google Sheets tabs: Habits (timestamp/date/raw_record/diary + habit fields), Dreams, Thoughts, Reflections. Users must share the sheet with the service account.
- Voice is transcribed to `raw_record` (or `record`), preserved verbatim; bot shows a JSON preview for confirmation before writing.
- Primary audience Russian speakers; messages/buttons localized (RU/EN); natural-language date parsing supports RU/EN keywords.

## Important Constraints
- Preserve `raw_record` as ground truth; `diary` is optional/hallucination-prone and can be omitted when LLM unavailable.
- Whisper/LLM/Firestore are optional; flows must degrade gracefully to text-only/in-memory operation with clear user messaging.
- Validate Telegram webhook requests with a shared secret; rate limiting defaults to 30 req/min per user.
- Never commit service account JSON; require users to share their Sheet with the service account email.
- Cloud Run, Secret Manager, and Firestore usage should be controlled by env vars; prefer idempotent sheet/tab creation and minimal permissions.

## External Dependencies
- Telegram Bot API (webhook mode).
- OpenRouter LLM API (structured extraction) and LangChain.
- OpenAI Whisper API for transcription.
- Google Sheets API (via `gspread`/`google-api-python-client`), Google Auth/OAuth libraries.
- Google Firestore (user/session persistence) and Google Secret Manager for secrets; both optional with in-memory fallbacks.
- Python libs: structlog, tenacity, httpx, pydantic/pydantic-settings.
