## Context
`handle_habits_text` joins earlier raw text and additions with `[Update]`, extracts
custom fields, and sets `diary = combined_text`. `HabitExtractor` deliberately
excludes `diary` and `raw_record` from model output. Configuration also prevents
editing the diary field. These rules protect against earlier diary shortening, so
the replacement must preserve detail without requiring diary/raw equality.

## Decisions
- Use one LLM call to produce the full current diary and all configured habit
  values in one structured response. Keep `raw_record`, date selection, entry IDs,
  timestamps, defaults, validation, and saving under application control.
- Supply entry-scoped message history: system editing/extraction rules and schema,
  original user input, previous structured assistant drafts, and later user
  additions. Preserve original user turns, not just generated summaries. Do not
  include unrelated Telegram menu messages or other days' conversations.
- A previous assistant draft is context, not a source of new facts; habit values
  must follow the original user turns and explicit later corrections. Never
  extract habits solely from a polished diary.
- When appending to a saved entry, initialize context from the saved original
  text and current diary/fields, without assuming a complete earlier chat history
  is available. When rewriting, start a new entry history.
- A diary-only schema must still run unified processing. With diary disabled,
  omit diary generation and extract only configured habit fields; skip the model
  if neither task is enabled.
- Retain prior diary context when editing an unconfirmed draft and when loading
  a saved entry for append. Repeated additions must build on the latest draft,
  without losing earlier additions or duplicating the entire raw history.
- Preserve language, first-person perspective, vocabulary, uncertainty, names,
  and all narrative details, including intimate or health-related experiences.
  Make only edits needed to integrate additions and remove bot-directed wording.
- Treat explicit later corrections as corrections; do not silently resolve an
  ambiguous contradiction. Do not infer that unrelated events happened together.
- Distinguish field-setting instructions from narrative: an isolated score-setting
  addition changes fields only; a statement such as "Мне было грустно" stays in
  the diary even when it also informs an extracted field. Do not classify every
  mention of a habit as a command.
- Validate structured output; an empty diary is acceptable only when all input
  consists of field-setting instructions and there was no previous narrative.
- Explicitly configure JSON Schema structured output for a compatible endpoint,
  retaining application-side schema validation. The response schema constrains
  format; preservation and placement still require prompt instructions and
  behavioral evaluation.
- Increase or calculate the output token budget for full diary plus habit values;
  the current 2,000-token limit is not sufficient for every accepted 30,000-unit
  entry. Treat truncated responses as processing failures, not valid drafts.
- Use the configured timeout for short entries. Above 8,000 characters, allow one
  extra second per 150 characters, capped at 180 seconds (without lowering a
  larger configured timeout), both in the handler and SDK transport. The live
  20,202-character fixture needed 44 seconds initially and its addition exceeded
  the old 45-second timeout. Do not retry automatically or change the model.
- On timeout, missing model, or invalid output, retain the prior readable diary
  plus the verbatim addition joined by a paragraph break, and show a localized
  notice that the addition could not be integrated. On initial entries use all
  original input. Never present this fallback as successfully composed prose.
- Keep confirmation, chunking, existing-row targeting, and save retry/idempotency
  behavior. Do not regenerate prose during a save retry.

## Risks / Trade-offs
- A model can omit details or place them incorrectly. A preservation-focused
  prompt, complete preview, and behavioral evaluation examples are required.
  Mocked unit tests verify wiring and fallback, not model quality. Implementation evidence and the real Gemini prose review are recorded in `docs/evals/2026-10-22/diary-integration-report.md`.
- A single combined call avoids a second request, but full-diary output and
  repeated history still add tokens. Keep history scoped to one entry and use
  the existing timeout conventions; do not add providers or external services.
- Existing `raw_record` may contain historical generated markers. These remain
  in the source text but are omitted from generated narrative; no bulk migration.

## Verification
Exercise initial text/voice input, three consecutive draft additions, append to a
saved row with a diary differing from raw text, rewrite, diary-only schema,
disabled diary, ratings-only and mixed additions, model failures, long previews,
and save retry. Use deterministic fakes for handler regression tests and record
real model behavior separately if a configured test environment is available.
