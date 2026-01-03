## Context
Habits entries are currently append-only. We need a user choice when a date already has entries.

## Goals / Non-Goals
- Goals: detect existing entry for selected date, prompt user, update the most recent row on rewrite or append, refresh timestamp.
- Non-Goals: editing arbitrary historical rows beyond the most recent match, changes to dreams/thoughts/reflections.

## Decisions
- Use the Habits sheet "date" column to find matches; select the last matching row index as the most recent entry.
- Append choice combines previous raw_record with the new text using a separator and re-runs extraction; rewrite uses only the new text.
- Update the selected row instead of appending a new row; set timestamp to current time for both choices.
- If the sheet is not configured or a read fails, skip the prompt and continue with the normal flow.

## Risks / Trade-offs
- Sheets date formatting may vary; matching will parse ISO and common date formats and handle numeric date serials from Sheets.

## Migration Plan
No migration; behavior changes only for new entries.

## Open Questions
None.
