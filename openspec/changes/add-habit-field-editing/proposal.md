# Change: Add habit field editing and button-based removal

## Why
Habit field configuration currently supports only add/remove via text, making updates cumbersome and removal error-prone.

## What Changes
- Add an edit flow for custom habit fields (name, description, type, min, max).
- Provide inline buttons to select fields for removal (and for editing).
- Update localized prompts and inline button labels to cover editing actions.

## Impact
- Affected specs: habit-field-config
- Affected code: habits config handlers, inline keyboards, localized messages
