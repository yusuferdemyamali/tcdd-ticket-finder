## ADDED Requirements

### Requirement: Monitoring metadata updates are durable
The ticket-search domain SHALL provide durable updates for monitoring metadata needed to resume polling and outage behavior after process restart.

Updates to `last_checked_at`, `last_successful_check_at`, `next_check_at`, `last_tcdd_error_at`, and `tcdd_outage_notified` SHALL be persisted through the ticket-search domain boundary before monitoring relies on the updated values.

#### Scenario: Check timestamps are persisted through domain behavior
- **WHEN** monitoring records a real TCDD check attempt for a search
- **THEN** the ticket-search domain persists `last_checked_at`
- **AND** the updated value is visible through a later read using a new process or database connection

#### Scenario: Successful check timestamp is only success metadata
- **WHEN** monitoring records a successful real TCDD check for a search
- **THEN** the ticket-search domain persists `last_successful_check_at`
- **AND** failed TCDD checks do not advance `last_successful_check_at`

#### Scenario: Next check is persisted for restart recovery
- **WHEN** monitoring schedules the next check for an `ACTIVE` search
- **THEN** the ticket-search domain persists `next_check_at`
- **AND** startup recovery can read that timestamp after process restart

### Requirement: Persisted outage state can be set and cleared
The ticket-search domain SHALL provide durable behavior for setting and clearing TCDD outage notification state without requiring Telegram handlers or the TCDD provider to write SQLite directly.

#### Scenario: Outage notification state is set durably
- **WHEN** monitoring records that a TCDD outage notification was sent for a search
- **THEN** the ticket-search domain persists `tcdd_outage_notified` as true
- **AND** the updated value is visible after process restart

#### Scenario: Last TCDD error time is persisted durably
- **WHEN** monitoring records a TCDD failure for a search
- **THEN** the ticket-search domain persists `last_tcdd_error_at`
- **AND** the updated value is visible after process restart

#### Scenario: Outage state is cleared after recovery
- **WHEN** monitoring records TCDD recovery for a search after a successful check
- **THEN** the ticket-search domain clears `tcdd_outage_notified`
- **AND** a later independent outage can be recorded as a new outage period

### Requirement: Found notification retry data is durable
The ticket-search domain SHALL persist enough found-event data before found-ticket notification delivery so a `FOUND` search can retry that notification after process restart without depending on process memory.

The persisted data SHALL be limited to the search and eligible normalized train details needed to rebuild the existing found-ticket notification, and SHALL NOT expose raw TCDD response shapes to Telegram or monitoring callers.

#### Scenario: Found event details survive restart
- **WHEN** monitoring marks an `ACTIVE` search as `FOUND` because one or more eligible trains were found
- **THEN** the ticket-search domain persists the found-event train details needed for notification retry
- **AND** those details are visible through a later read using a new process or database connection

#### Scenario: Found event persistence does not leak raw TCDD response
- **WHEN** found-event details are stored for retry
- **THEN** the stored data contains only normalized train notification fields
- **AND** it does not store raw TCDD availability response objects

#### Scenario: Completed retry data is no longer active recovery work
- **WHEN** a `FOUND` search notification succeeds and the search transitions to `COMPLETED`
- **THEN** the search is no longer returned as found-notification recovery work

### Requirement: Restart recovery reads non-terminal monitoring state
The ticket-search domain SHALL expose persisted searches that require monitoring recovery without relying on process memory.

Recovery-required searches SHALL include `ACTIVE` searches for polling continuation and `FOUND` searches for found-ticket notification retry. Searches in `COMPLETED`, `CANCELLED`, and `EXPIRED` SHALL NOT be returned as monitoring-recovery work.

#### Scenario: Active search is returned for recovery
- **WHEN** a persisted search has status `ACTIVE`
- **THEN** monitoring recovery lookup returns that search for polling continuation

#### Scenario: Found search is returned for notification retry
- **WHEN** a persisted search has status `FOUND`
- **THEN** monitoring recovery lookup returns that search for found-ticket notification retry

#### Scenario: Terminal searches are excluded from recovery
- **WHEN** persisted searches have status `COMPLETED`, `CANCELLED`, or `EXPIRED`
- **THEN** monitoring recovery lookup does not return those searches as recovery work
