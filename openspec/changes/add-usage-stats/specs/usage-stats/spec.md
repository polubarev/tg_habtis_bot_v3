## ADDED Requirements
### Requirement: Usage stats structure
The system SHALL store per-user usage counters in the user profile for tracked features: habits, dream, thought, reflection.

#### Scenario: New user profile has counters
- **WHEN** a new user profile is created
- **THEN** usage counters exist for habits, dream, thought, reflection and are initialized to 0

### Requirement: Increment on successful completion
The system SHALL increment the relevant usage counter when a user successfully completes a feature flow.

#### Scenario: Reflection saved increments counter
- **WHEN** a user confirms and saves a reflection entry
- **THEN** the reflection usage counter increments by 1

### Requirement: Content-free analytics
The system SHALL NOT store diary text, recordings, or extracted content inside usage statistics.

#### Scenario: Updating counters
- **WHEN** a usage counter is updated
- **THEN** only numeric counters are stored in usage statistics
