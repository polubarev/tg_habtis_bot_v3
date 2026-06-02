## ADDED Requirements
### Requirement: Content-free usage event storage
The system SHALL store usage events for admin analytics without storing user-generated content.

#### Scenario: Feature save recorded
- **WHEN** a user successfully saves a habits, dream, thought, or reflection entry
- **THEN** the system records a usage event with user id, feature name, timestamp, day, week, and month
- **AND** the event does not include diary text, extracted habit data, dream text, thought text, reflection answers, voice transcript, or feedback message text

### Requirement: Period admin stats
The system SHALL allow admins to view usage statistics for Today, This Week, This Month, and Last 30 Days.

#### Scenario: Admin requests weekly stats
- **GIVEN** the user is an admin
- **WHEN** the user selects weekly stats
- **THEN** the bot shows active users, new users, feature usage counts, voice usage, feedback count, and broadcast counts for the current UTC week

### Requirement: Unique user metrics
The system SHALL report unique users for selected analytics periods.

#### Scenario: Same user has multiple events
- **GIVEN** one user has multiple usage events in the selected period
- **WHEN** admin stats are aggregated
- **THEN** that user counts once in active users

### Requirement: New user metrics
The system SHALL report new users for selected analytics periods based on user profile creation time.

#### Scenario: User created inside period
- **GIVEN** a user profile has `created_at` inside the selected period
- **WHEN** admin stats are aggregated
- **THEN** that user is counted as a new user for the period

### Requirement: Graceful analytics degradation
The system SHALL degrade gracefully when usage event storage is unavailable.

#### Scenario: Storage unavailable
- **GIVEN** usage event storage is unavailable
- **WHEN** an admin requests period stats
- **THEN** the bot shows an analytics-unavailable message and does not crash
