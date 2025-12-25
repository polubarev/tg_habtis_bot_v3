## ADDED Requirements

### Requirement: Habit field editing
The system SHALL allow users to edit existing custom habit fields (name, description, type, minimum, maximum) through the habits config flow.

#### Scenario: Update a field attribute
- **WHEN** the user selects edit, chooses a custom field, and provides a new value
- **THEN** the bot updates the habit schema and confirms the change

### Requirement: Button-based habit field removal
The system SHALL present inline buttons to select a custom habit field for removal.

#### Scenario: Remove a field via button
- **WHEN** the user selects remove and taps a field button
- **THEN** the bot deletes the field and returns to the habit config menu
