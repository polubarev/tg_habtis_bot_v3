# Change: Update habits config UX and cleanup transient messages

## Why
The current habits config flow requires free-text type entry, removal lacks visibility into existing custom fields, and transient progress messages linger after completion, creating friction.

## What Changes
- Add inline buttons for habit field type selection with localized labels and examples.
- Show the current custom habit fields list when prompting for removal.
- After adding a habit field, return the user to the habits config menu.
- Remove transient "processing" / "saving" messages after success or error outcomes.

## Impact
- Affected specs: habit-field-config, progress-messages (new delta specs)
- Affected code: habit config handlers, keyboards, localized messages, and command flows that post progress messages
