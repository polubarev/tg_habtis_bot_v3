## 1. Implementation
- [x] 1.1 Extend `UserProfile` with smart nudge settings (enabled, times list, rollover time, task name) and last-habits-logged date.
- [x] 1.2 Add helpers to compute the due day from timezone + rollover time and determine whether a nudge should be sent.
- [x] 1.3 Implement multi-time scheduling (compute next run from a daily list of times; schedule exactly one next Cloud Task at a time).
- [x] 1.4 Add Smart nudges UI under Config → Reminders (enable/disable, edit times, edit rollover time, show current status).
- [x] 1.5 Add dispatch handling to send a nudge message when due day is missing and reschedule the next nudge task.
- [x] 1.6 On successful Habits save, persist the logged-for date (so nudges do not require reading Google Sheets).
- [x] 1.7 Add minimal inline actions on the nudge message (Log now / Disable), and wire them to existing flows.

## 2. Tests
- [x] 2.1 Add unit tests for due-day rollover logic (before/after rollover, timezone correctness).
- [x] 2.2 Add unit tests for next-run selection from multiple daily times (same-day and next-day scheduling).
- [ ] 2.3 Add tests for dispatch skip/send behavior (disabled, already logged, missing settings).
