# Change: Add feedback entry in settings menu

## Why
Users need a simple, in-bot way to share feedback; today there is no feedback channel.

## What Changes
- Add a "Feedback" option under the Config menu.
- Prompt the user for a free-text message and capture the next message as feedback.
- Persist feedback entries in Firestore with user metadata and a timestamp.
- Acknowledge success; show a clear error if Firestore is unavailable.

## Impact
- Affected specs: user-feedback (new)
- Affected code: Telegram handlers/router/keyboards/constants, Firestore storage (new), tests
