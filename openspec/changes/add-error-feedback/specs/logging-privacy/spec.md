## ADDED Requirements

### Requirement: Exclude private entry content from logs
The system SHALL NOT log diary text, dreams, thoughts, reflection answers, voice transcripts, prompts containing user content, or extracted field values.

#### Scenario: Debug logging is enabled
- **WHEN** application debug logging is enabled and an external SDK processes an entry
- **THEN** logs contain only operation metadata, latency, status, identifiers, and exception types
- **AND** no user-provided or generated entry content appears
