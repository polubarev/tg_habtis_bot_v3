## ADDED Requirements
### Requirement: Feedback capture from settings menu
The system SHALL provide a feedback option in the settings menu that prompts the user for a free-text message and treats the next message as feedback.

#### Scenario: Feedback submitted
- **WHEN** the user selects Feedback and sends a message
- **THEN** the bot acknowledges receipt and returns the main menu keyboard

### Requirement: Feedback persistence
The system SHALL store feedback entries in Firestore with user metadata and a timestamp.

#### Scenario: Firestore available
- **WHEN** feedback is submitted and Firestore is configured
- **THEN** the feedback entry is persisted with user id, username, language, message, and created_at

#### Scenario: Firestore unavailable
- **WHEN** feedback is submitted and Firestore is unavailable
- **THEN** the bot informs the user that saving failed and does not crash
