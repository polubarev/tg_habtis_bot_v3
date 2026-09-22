## 1. Collection model and persistence
- [x] 1.1 Add typed collection and part models, statuses, limits, and input kinds.
- [x] 1.2 Add transactional Firestore and locked in-memory collection adapters.
- [x] 1.3 Add the shared collection interface for start, append, and actions.

## 2. Telegram flows
- [x] 2.1 Route habits, dreams, thoughts, and reflections through collection mode.
- [x] 2.2 Append transcribed voice as an ordered part and support mixed input type.
- [x] 2.3 Add one editable Done/Undo/Cancel status card and localized messages.
- [x] 2.4 Process atomically on Done and send full chunked confirmations.
- [x] 2.5 Preserve collections and processed drafts across retryable failures.

## 3. Sheets idempotency
- [x] 3.1 Add entry UUIDs and append-only header migration for all tabs.
- [x] 3.2 Make all row writers header-driven.
- [x] 3.3 Reconcile entry IDs before retrying ambiguous writes.

## 4. Verification
- [x] 4.1 Add collection, concurrency, limit, expiry, and mixed-input tests.
- [x] 4.2 Add handler tests for all four flows and recovery states.
- [x] 4.3 Add Sheets migration/idempotency tests and an end-to-end multipart scenario.
