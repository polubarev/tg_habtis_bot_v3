# Change: Add loading indicators and timeout feedback

## Why
Long-running operations (LLM extraction, transcription, Sheets writes) can take ~30s, which feels like the bot is broken without immediate feedback.

## What Changes
- Add explicit loading indicators ("Processing…" and "Saving data…") within 1–2 seconds of user actions.
- Define a timeout threshold for long-running operations.
- On timeout, return a human-readable message instead of silence.

## Impact
- Affected specs: response-timing (new)
- Affected code: Telegram handlers, long-running service calls, message constants
