## ADDED Requirements

### Requirement: Stable entry identity
Every newly created habits, dream, thought, and reflection entry SHALL have a stable UUID that is stored in its Google Sheets row.

#### Scenario: Migrate an existing sheet
- **WHEN** a sheet without `entry_id` is used for a new write
- **THEN** the header is appended without reordering existing columns and historical rows remain unchanged

### Requirement: Idempotent save retry
The system SHALL reuse the same entry UUID and reconcile the sheet before retrying an ambiguous write.

#### Scenario: Previous append succeeded but response timed out
- **WHEN** the user retries saving and a row with the same entry UUID already exists
- **THEN** the system treats the entry as saved and does not intentionally append another row
