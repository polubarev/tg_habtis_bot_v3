# Change: Add admin period usage statistics

## Why
Current admin statistics use cumulative counters on user profiles, so they cannot answer period-based questions like weekly active users, monthly usage, or feature usage over time. Admins need lightweight operational analytics inside Telegram without exposing user diary content.

## What Changes
- Add content-free usage event persistence for completed bot actions and relevant operational events.
- Add admin stats views for today, this week, this month, and last 30 days.
- Report unique active users, new users, connected-sheet users, feature usage, voice usage, feedback count, and broadcast results for a selected period.
- Keep existing cumulative profile counters for quick totals and backward compatibility.

## Impact
- Affected specs: admin-analytics (new)
- Affected code: usage event model/repository, Telegram completion flows, feedback/admin broadcast handlers, admin menu/buttons/messages, tests
