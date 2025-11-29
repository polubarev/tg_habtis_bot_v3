
# Habits & Diary Telegram Bot 2.0

Early scaffold based on the provided project/technical description. The goal is a modular
Telegram bot (FastAPI webhook on Cloud Run) that captures diary and habits, extracts
structured data with an LLM, and writes everything to user-managed Google Sheets.

## Getting started
1. Create and activate a Python 3.11+ virtualenv.
2. Install dependencies: `pip install -e .[dev]` or `pip install -r requirements.txt` once added.
3. Copy `.env.example` to `.env` and fill tokens/IDs (Telegram bot token, OpenRouter key, OpenAI key for Whisper, webhook secret, GCP project info).
4. Run locally: `uvicorn src.main:app --reload`.

## Next steps
- Implement real Firestore/Sessions repositories and Sheet validators.
- Flesh out Telegram conversation flows for /habits, /dream, /thought, /reflect with confirmation steps.
- Add LLM prompt templates and schema-driven extraction using LangChain + OpenRouter.
- Wire STT provider (Whisper) and media download pipeline with proper auth and storage.
- Add tests (unit + integration) per the technical description.
