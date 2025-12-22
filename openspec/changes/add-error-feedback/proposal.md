# Change: Add explicit user-facing error feedback for external failures

## Why
Users currently receive no feedback when external writes or requests fail, leading to silent failures and confusion. We need clear, actionable error messaging for common failure modes.

## What Changes
- Add explicit error states and human-readable messages for Google Sheets write failures.
- Add handling for network/server timeouts with next-step guidance.
- Add handling for invalid external responses (e.g., malformed LLM output, transcription failures).
- Ensure every external operation results in either success confirmation or a clear error message.

## Impact
- Affected specs: error-handling (new)
- Affected code: Telegram handlers, Sheets client, LLM/Whisper clients, message constants, tests
