## ADDED Requirements
### Requirement: Env-configured admin access
The system SHALL grant admin access only to Telegram user IDs configured in environment settings.

#### Scenario: Configured admin opens admin menu
- **GIVEN** the user's Telegram ID is configured as an admin
- **WHEN** the user sends `/admin`
- **THEN** the bot shows the admin menu

#### Scenario: Non-admin opens admin menu
- **GIVEN** the user's Telegram ID is not configured as an admin
- **WHEN** the user sends `/admin`
- **THEN** the bot refuses access and does not show admin actions

### Requirement: Admin stats
The system SHALL allow admins to view aggregate operational stats without diary or habit content.

#### Scenario: Admin requests stats
- **GIVEN** the user is an admin
- **WHEN** the user selects the stats action
- **THEN** the bot shows total users, connected-sheet users, and aggregate usage counters

### Requirement: Admin feedback viewer
The system SHALL allow admins to view recent feedback entries.

#### Scenario: Admin requests feedback
- **GIVEN** the user is an admin
- **WHEN** the user selects the feedback action
- **THEN** the bot shows recent feedback entries with user metadata, timestamp, and message text

### Requirement: Confirmed broadcast
The system SHALL allow admins to broadcast a message to users only after a preview and explicit confirmation.

#### Scenario: Admin confirms broadcast
- **GIVEN** the user is an admin and has entered a broadcast message
- **WHEN** the bot shows a preview and the admin confirms
- **THEN** the bot sends the message to users and reports sent and failed counts

#### Scenario: Admin cancels broadcast
- **GIVEN** the user is an admin and has entered a broadcast message
- **WHEN** the bot shows a preview and the admin cancels
- **THEN** the bot does not send the broadcast
