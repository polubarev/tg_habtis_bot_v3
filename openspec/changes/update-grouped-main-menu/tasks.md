## 1. Implementation
- [x] 1.1 Add localized category labels and prompts in Russian and English.
- [x] 1.2 Replace the main keyboard with the two-row category menu; add Records, Review, and Tools keyboards with Back.
- [x] 1.3 Route category buttons safely, preserving existing commands, old action labels, active input flows, cancellation, and return to the main menu. Register the previously missing `/cancel` command.
- [x] 1.4 Update user-facing menu documentation.

## 2. Verification
- [x] 2.1 Verify category layout and reachability of all existing actions in both languages.
- [x] 2.2 Verify Back, Cancel, old keyboard labels, and category selection during unfinished entry and transcription flows.
- [x] 2.3 Run relevant tests and lint checks: 243 passed, 1 skipped; Ruff passed.
- Type checking attempted; existing environment/stub and unchanged scheduler ignore diagnostics prevent a clean full run. Details are recorded in `proposal.md`.
- [ ] 2.4 Run `openspec validate update-grouped-main-menu --strict` when the CLI is available. Blocker: OpenSpec CLI is not installed or available on PATH; delta format reviewed manually.
