# Change: Add resilient multipart text entry collection

## Why
Telegram limits a text message to 4,096 UTF-16 units, while diaries and other free-form entries can span several messages. Immediate processing also makes consecutive messages race and prevents reliable recovery.

## What Changes
- Collect ordered text and transcribed voice parts for habits, dreams, thoughts, and reflections.
- Require an explicit Done action and provide Undo last and Cancel controls.
- Enforce a 30,000 UTF-16-unit aggregate limit and preserve collections across retryable failures.
- Show complete confirmations using Telegram-safe chunks.
- Add stable entry identifiers and idempotent Google Sheets retry behavior.

## Impact
- Affected specs: text-entry-collection (new), sheet-entry-idempotency (new)
- Affected code: session routing, Telegram handlers/keyboards, Firestore repositories, Sheets models/client, tests
