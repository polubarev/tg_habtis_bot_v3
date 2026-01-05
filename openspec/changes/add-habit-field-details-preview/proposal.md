# Change: Show habit field details before edit

## Why
Users need to see the current field details before choosing what to update in the edit flow.

## What Changes
- Show the selected habit field details (name, description, type, min, max) before prompting for an edit attribute in /habits_config.
- Update localized messaging to include the details preview.

## Impact
- Affected specs: habit-field-config
- Affected code: habits config handlers, localized messages
