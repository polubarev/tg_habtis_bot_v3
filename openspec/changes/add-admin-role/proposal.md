# Change: Add env-based admin features

## Why
The bot owner needs private operational tools inside Telegram to inspect lightweight usage, review feedback, and message users without exposing these actions to normal users.

## What Changes
- Add env-configured admin access using Telegram user IDs.
- Add an admin menu and `/admin` command guarded by admin checks.
- Provide aggregate user/usage stats and recent feedback viewing.
- Add a broadcast flow with preview and explicit confirmation before sending.

## Impact
- Affected specs: admin (new)
- Affected code: settings, Telegram routing/keyboards/messages, user and feedback repositories, session state, tests
