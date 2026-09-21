## Context
Telegram delivers forwarded media as independent updates. Current voice handling transcribes each update immediately and session persistence uses non-transactional last-write-wins writes. A batch must therefore have its own transactional persistence and must not run inside the Telegram webhook request.

## Goals / Non-Goals
- Goals: collect 1-10 voice/audio/video/video-note items, preserve arrival order, process asynchronously, resume safely after retries, and avoid content-bearing analytics.
- Non-Goals: speaker diarization, caption transcription, protected-content workarounds, more than one active batch per user, or replacing the existing Whisper model.

## Decisions
- Use `transcription_batches/{user_id}` with a unique batch UUID and transactional appends.
- Store Telegram file identifiers until processing; never store media bytes.
- Use a dedicated Cloud Tasks queue and authenticated dispatch endpoint.
- Checkpoint each item and make enqueue/dispatch idempotent.
- Process sequentially and return partial results for permanent failures.
- Keep existing voice routing unchanged unless the session is collecting a transcription batch.

## Risks / Trade-offs
- Long batches may retry after transient provider errors; persisted checkpoints avoid repeating completed items.
- Exactly-once Telegram delivery is unavailable; delivery markers minimize duplicate results after retries.
- Telegram's hosted Bot API download limit makes 20 MB the per-item ceiling.

## Migration Plan
Deploy the code and secrets, create the `transcriptions` queue, then expose the new menu button. Existing sessions and users require no data migration.
