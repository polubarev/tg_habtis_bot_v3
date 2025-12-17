# Change: Telethon-based integration tests for bot behaviour

## Why
We lack end-to-end coverage of Telegram conversations; only unit tests exist. Using Telethon as a real Telegram client will let us drive commands (/start, /habits, etc.) and assert bot responses, reducing regressions in conversation flows.

## What Changes
- Introduce a Telethon-driven integration test harness that sends real Bot API updates to the running webhook and validates replies for core flows.
- Add minimal configuration/env contract so tests can run against a dedicated test bot/user and skip safely when tokens/IDs are absent.
- Document how to run these tests locally and in CI with guarded credentials.

## Impact
- Affected specs: testing
- Affected code: integration/e2e test suite, test utilities for Telethon, possibly test configuration/env parsing, CI test command wiring.
