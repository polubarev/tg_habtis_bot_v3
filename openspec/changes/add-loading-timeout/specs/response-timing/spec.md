## ADDED Requirements

### Requirement: Loading indicators for long operations
The system SHALL send a loading indicator message within 1–2 seconds when user-initiated operations start.

#### Scenario: Start processing user input
- **WHEN** the user submits a message that triggers a long-running operation
- **THEN** the bot sends a loading indicator (e.g., "Processing…") within 1–2 seconds

### Requirement: Timeout feedback
The system SHALL enforce a timeout threshold for long-running operations and return a human-readable timeout message on expiry.

#### Scenario: Operation exceeds timeout
- **WHEN** a long-running operation exceeds the timeout threshold
- **THEN** the user receives a timeout message and the conversation does not hang
