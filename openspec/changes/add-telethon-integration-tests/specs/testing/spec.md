## ADDED Requirements
### Requirement: Telethon integration harness
The project SHALL provide a Telethon-driven integration test harness that can send real Bot API updates to the running webhook and read replies for assertions while keeping the suite opt-in via environment variables.

#### Scenario: Harness runs when credentials provided
- **GIVEN** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and a target chat/user ID are set for testing
- **WHEN** the Telethon integration tests run
- **THEN** the harness SHALL connect to Telegram, send a command message to the bot via webhook delivery, and capture the bot’s reply for assertions

#### Scenario: Harness skips when credentials missing
- **GIVEN** the required Telegram credentials are absent or network access is unavailable
- **WHEN** the Telethon integration tests run
- **THEN** the suite SHALL skip gracefully without failing the test run

### Requirement: Core commands covered via Telethon
The Telethon integration suite SHALL cover core user-visible flows with deterministic expectations, stubbing external dependencies (LLM, STT, Sheets) as needed to make assertions stable.

#### Scenario: Start/help responses
- **WHEN** the Telethon test sends `/start` followed by `/help`
- **THEN** the bot SHALL return the localized welcome/help text without crashing, and the test SHALL assert key phrases are present

#### Scenario: Config flow validates sheet prompt
- **WHEN** the Telethon test sends `/config` in a chat with the bot
- **THEN** the bot SHALL prompt for a Google Sheet link/ID, and the test SHALL assert the prompt text is returned

#### Scenario: Habits draft confirmation with stubs
- **GIVEN** LLM/STT/Sheets are stubbed to deterministic outputs
- **WHEN** the Telethon test runs `/habits`, selects a date, and sends sample text
- **THEN** the bot SHALL return a draft JSON confirmation message and the test SHALL assert that the draft contains the sample text or stubbed fields
