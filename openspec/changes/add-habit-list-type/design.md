## Context
Users want to track categorical habit values (e.g., work_place = home/office/holiday). Current habit field types (string/int/number/boolean) do not constrain values, so extraction can drift and reports become noisy.

## Goals / Non-Goals
- Goals:
  - Support a new habit field type `list` backed by a fixed set of allowed options.
  - Let users choose single-select vs multi-select while configuring the field.
  - Enforce strict options during extraction, falling back to null when no option matches.
- Non-Goals:
  - New onboarding flow changes; list type is configured via existing habit config UI.
  - Multi-language synonym mapping beyond case-insensitive matching.

## Decisions
- Decision: Extend `HabitFieldConfig` with `options: list[str] | None` and `allow_multiple: bool`.
  - Rationale: Keeps list semantics explicit while avoiding a separate schema model.
- Decision: Prompt for list mode (single/multi) and options as comma-separated values during add/edit.
  - Rationale: Matches current step-by-step config flow and keeps input lightweight in Telegram.
- Decision: Enforce strictness in post-processing rather than hard schema validation.
  - Rationale: Structured output should guide the LLM, but invalid values should not fail the entire extraction; normalize to null instead.
- Decision: For multi-select values, store comma-separated values in Sheets.
  - Rationale: Sheets columns are scalar; list values should remain readable and searchable.
- Decision: Match options case-insensitively but store canonical values as configured.
  - Rationale: Tolerates user/LLM casing without drifting stored values.
- Decision: Multi-select order is not significant; normalization preserves configured option order.
  - Rationale: Keeps output stable and readable without implying semantic order.

## Risks / Trade-offs
- LLM may still output invalid values; normalization mitigates but could hide extraction issues.
- Comma-separated storage loses original ordering if we later dedupe or normalize.

## Migration Plan
- Backward compatible: existing habit fields remain unchanged.
- New list fields are optional and require `options` to be set during configuration.

## Open Questions
- None.
