# Change: Add explicit user-facing error feedback for external failures

## Why
Users currently receive no feedback when external writes or requests fail, leading to silent failures and confusion. We need clear, actionable error messaging for common failure modes.

## What Changes
- Add explicit error states and human-readable messages for Google Sheets write failures.
- Add handling for network/server timeouts with next-step guidance.
- Add handling for invalid external responses (e.g., malformed LLM output, transcription failures).
- Ensure every external operation results in either success confirmation or a clear error message.
- Preserve retryable drafts and keep progress messages visible until final delivery succeeds.
- Split all user-derived Telegram responses into safe-sized chunks.
- Prevent diary, transcript, prompt, and extracted content from reaching application or SDK logs.
- Make production images immutable and expose the deployed Git revision for verification.

## Impact
- Affected specs: error-handling (new), logging-privacy (new), deployment (new)
- Affected code: Telegram handlers, logging, deployment scripts, message constants, tests
