## ADDED Requirements

### Requirement: Compact grouped main menu
The system SHALL display a main reply keyboard with exactly two rows and four localized category buttons: Records and Review, followed by Tools and Settings.

#### Scenario: Open the main menu
- **WHEN** a user starts the bot or returns to the main menu
- **THEN** the reply keyboard displays the four categories in two rows in the user's selected language
- **AND** no individual action or Cancel button occupies an additional main-menu row

### Requirement: Grouped action access
The system SHALL expose all existing main-menu actions through their categories, with a Back button in each category. Records, Review, and Tools SHALL each use at most three rows.

#### Scenario: Open Records
- **WHEN** an idle user selects Records
- **THEN** the keyboard displays Habits / Day, Dream, Thought, Reflection, and Back

#### Scenario: Open Review
- **WHEN** an idle user selects Review
- **THEN** the keyboard displays Week Analysis, On this day, and Back

#### Scenario: Open Tools
- **WHEN** an idle user selects Tools
- **THEN** the keyboard displays Transcription, Help, and Back

#### Scenario: Open Settings
- **WHEN** an idle user selects Settings
- **THEN** the existing settings actions remain available

#### Scenario: Return from a category
- **WHEN** a user selects Back from a category
- **THEN** the system displays the two-row main menu

### Requirement: Existing flow compatibility
The system SHALL preserve existing slash commands, action labels in both supported languages, and input-flow cancellation. Category navigation SHALL NOT save category labels as entry content or discard unfinished input.

#### Scenario: Use an old keyboard
- **WHEN** an idle user selects an existing action label from a keyboard displayed before the update
- **THEN** the corresponding action still starts

#### Scenario: Cancel input
- **WHEN** a user cancels an active input flow using its Cancel button or `/cancel`
- **THEN** existing cancellation behavior is preserved and the compact main menu is displayed

#### Scenario: Category label during unfinished input
- **WHEN** a user sends a category label while an entry or transcription collection is active
- **THEN** the system keeps the unfinished input and asks the user to finish or cancel the active flow before navigating
- **AND** the category label is not appended to the entry
