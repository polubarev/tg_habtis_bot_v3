## ADDED Requirements

### Requirement: Non-technical input guidance for habit field types
The system SHALL explain expected data type formats in simple language before requesting a value and provide a valid example.

#### Scenario: User adds a new habit field
- **WHEN** the user reaches the field type step
- **THEN** the bot explains allowed types in non-technical terms and shows an example

### Requirement: Instructional validation errors
The system SHALL return validation errors that explain what was wrong and what format is expected.

#### Scenario: User enters an invalid type or numeric limit
- **WHEN** the user submits an invalid type or invalid min/max value
- **THEN** the bot responds with a clear explanation of the issue and the expected format

### Requirement: Simplified JSON import guidance
The system SHALL provide a simplified JSON import explanation with a valid example.

#### Scenario: User chooses JSON import
- **WHEN** the user requests JSON import for habit fields
- **THEN** the bot shows a short, non-technical explanation and a valid JSON example
