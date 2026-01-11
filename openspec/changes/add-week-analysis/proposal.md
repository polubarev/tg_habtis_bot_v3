# Change: Add weekly analysis

## Why
Users want a weekly overview that synthesizes their last 7 completed days into insights from a psychology and habit coaching perspective.

## What Changes
- Add a main-menu button to trigger weekly analysis.
- Fetch the last 7 completed days of habit entries (diary + habit fields) from the user’s sheet.
- Build a localized LLM prompt and return a structured, helpful weekly analysis.
- Handle missing sheet access or insufficient data with clear user messaging.

## Impact
- Affected specs: weekly-analysis
- Affected code: Telegram handlers, buttons/messages, Sheets access, LLM prompt templates
