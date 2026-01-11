## ADDED Requirements

### Requirement: Weekly analysis entry point
The system SHALL provide a main-menu action to request a weekly analysis.

#### Scenario: User triggers weekly analysis
- **WHEN** the user taps the Week Analysis button
- **THEN** the system starts the weekly analysis flow

### Requirement: Use last 7 completed days of data
The system SHALL gather the last 7 completed days (ending yesterday in the user’s timezone) of habit entries (diary + habit fields) and include related dreams, thoughts, and reflections from the same dates.

#### Scenario: Collect week data
- **WHEN** the weekly analysis flow runs
- **THEN** the system loads the most recent 7 completed days from the user’s Habits sheet
- **AND** includes Dreams, Thoughts, and Reflections entries from the same dates

### Requirement: Localized LLM analysis
The system SHALL send the collected data to the LLM with a psychology and habit coach prompt in the user’s language.

#### Scenario: Generate weekly analysis
- **WHEN** the system submits week data to the LLM
- **THEN** the response is returned to the user in the selected language

### Requirement: Missing data handling
The system SHALL return a clear message when the sheet is not configured or insufficient data is available.

#### Scenario: Sheet not configured
- **WHEN** the user triggers weekly analysis without a configured sheet
- **THEN** the system responds with the sheet setup prompt

#### Scenario: Not enough entries
- **WHEN** fewer than 7 completed days are available
- **THEN** the system informs the user and indicates how many days are available
