## ADDED Requirements
### Requirement: List habit field configuration
The system SHALL allow habit fields with type `list` to define allowed options and a selection mode (single or multiple).

#### Scenario: Add list field with options
- **WHEN** a user configures a habit field with type `list`
- **THEN** the system stores the options and the selected mode with the field definition

### Requirement: List habit extraction strictness
The system SHALL populate list-type fields using only the configured options, and set the value to null when no option matches.

#### Scenario: Extract single-select list value
- **WHEN** a habit entry mentions a value that matches an allowed option
- **THEN** the extracted value equals that option

#### Scenario: Extract missing list value
- **WHEN** a habit entry does not mention any allowed option
- **THEN** the extracted value is null

### Requirement: List options in habit hints
The system SHALL show list field options in the habit-fields hint shown before a daily entry.

#### Scenario: Hint includes list options
- **WHEN** a user starts the habits flow with a list-type field configured
- **THEN** the hint includes the allowed options for that field
