# Change: Add smart nudges for missing habit logs

## Why
Many users log their habits for *yesterday* (expected behavior). A single daily reminder is often insufficient: users forget and want a few gentle reminders during the day, but only when the relevant day is still missing.

## What Changes
- Add a new Settings mode: **Smart nudges** (conditional reminders) configured with multiple times per day.
- Introduce a user-configurable **rollover time** (default `12:00` local time) to decide which day is "due":
  - Before rollover: the due day is **yesterday**
  - After rollover: the due day is **today**
- Send nudges only if the user has not saved a Habits entry for the current due day.
- After rollover, nudges continue for **today** even if the user logs **yesterday** later in the day.
- Add quick actions on nudges (at minimum: **Log now** for the due day and **Disable nudges**; optionally: **Choose day** and **Snooze**).
- Schedule nudges via Cloud Tasks using the existing reminder-dispatch secret mechanism.

## Impact
- Affected specs: reminders (extend existing capability)
- Affected code: user profile model/storage, habits save flow (to record last logged date), reminder scheduling helpers, FastAPI dispatch endpoint(s), Telegram settings UX (keyboards/messages)

