## ADDED Requirements

### Requirement: Batch media collection
The system SHALL let a user collect between one and ten voice notes, audio files, videos, or video notes in a dedicated localized transcription flow.

#### Scenario: Forward several media messages
- **WHEN** a user starts Transcription and forwards supported media messages
- **THEN** the system stores each item in arrival order and reports the current count

#### Scenario: Collection limits
- **WHEN** an item exceeds 20 MB, duplicates an existing item, or makes the batch exceed 60 minutes
- **THEN** the system rejects that item without leaving collection mode

### Requirement: Explicit and automatic submission
The system SHALL submit a non-empty batch when the user selects Transcribe and SHALL submit automatically when the tenth item is accepted.

#### Scenario: Submit fewer than ten items
- **WHEN** the user selects Transcribe with one through nine collected items
- **THEN** the batch is queued exactly once and the user may continue using the bot

#### Scenario: Accept the tenth item
- **WHEN** the tenth valid item is accepted
- **THEN** the batch is locked and queued automatically

### Requirement: Resumable asynchronous transcription
The system SHALL process submitted batches through an authenticated background task and checkpoint every completed item.

#### Scenario: Worker retry
- **WHEN** processing is retried after a transient failure
- **THEN** already completed items are not transcribed again

#### Scenario: Partial failure
- **WHEN** one or more items fail permanently
- **THEN** successful transcripts are delivered in order and failed items are identified without exposing provider details

### Requirement: Combined private result
The system SHALL return one logically combined, numbered transcript and SHALL not persist or log forwarding-source information.

#### Scenario: Long result
- **WHEN** the combined transcript would require more than three Telegram text messages
- **THEN** the system sends the transcript as a UTF-8 text document

#### Scenario: Successful delivery
- **WHEN** the transcript is delivered
- **THEN** stored file identifiers and transcript content are purged while content-free delivery metadata is retained for idempotency
