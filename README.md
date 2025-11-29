
# Habits & Diary Telegram Bot 2.0

Early scaffold based on the provided project/technical description. The goal is a modular
Telegram bot (FastAPI webhook on Cloud Run) that captures diary and habits, extracts
structured data with an LLM, and writes everything to user-managed Google Sheets.

## Getting started
1. Create and activate a Python 3.11+ virtualenv.
2. Install dependencies: `pip install -e .[dev]` or `pip install -r requirements.txt` once added.
3. Copy `.env.example` to `.env` and fill tokens/IDs (Telegram bot token, OpenRouter key, OpenAI key for Whisper, webhook secret, GCP project info).
4. Run locally: `uvicorn src.main:app --reload`.

## Google Sheets setup (local/dev)
1) Create a Service Account in your GCP project, generate a JSON key, and **do not commit it**. Store it outside the repo or under `src/secrets/` (ignored by git).
2) Set `google_credentials_path` in `.env` to the JSON location, e.g. `google_credentials_path=~/.config/habits-bot/service_account.json` or `google_credentials_path=src/secrets/sa.json`.
3) Share your target Google Sheet with the service account email (from the JSON) with **Editor** access.
4) In Telegram, run `/config` and paste the Sheet link/ID. If sharing is missing, the bot will prompt you to grant access.

## Persistence (Firestore)
- Session/user state can persist across restarts if Firestore is available. Set `gcp_project_id` in `.env` and `google_credentials_path` to a service account with Firestore access. If Firestore API is disabled or unreachable, the bot automatically falls back to in-memory stores (state resets on restarts).
- Collections used: `users`, `sessions` (see `src/config/settings.py` for names).

## Commands
- `/start` — welcome, shows keyboard
- `/config` — set/change Google Sheet (prompts to share with service account)
- `/habits` — diary + habits flow
- `/dream` — dream log
- `/thought` — quick note
- `/reflect` — answer custom questions
- `/habits_config` — add/remove/reset habit fields
- `/reflect_config` — manage reflection questions
- `/help` — help text + keyboard

## Next steps
- Implement real Firestore/Sessions repositories and Sheet validators.
- Flesh out Telegram conversation flows for /habits, /dream, /thought, /reflect with confirmation steps.
- Add LLM prompt templates and schema-driven extraction using LangChain + OpenRouter.
- Wire STT provider (Whisper) and media download pipeline with proper auth and storage.
- Add tests (unit + integration) per the technical description.
