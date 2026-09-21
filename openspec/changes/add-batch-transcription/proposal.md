# Change: Add batched Telegram transcription

## Why
Users need to forward or send several voice/audio/video messages and receive one ordered transcript without routing the content into diary flows.

## What Changes
- Add a localized Transcription menu flow that collects up to ten supported media messages.
- Persist batches safely in Firestore and process them asynchronously through a dedicated Cloud Tasks queue.
- Return ordered combined transcripts with partial-failure handling and long-output file fallback.
- Preserve existing voice-to-diary behavior outside transcription mode.

## Impact
- Affected specs: batch-transcription
- Affected code: Telegram routing/keyboards, session state, Firestore repositories, Cloud Tasks scheduling, FastAPI dispatch, settings/deployment, analytics, tests
