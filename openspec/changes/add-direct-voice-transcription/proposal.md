# Direct voice transcription

## Why

Users can send voice notes to the bot without opening a diary workflow. The bot already returns a transcript, but also treats that transcript as typed input, which can open a menu or send an unrelated help message.

## What changes

- Reply to each standalone voice note with its transcript.
- Give active diary and transcription collections priority. Pass a completed transcript to an input step only when the same step is still active.
- Reuse the current transcription service and error handling.

## Impact

- Voice message routing and its regression tests.
