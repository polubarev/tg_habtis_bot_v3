## ADDED Requirements

### Requirement: Unified structured entry processing
The system SHALL process each completed collection or addition using one LLM
request with entry-scoped message context and SHALL request a single structured
response containing the full enabled diary and configured habit values. Original
user turns MUST remain available as factual evidence independently of prior
assistant drafts. The application SHALL validate the response and handle output
truncation as a processing failure.

#### Scenario: Addition follows a previous structured draft
- **WHEN** the user adds text after reviewing a draft
- **THEN** the request includes original input, previous structured draft context,
  and the new addition, and one response updates the diary and habits together

#### Scenario: Start another date or rewrite an entry
- **WHEN** the user starts an entry for another date or chooses rewrite
- **THEN** the bot initializes fresh entry context without unrelated conversation history

### Requirement: Separate original input from the readable diary
The system SHALL preserve all accepted original text and voice transcripts in
`raw_record` and SHALL generate a separate readable diary when diary is enabled.
The diary MUST retain narrative facts, detail, language, voice, and uncertainty
without inventing information or summarizing the entry.

#### Scenario: Initial diary with habit fields
- **WHEN** the user submits narrative text and configured habit values
- **THEN** extraction uses original input and the diary preserves the narrative
  independently of `raw_record`

#### Scenario: Only the diary field is configured
- **WHEN** diary is enabled and there are no custom habit fields
- **THEN** diary composition still runs

#### Scenario: Diary is disabled
- **WHEN** the user submits an entry with diary disabled
- **THEN** original input and configured habits are processed without composing a diary

### Requirement: Integrate diary additions naturally
The system SHALL integrate additions into the current diary at the appropriate
time or topic when explicitly supported by context, and SHALL otherwise add a
natural paragraph. It MUST preserve prior narrative unless the user explicitly
corrects it and MUST omit application-generated update labels from composed prose.

#### Scenario: Add a morning event after an evening paragraph
- **WHEN** a diary describes morning and evening and an addition explicitly
  describes another morning event
- **THEN** the new event is integrated next to the morning content and the evening
  content is retained

#### Scenario: Repeat additions before confirmation
- **WHEN** the user adds content over several draft confirmation rounds
- **THEN** each new diary includes all earlier narrative and the latest addition
  without duplicating content

#### Scenario: Append to a saved entry
- **WHEN** the user chooses append for a saved entry whose diary differs from raw text
- **THEN** composition receives the existing diary and the new addition, original
  text remains preserved, and confirmation updates the selected existing row

#### Scenario: Ambiguous placement
- **WHEN** the addition has no clear time or relation to an existing passage
- **THEN** the diary includes it as a natural paragraph without invented chronology

### Requirement: Distinguish field commands from narrative
The system SHALL apply explicit habit-field instructions to configured fields
without copying those commands into the diary. Narrative experiences and feelings
MUST remain in the diary even when they also supply habit values.

#### Scenario: Ratings-only addition
- **WHEN** the user adds "Настроение 2, важность дня 2" to an existing diary
- **THEN** the configured ratings are updated and the narrative stays unchanged

#### Scenario: Addition contains both experience and commands
- **WHEN** an addition contains a personal event and an explicit score-setting instruction
- **THEN** the event is integrated into the diary and the instruction updates the field

### Requirement: Lossless composition fallback and confirmation
The system SHALL show the complete diary preview before saving. If composition
fails or is unavailable, it SHALL retain the prior diary and verbatim new input,
or all original input for an initial entry, and display a localized fallback notice.
It MUST NOT overwrite the original text with model output.

#### Scenario: Composition times out
- **WHEN** a new addition cannot be composed within the timeout
- **THEN** the preview contains the prior diary and complete addition separated by
  a paragraph break, with a notice that automatic integration failed

#### Scenario: Retry a confirmed save
- **WHEN** a save fails and the user retries
- **THEN** the already confirmed diary is reused without recomposition
