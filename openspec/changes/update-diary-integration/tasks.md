## 1. Diary composition
- [x] 1.1 Add unified diary/habit processing with entry-scoped message history,
  preservation-focused instructions, explicit JSON Schema output, adequate output
  token budget, validation, timeout handling, and lossless fallback.
- [x] 1.2 Cover chronology, ratings-only commands, mixed narrative and commands,
  explicit corrections, ambiguous placement, sensitive details, and old markers.

## 2. Habits flow
- [x] 2.1 Pass the prior diary and new additions through draft-edit and saved-append
  flows, keeping raw text intact and extracting habits from original input.
- [x] 2.2 Support initial entries, diary-only schemas, disabled diary, and rewrite;
  preserve full confirmation, same-row updates, and retry behavior.
- [x] 2.3 Update fixed field descriptions and localized RU/EN messages, including
  the composition-failure notice.

## 3. Verification
- [x] 3.1 Update handler tests that currently require diary/raw equality and add
  regression cases for repeated additions, chronology, and ratings-only updates.
- [x] 3.2 Verify fallback, empty/invalid output, long previews, raw preservation,
  sheet save behavior, and save retry without another composition call.
- [x] 3.3 Verify message order, isolation between dates, append context from saved
  entries, explicit later corrections, and handling of output truncation.
- [x] 3.4 Run relevant tests and lint; document whether real model evaluation ran.

## Verification evidence
See `docs/evals/2026-10-22/diary-integration-report.md`: 282 offline tests passed, one skipped; 16 real Gemini requests (15 valid, one initial timeout resolved by a successful long-entry recheck). Full final prose for six synthetic cases was read. External Telegram/Sheets writes were mocked.
