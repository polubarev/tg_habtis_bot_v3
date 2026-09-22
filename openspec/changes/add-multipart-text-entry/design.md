## Context
Telegram delivers multipart text and media as independent updates. Current handlers process the first message immediately, and session writes are last-write-wins. Collection therefore requires transactional ordered persistence and an explicit completion action.

## Goals / Non-Goals
- Goals: one shared collection interface, ordered/idempotent parts, mixed text and voice, retryable processing and saving, full confirmation previews.
- Non-Goals: automatic pause-based completion, concurrent active entry collections per user, editing individual historical parts, or changing existing saved rows.

## Decisions
- Use a `text_entry_collections/{user_id}` Firestore document with an in-memory adapter and per-user locks.
- Present one editable inline status card with Done, Undo last, and Cancel actions.
- Count limits using Telegram UTF-16 units and join accepted parts with two newlines.
- Atomically claim Done so duplicate callbacks do not repeat processing.
- Store a generated `entry_id` in every new Sheet row and reconcile it before retrying ambiguous writes.
- Start a new empty collection when a generated draft is rejected for editing.

## Risks / Trade-offs
- Every entry requires an extra Done action; this removes ambiguous timing and races.
- Very long confirmations create several Telegram messages; all content remains visible and controls stay on the final chunk.
- Google Sheets does not provide native append idempotency; stable IDs plus reconciliation prevent intentional duplicate retries and make ambiguous writes detectable.

## Migration Plan
Deploy error/output/logging safeguards first. Then deploy collection support and append `entry_id` headers without moving existing columns or changing historical rows.
