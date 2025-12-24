## ADDED Requirements

### Requirement: Transient progress messages are removed
The system SHALL remove transient progress messages (for example: processing or saving) after completion or error outcomes to reduce chat clutter.

#### Scenario: External call succeeds
- **WHEN** the bot posts a progress message and the operation succeeds
- **THEN** the bot deletes the progress message before sending the final status

#### Scenario: External call fails
- **WHEN** the bot posts a progress message and the operation fails
- **THEN** the bot deletes the progress message before sending the error status
