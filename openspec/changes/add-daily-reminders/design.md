# Design: Daily reminders via Cloud Tasks

## Overview
- Store per-user reminder settings in `UserProfile` (time string, enabled).
- When a user sets/updates a reminder, enqueue a Cloud Task scheduled for the next local occurrence.
- When a reminder task executes, send a Telegram message and schedule the next task.

## Scheduling
- Parse HH:MM in the user's timezone.
- Compute the next reminder time; if the time has already passed today, schedule for tomorrow.
- Convert to UTC for Cloud Tasks schedule_time.

## Cloud Tasks
- Use a dedicated queue configured via env vars.
- Task targets a FastAPI endpoint `/reminders/dispatch` with a secret header.
- Task payload includes the Telegram user id.
- On execute: load user profile, verify reminders are enabled and time is set, then send message and reschedule.

## Security
- Require a shared secret header for `/reminders/dispatch`.
- Keep the Telegram webhook endpoint behavior unchanged.
