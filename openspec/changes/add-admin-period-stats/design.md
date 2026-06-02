## Context
The bot already emits structured Cloud Logging analytics via `log_event`, and admin stats currently aggregate cumulative `UserProfile.usage_stats` counters. Cloud Logging/BigQuery remains best for external dashboards, but Telegram admin stats need a simple in-app data source that works directly from Firestore.

## Goals / Non-Goals
- Goals: provide period-based admin stats in Telegram; store no diary text, extracted habit values, recordings, or feedback message bodies in usage events; work with Firestore and degrade gracefully if storage is unavailable.
- Non-Goals: replace BigQuery dashboards; build charts; track detailed per-user content; backfill historical stats before this feature is deployed.

## Data Model
Add a `UsageEvent` model stored in a configurable Firestore collection, default `usage_events`.

Fields:
- `user_id: int | None`
- `event_name: str`
- `feature: str | None`
- `occurred_at: datetime`
- `day: str` in `YYYY-MM-DD`
- `week: str` in ISO year-week format, for example `2026-W23`
- `month: str` in `YYYY-MM`
- `metadata: dict[str, str | int | bool]` limited to low-cardinality operational values

Allowed events for the first version:
- `feature.saved` with feature `habits`, `dream`, `thought`, `reflection`
- `command.used` with feature matching command names where useful for activity
- `voice.received`
- `feedback.submitted`
- `broadcast.sent` with sent/failed counts

## Query Strategy
Repository methods should support:
- Create a usage event.
- Query events between UTC datetimes.
- Aggregate period stats in application code for the small expected bot scale.

Period presets:
- Today: user timezone is not relevant for admin stats; use UTC dates for stable server-side periods.
- This week: ISO week containing current UTC date.
- This month: current UTC month.
- Last 30 days: rolling UTC window.

## Privacy
Usage events must be content-free. They may include counts, feature names, success/failure booleans, and user IDs, but must not include diary text, habit data, dream/thought text, reflection answers, voice transcripts, or feedback message text.

## Rollout
Historical period stats start from deployment time. Existing cumulative profile counters still show lifetime totals, but period stats do not backfill old usage.
