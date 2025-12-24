## ADDED Requirements

### Requirement: Habit field type selection uses buttons
The system SHALL present a localized inline button list for habit field type selection, with user-friendly labels and examples, and accept the selected type without requiring free-text input.

#### Scenario: User adds a habit field and selects type
- **WHEN** the user reaches the type selection step
- **THEN** the bot shows inline buttons for string, integer, number, and boolean types with localized labels and examples
- **AND** selecting a button sets the type and advances the flow

### Requirement: Remove prompt shows custom fields
The system SHALL display the current list of custom habit fields when prompting the user to remove a field, excluding base sheet columns.

#### Scenario: User chooses remove
- **WHEN** the user selects the remove action
- **THEN** the bot shows the existing custom field names or indicates the list is empty

### Requirement: Return to habits config menu after add
The system SHALL return the user to the habits config menu after successfully adding a new habit field.

#### Scenario: User completes add flow
- **WHEN** a new habit field is saved
- **THEN** the bot sends the habits config menu in the current language
