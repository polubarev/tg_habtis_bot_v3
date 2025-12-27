# Change: Add per-user usage statistics

## Why
We want lightweight analytics per user (counts only) to understand feature usage without storing any diary/recording content.

## What Changes
- Add per-user usage counters to the user profile (Firestore user doc).
- Increment counters when a user completes a feature flow (habits/dream/thought/reflection).
- Keep analytics content-free (only counts, no text or payloads).

## Impact
- Affected specs: usage-stats (new)
- Affected code: user profile model, feature handlers, user repository persistence
