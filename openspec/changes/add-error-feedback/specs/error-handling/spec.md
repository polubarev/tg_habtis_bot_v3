## ADDED Requirements

### Requirement: Surface Google Sheets write failures
The system SHALL detect Google Sheets write failures and return a human-readable error message with next steps.

#### Scenario: Sheets write failure
- **WHEN** a write to Google Sheets fails due to permission, access, or API error
- **THEN** the user receives a clear error message (e.g., instructing to check sharing/permissions) and the conversation does not hang

### Requirement: Surface network/server timeouts
The system SHALL detect network/server timeouts from external services and return a human-readable error message with next steps.

#### Scenario: External timeout
- **WHEN** an external request times out (Sheets, LLM, transcription, or other service)
- **THEN** the user receives a clear error message suggesting a retry and the conversation does not hang

### Requirement: Surface invalid external responses
The system SHALL detect invalid external responses and return a human-readable error message with next steps.

#### Scenario: Invalid response payload
- **WHEN** an external service returns an invalid or malformed response that cannot be processed
- **THEN** the user receives a clear error message suggesting to retry or adjust inputs and the conversation does not hang

### Requirement: Surface Telegram delivery failures
The system SHALL provide a short localized fallback when a generated response cannot be delivered and SHALL retain any retryable draft.

#### Scenario: Confirmation delivery fails
- **WHEN** a processed entry cannot be delivered to Telegram
- **THEN** the progress response becomes a recovery message with retry, edit, and cancel actions
- **AND** the processed draft remains available without repeating completed external work

### Requirement: Preserve retryable save state
The system SHALL retain a pending entry when a Google Sheets save fails.

#### Scenario: Save timeout
- **WHEN** a pending entry cannot be confirmed as saved because the Sheets request times out
- **THEN** the user receives retry, edit, and cancel actions
- **AND** retrying reuses the same entry identifier

### Requirement: Complete progress messages
The system SHALL keep a progress message visible until a success or failure response has been delivered.

#### Scenario: Failure after processing
- **WHEN** processing succeeds but response delivery fails
- **THEN** the progress message is not silently deleted
