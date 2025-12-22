## ADDED Requirements

### Requirement: Language selection on onboarding
The system SHALL prompt the user to select a language immediately after /start.

#### Scenario: User starts onboarding
- **WHEN** a new user runs /start
- **THEN** the bot prompts for language selection before continuing

### Requirement: Persisted language preference
The system SHALL persist the user’s selected language and use it for all messages.

#### Scenario: User picks Russian
- **WHEN** the user selects Russian during onboarding
- **THEN** all subsequent messages are in Russian

### Requirement: Language change in settings
The system SHALL allow changing the language from settings.

#### Scenario: User changes language later
- **WHEN** the user selects a new language in settings
- **THEN** subsequent messages use the new language and do not mix languages within a flow
