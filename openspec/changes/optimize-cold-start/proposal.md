# Change: Optimize cold start behavior

## Why
Cold starts can feel slow when Cloud Run scales from zero. Reducing container size and startup work improves time-to-first-response while keeping scale-to-zero cost savings.

## What Changes
- Remove unused ffmpeg dependency from the container image.
- Add optional Cloud Run startup CPU boost flag in the deploy script.
- Lazy-initialize external clients (LLM/Whisper/Sheets/Firestore) to reduce startup work.

## Impact
- Affected specs: deployment
- Affected code: Dockerfile, Cloud Run deploy script, Telegram bot service/client initialization
