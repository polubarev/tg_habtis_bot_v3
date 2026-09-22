## ADDED Requirements

### Requirement: Collect multipart entries
The system SHALL collect one or more ordered text or transcribed voice parts for habits, dreams, thoughts, and reflections until the user explicitly finishes.

#### Scenario: Submit two text parts
- **WHEN** a user sends two messages and selects Done
- **THEN** the system processes one entry containing both parts joined by two newlines in Telegram message order

#### Scenario: Submit mixed text and voice
- **WHEN** a user sends text and voice during the same collection
- **THEN** the system stores the voice transcript as an ordered part and records mixed input for habits

### Requirement: Collection controls
The system SHALL maintain one status card with Done, Undo last, and Cancel controls.

#### Scenario: Undo latest part
- **WHEN** the user selects Undo last after collecting multiple parts
- **THEN** only the latest ordered part is removed and the status counts are updated

### Requirement: Collection size limit
The system SHALL reject a part that would make the combined collection exceed 30,000 UTF-16 units without discarding previously accepted parts.

#### Scenario: Part exceeds remaining capacity
- **WHEN** a new part crosses the aggregate limit
- **THEN** that part is rejected and the existing collection remains unchanged

### Requirement: Retryable collection processing
The system SHALL retain collected content and atomically claim completion so failures and duplicate callbacks do not repeat successful work.

#### Scenario: Processing times out
- **WHEN** processing a completed collection times out
- **THEN** the collection remains available with Retry, Edit, and Cancel actions

### Requirement: Complete confirmation preview
The system SHALL show the full processed entry in Telegram-safe chunks with confirmation controls on the final chunk.

#### Scenario: Preview exceeds one Telegram message
- **WHEN** a generated confirmation exceeds Telegram's message limit
- **THEN** every chunk is within the limit and concatenating the chunks preserves the complete preview
