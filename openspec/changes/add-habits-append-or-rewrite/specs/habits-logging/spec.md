## ADDED Requirements

### Requirement: Prompt on existing habits entry for selected date
The system SHALL detect existing Habits entries for the selected date and prompt the user to rewrite or append the most recent entry.

#### Scenario: Existing entry found
- **WHEN** a user selects a date that already has one or more Habits rows
- **THEN** the bot prompts for rewrite vs append and targets the most recent row for that date

### Requirement: Rewrite existing habits entry
The system SHALL replace the most recent Habits row for the selected date when the user chooses rewrite and SHALL set the timestamp to the current time.

#### Scenario: Rewrite choice
- **WHEN** the user chooses rewrite
- **THEN** the row is overwritten with the new raw record and extracted fields and the timestamp is updated to now

### Requirement: Append to existing habits entry
The system SHALL append new text to the existing raw record, reprocess extraction, and update the most recent Habits row for the selected date, setting the timestamp to the current time.

#### Scenario: Append choice
- **WHEN** the user chooses append
- **THEN** the system combines prior raw record with new input, re-extracts fields, and updates the same row with a refreshed timestamp
