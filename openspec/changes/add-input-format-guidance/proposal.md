# Change: Add non-technical input guidance for habit field types

## Why
Users struggle to understand expected data types and formats when adding habit fields, leading to errors and retries.

## What Changes
- Add clear, non-technical explanations and examples before requesting type/min/max inputs.
- Make validation errors explain what was wrong and what format is expected.
- Keep guidance consistent in both EN/RU for the habit field configuration flow.

## Impact
- Affected specs: habit-field-config (new delta)
- Affected code: habit field config handlers and localized message templates
