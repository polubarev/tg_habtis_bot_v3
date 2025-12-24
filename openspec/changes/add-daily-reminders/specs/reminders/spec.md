## ADDED Requirements

### Requirement: Daily reminder configuration
The system SHALL allow a user to configure a daily reminder time in Settings using the user's timezone.

#### Scenario: User sets a reminder time
- **WHEN** the user selects the reminders setting and submits a valid time (HH:MM)
- **THEN** the system saves the time and enables daily reminders for that user

#### Scenario: User disables reminders
- **WHEN** the user selects the reminders setting and submits a disable command
- **THEN** the system disables daily reminders for that user

### Requirement: Reminder delivery via Cloud Tasks
The system SHALL schedule reminders via Cloud Tasks so the service can be idle between reminders.

#### Scenario: Reminder task executes
- **WHEN** a scheduled reminder task runs
- **THEN** the system sends a reminder message to the user and schedules the next daily reminder

### Requirement: Localized reminder message
The system SHALL send reminder messages in the user's language.

#### Scenario: User has Russian language
- **WHEN** a reminder is sent
- **THEN** the user receives the Russian reminder message
