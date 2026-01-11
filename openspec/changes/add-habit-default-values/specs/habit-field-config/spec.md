## ADDED Requirements

### Requirement: Habit field default values
The system SHALL allow users to define a default value per custom habit field and validate it against the field type and numeric min/max constraints.

#### Scenario: Set default during add flow
- **WHEN** a user adds a habit field and provides a default value
- **THEN** the bot validates the default against the field type and min/max limits
- **AND** saves the default with the field if valid

#### Scenario: Set default during edit flow
- **WHEN** a user edits a habit field default value
- **THEN** the bot validates and updates the default
- **AND** allows clearing the default value

### Requirement: Apply defaults to missing habit values
The system SHALL replace extracted habit values that are None with the configured default for that field.

#### Scenario: LLM returns None and a default exists
- **WHEN** the extractor returns None for a habit field with a default value
- **THEN** the entry uses the default value for storage and sheet output

#### Scenario: LLM returns explicit values
- **WHEN** the extractor returns 0, false, or an empty string for a habit field
- **THEN** the entry keeps the explicit value without applying the default

### Requirement: Draft preview marks defaulted fields
The system SHALL annotate draft previews with a default marker only for fields where a default was applied.

#### Scenario: Preview shows default marker
- **WHEN** a default value is applied for a field
- **THEN** the draft preview appends "(по умолчанию)" or "(default)" based on language
- **AND** the stored value does not include the marker

#### Scenario: Preview shows missing value
- **WHEN** no value is extracted and no default is configured
- **THEN** the draft preview shows "-"
