# Change: Integrate diary additions into a coherent entry

## Why
Habits drafts currently copy `raw_record` into `diary` verbatim and insert a literal
`[Update]` between confirmation rounds or additions to saved entries. Consequently,
field-setting instructions such as "Настроение 2, важность дня 2" appear inside the
diary, and late details cannot be placed next to the events they describe. This is
intentional existing behavior, enforced by code and tests, so changing it requires
an approved behavior change rather than a separator-only bug fix.

## What Changes
- Keep all original text and voice transcripts in `raw_record` as the source of truth.
- Generate a separate diary with minimal editing, in the user's language and voice.
- Use one LLM request per processing round for both the diary and habit values,
  with entry-scoped message history and one structured response schema. A separate
  diary-generation call is not required.
- Integrate additions into the relevant time or topic when the context is clear.
  Otherwise add a natural paragraph without inventing chronology or relationships.
- Exclude field-setting instructions from the diary while applying them to habit
  fields. Preserve actual experiences, feelings, and explicit sensitive details.
- Remove application-generated `[Update]` markers from the generated diary,
  including markers inherited from older entries; preserve original stored text.
- Preserve the full confirmation preview and explicit save confirmation.
- Update the fixed diary description and RU/EN help text to explain the new
  behavior. Arbitrary editing of diary instructions is outside this change.
- Use a visible, lossless fallback when the model is unavailable or fails.

## Acceptance Examples
- Existing diary: "Утром позавтракал. Вечером играл с друзьями." Addition:
  "Забыл добавить: утром ещё сходил в магазин." The shopping detail belongs next
  to breakfast, with the evening event retained.
- Addition: "Настроение 2, важность дня 2." Update those configured fields and
  leave the diary narrative unchanged.
- Addition: "Пока Катя бегала, мастурбировал." Preserve the event in the diary
  and extract the configured habit; do not sanitize it or invent a time of day.
- An addition without a clear time or topic becomes a separate natural paragraph.

## Impact
- Affected specs: habits-logging (existing capability; delta included here).
- Affected code: habits handler, unified LLM processing, session draft context,
  habit descriptions and localized messages, handler and LLM regression tests.
- Existing rows are not bulk-rewritten. Only newly confirmed saves change diaries.
- Diary generation now needs an LLM even when no custom habit fields are configured;
  timeout handling and a lossless fallback remain necessary.

## Approval
Approved by the user on 2026-10-22; implementation and verification are authorized. Keep the configured Gemini 3.8 Flash model.
