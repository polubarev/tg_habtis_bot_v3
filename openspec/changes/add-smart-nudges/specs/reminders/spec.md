## ADDED Requirements

### Requirement: Smart nudges configuration
The system SHALL allow a user to enable and configure Smart nudges with multiple times per day.

#### Scenario: User enables smart nudges with times
- **WHEN** the user enables Smart nudges and provides a list of valid times (HH:MM)
- **THEN** the system stores the times and enables Smart nudges for that user
- **AND** the system schedules the next nudge execution via Cloud Tasks

#### Scenario: User disables smart nudges
- **WHEN** the user disables Smart nudges
- **THEN** the system disables Smart nudges for that user
- **AND** any scheduled Smart nudges task is deleted or allowed to expire safely

### Requirement: Rollover-based due day
The system SHALL determine the nudge "due day" using a user-configurable rollover time (default `12:00`) in the user’s timezone.

#### Scenario: Before rollover, due day is yesterday
- **GIVEN** the user’s local time is before rollover
- **WHEN** the system evaluates Smart nudges
- **THEN** the due day is yesterday (local date)

#### Scenario: After rollover, due day is today
- **GIVEN** the user’s local time is after rollover
- **WHEN** the system evaluates Smart nudges
- **THEN** the due day is today (local date)

### Requirement: Conditional send based on logged date
The system SHALL send a Smart nudge only when there is no saved Habits entry for the current due day.

#### Scenario: Skip when due day is already logged
- **GIVEN** the user has saved a Habits entry for the due day
- **WHEN** a Smart nudge task executes
- **THEN** the system does not send a nudge message
- **AND** the system schedules the next Smart nudge task

#### Scenario: Send when due day is missing
- **GIVEN** the user has not saved a Habits entry for the due day
- **WHEN** a Smart nudge task executes
- **THEN** the system sends a localized nudge message indicating which day is missing
- **AND** the system schedules the next Smart nudge task

### Requirement: Logging yesterday after rollover does not satisfy today
The system SHALL continue nudges for today after rollover even if the user logs yesterday later in the same day.

#### Scenario: User logs yesterday after rollover
- **GIVEN** the current local time is after rollover (so the due day is today)
- **WHEN** the user saves a Habits entry for yesterday
- **THEN** Smart nudges remain eligible for today until a Habits entry for today is saved

### Requirement: Smart nudges delivery via Cloud Tasks
The system SHALL schedule Smart nudges via Cloud Tasks and reschedule exactly one next task per user after each execution.

#### Scenario: Task executes and reschedules next run
- **WHEN** a Smart nudge task executes
- **THEN** the system evaluates whether to send a nudge
- **AND** the system schedules the next Smart nudge task at the next configured time

