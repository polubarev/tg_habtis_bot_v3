
# Habits & Diary Telegram Bot 2.0

Early scaffold based on the provided project/technical description. The goal is a modular
Telegram bot (FastAPI webhook on Cloud Run) that captures diary and habits, extracts
structured data with an LLM, and writes everything to user-managed Google Sheets.

## Capabilities
- Diary + habits logging with LLM extraction into Google Sheets.
- Dream, thought, and reflection logging (reflection answers are parsed from a single reply).
- Weekly analysis: LLM summary over the last 7 completed days (habits, dreams, thoughts, reflections).
- Voice messages: optional Whisper-based transcription for voice input.
- Configurable habit fields and reflection questions.
- Multi-language interface (RU/EN) with per-user settings.
- User feedback capture.
- Timezone and reminder scheduling (Cloud Tasks): daily reminder + smart nudges (conditional).

## Getting started
1. Create and activate a Python 3.11+ virtualenv.
2. Install dependencies: `pip install -e '.[dev]'` or `pip install -r requirements.txt` once added.
3. Copy `.env.example` to `.env` and fill tokens/IDs (Telegram bot token, OpenRouter key, OpenAI key for Whisper, webhook secret, GCP project info).
4. Run locally: `uvicorn src.main:app --reload --port 8001`.

## Set Telegram webhook
- Fill `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_URL` (base service URL), and optionally `TELEGRAM_WEBHOOK_SECRET` in `.env`.
- Run `python scripts/setup_webhook.py` to register the webhook; the script appends `/telegram/webhook` to the base URL automatically.

## Deploy to Cloud Run
Deployment is handled by `scripts/deploy_cloud_run.sh`. Run it from Git Bash, WSL, Linux, macOS, or Google Cloud Shell.
Shell scripts are tracked with LF line endings via `.gitattributes`, so the same checkout works from macOS and WSL.

1. Install and authenticate the Google Cloud CLI:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project "$GCP_PROJECT_ID"
   ```

2. Enable required APIs:
   ```bash
   gcloud services enable \
     run.googleapis.com \
     artifactregistry.googleapis.com \
     cloudbuild.googleapis.com \
     secretmanager.googleapis.com \
     firestore.googleapis.com \
     cloudtasks.googleapis.com \
     sheets.googleapis.com
   ```

3. Create the Artifact Registry repo once:
   ```bash
   gcloud artifacts repositories create habits-bot \
     --repository-format=docker \
     --location="$GCP_REGION"
   ```

4. Create the runtime service account once:
   ```bash
   gcloud iam service-accounts create tg-habits-bot \
     --display-name="Telegram Habits Bot"

   gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
     --member="serviceAccount:tg-habits-bot@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/datastore.user"

   gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
     --member="serviceAccount:tg-habits-bot@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/cloudtasks.enqueuer"

   gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
     --member="serviceAccount:tg-habits-bot@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

5. Copy `.env.example` to `.env` and set at least:
   ```dotenv
   GCP_PROJECT_ID=your-project-id
   GCP_REGION=europe-west1
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_WEBHOOK_SECRET=...
   OPENROUTER_API_KEY=...
   OPENAI_API_KEY=...
   SERVICE_NAME=habits-diary-bot
   REPO=habits-bot
   BUILD_STRATEGY=cloud
   SET_TELEGRAM_WEBHOOK=true
   ```

6. Recommended: create Secret Manager secrets for sensitive values. Secret names must exactly match the env var names:
   ```bash
   printf '%s' "$TELEGRAM_BOT_TOKEN" | gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=-
   printf '%s' "$TELEGRAM_WEBHOOK_SECRET" | gcloud secrets create TELEGRAM_WEBHOOK_SECRET --data-file=-
   printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets create OPENROUTER_API_KEY --data-file=-
   printf '%s' "$OPENAI_API_KEY" | gcloud secrets create OPENAI_API_KEY --data-file=-
   ```

   For a quick test without Secret Manager, set `USE_SECRET_MANAGER=false` in `.env`; this passes secrets as Cloud Run env vars.

7. Deploy:
   ```bash
   bash scripts/deploy_cloud_run.sh
   ```

The script builds the container, deploys `src.main:app` to Cloud Run on port `8080`, prints the service URL, and if `SET_TELEGRAM_WEBHOOK=true` registers Telegram to `https://SERVICE_URL/telegram/webhook`.
For a custom Telegram webhook base URL, set `TELEGRAM_SET_WEBHOOK_URL`; otherwise leave it empty so the script uses the deployed Cloud Run service URL automatically.

After deploy, check:
```bash
curl "$SERVICE_URL/health"
```

If webhook registration fails with HTTP 401, the bot token used by the deploy script is invalid. With `USE_SECRET_MANAGER=true`, the script reads Secret Manager secret `TELEGRAM_BOT_TOKEN` for the `setWebhook` call when that secret exists; otherwise it uses local `TELEGRAM_BOT_TOKEN`.

For Google Sheets writes in production, share each target spreadsheet with the runtime service account email, usually `tg-habits-bot@GCP_PROJECT_ID.iam.gserviceaccount.com`, with Editor access.

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

## Menu actions (main/config keyboard)
- Week analysis — weekly LLM summary from the last 7 days
- Language — switch interface language
- Feedback — send feedback to maintainers
- Timezone — set timezone used for reminders and weekly analysis
- Reminders — configure daily reminder and smart nudges (or disable)
- Reset — wipe stored user profile/session data

## Next steps
- Add tests (unit + integration) per the technical description.
- Expand validation and error handling around Sheets/LLM integrations.

# TODOs
- update habit feature
- option to choose habit for deletion using buttons
