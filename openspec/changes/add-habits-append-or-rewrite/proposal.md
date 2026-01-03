# Change: Prompt to rewrite or append same-day habits entries

## Why
Users can log multiple times per day, but the bot always appends a new row without a choice.

## What Changes
- Detect existing Habits rows for the selected date and ask the user to rewrite or append.
- Rewrite replaces the most recent row for that date with a new extraction and updates the timestamp.
- Append combines the existing raw_record with new text, reprocesses extraction, and updates the same row.

## Impact
- Affected specs: habits-logging (new)
- Affected code: src/services/telegram/handlers/habits.py, src/services/telegram/keyboards.py, src/config/constants.py, src/services/storage/interfaces.py, src/services/storage/sheets/client.py, src/models/session.py
