# Design: Smart nudges (conditional multi-time reminders)

## Goals
- Remind users **a few times per day** only when the relevant day is missing.
- Support the common behavior: users mostly log **yesterday**.
- Keep Cloud Run cold-start friendly: rely on Cloud Tasks, schedule **one next** task per user.
- Avoid reading Google Sheets for every nudge; use local persistence (Firestore) when available.

## Non-goals
- Perfect detection when persistence is unavailable (in-memory mode resets on restart).
- Complex per-habit completeness rules (this feature is about "did you log habits for the day").

## UX Flow (Settings)
- Entry point: `Config → Reminders → Smart nudges`
- Screen shows:
  - Status: On/Off
  - Times: list of HH:MM (local)
  - Rollover time: HH:MM (local), default `12:00`
  - Note: "Before rollover I remind for yesterday; after rollover for today."
- Actions:
  - Enable/Disable
  - Edit times (user sends `09:00, 14:00, 20:00`; validate HH:MM; dedupe; sort)
  - Edit rollover time (single HH:MM)

## Due day logic
Given `now` in user timezone and `rollover_time`:
- If `now.time() < rollover_time` → `due_date = (now.date() - 1 day)`
- Else → `due_date = now.date()`

Nudge eligibility:
- If smart nudges disabled → skip
- If user has `last_habits_logged_for_date == due_date` → skip
- Otherwise → send

Important behavior:
- After rollover, `due_date` becomes **today**. If the user logs **yesterday** at 18:00, nudges still apply for **today** (until today is logged).

## Scheduling
### Inputs
- `times`: list of local `time` values (e.g., 09:00, 14:00, 20:00)
- `timezone`: IANA tz name

### Next-run selection (one-task-at-a-time)
- Convert `now` to user timezone.
- Pick the earliest configured time that is still in the future today.
- If none remain today, pick the first configured time tomorrow.
- Convert to UTC and schedule a Cloud Task for that datetime.

### Dispatch
On task execution:
- Load user profile
- Compute `due_date`
- Decide send/skip based on eligibility
- Always schedule the next task (so the schedule continues)

## Data model additions
Add to `UserProfile`:
- `smart_nudges_enabled: bool`
- `smart_nudges_times: list[str]` (HH:MM strings)
- `smart_nudges_rollover_time: str` (HH:MM string, default `12:00`)
- `smart_nudges_task_name: str | None`
- `last_habits_logged_for_date: str | None` (ISO `YYYY-MM-DD`, based on the date the user saved in the Habits flow)

## Message + actions
Nudge message:
- Must mention which day is missing (Yesterday/Today, localized).

Inline actions (minimal set):
- `Log now` → starts `/habits` with the due date preselected.
- `Disable nudges` → turns off smart nudges and deletes pending task.

Optional actions:
- `Choose day` → Today / Yesterday (opens the Habits flow)
- `Snooze 1h` → suppress nudges until `now + 1h` (store `smart_nudges_snooze_until`).

## Security
- Use the existing reminder-dispatch secret header for Cloud Tasks → FastAPI dispatch.
- Payload MUST include the Telegram user id; dispatch MUST reject missing/invalid ids.

