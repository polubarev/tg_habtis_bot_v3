## ADDED Requirements

### Requirement: Direct voice transcription

The bot SHALL transcribe each standalone Telegram voice note and reply to that note using the existing transcription service. Active voice-input workflows and explicit transcription batches SHALL keep their normal handling.

#### Scenario: Several standalone notes

- **WHEN** the user sends one or more voice notes while the bot is idle
- **THEN** the bot replies to each note with its own transcript
- **AND** the transcripts leave the conversation idle

#### Scenario: Active voice input

- **WHEN** the user sends a voice note while Habits, Dream, Thought, or Reflect is accepting voice input
- **THEN** the bot uses the transcript as input to that step

#### Scenario: Explicit transcription batch

- **WHEN** the user sends a voice note after opening the Transcription tool
- **THEN** the tool collects the note in the current batch

#### Scenario: Step changes during transcription

- **WHEN** the user changes or closes the conversation step before transcription finishes
- **THEN** the bot returns the transcript and leaves the current step as it is
