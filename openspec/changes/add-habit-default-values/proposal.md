# Change: Add default values for habit fields

## Why
Users need a way to define per-habit default values so missing extractions can be filled automatically and shown clearly in the draft preview.

## What Changes
- Add default value inputs/edits for habit fields in the add and edit flows.
- Validate defaults against field type and numeric min/max constraints.
- Apply defaults only when extracted values are None, and annotate draft previews with a default marker.
- Ensure sheet writes use the actual default value without the marker suffix.

## Impact
- Affected specs: habit-field-config
- Affected code: habit config handlers, keyboards, localized messages, habit extraction/preview pipeline
