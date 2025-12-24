# Change: Add daily reminders with per-user timezone

## Why
Users want a daily reminder to log habits/diary entries, but the service runs cold and needs a reliable scheduler to deliver messages.

## What Changes
- Add a Config flow to set a daily reminder time per user.
- Schedule reminders using Cloud Tasks so reminders trigger even when the app is idle.
- Send a simple text reminder message in the user's language.

## Impact
- Affected specs: reminders (new capability)
- Affected code: Telegram config handlers/keyboards, user profile storage, FastAPI webhook endpoints, reminder scheduling service
