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
