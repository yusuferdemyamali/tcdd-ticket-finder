## Purpose

Provide durable ticket-search lifecycle behavior for the MVP so Telegram handlers and background monitoring can later share one restart-safe search state without depending on TCDD response internals.

## Requirements

### Requirement: Ticket searches are durably stored
The system SHALL persist ticket-search records in SQLite as the source of truth for critical state.

Each persisted ticket search SHALL retain, at minimum, the following fields in a round-trippable form: id, origin station id, origin station name, destination station id, destination station name, travel date, departure time from, departure time to, status, last checked at, last successful check at, next check at, TCDD outage notified flag, last TCDD error at, found at, completed at, cancelled at, expired at, created at, and updated at.

#### Scenario: Database can be initialized
- **WHEN** the application initializes an empty SQLite database for ticket searches
- **THEN** the database contains the table and constraints needed to persist ticket searches

#### Scenario: Search can be saved and read
- **WHEN** a valid ticket search is created
- **THEN** the search is stored durably with status `ACTIVE`
- **AND** reading the search by id returns the stored route, travel date, departure time window, status, metadata, and timestamps

#### Scenario: Search survives a new connection
- **WHEN** a ticket search has been stored and the current process or database connection is replaced
- **THEN** a new database connection can read the same search state from SQLite

#### Scenario: State is not memory-only
- **WHEN** a search status or critical timestamp changes
- **THEN** the changed value is persisted to SQLite before it is treated as the current search state

### Requirement: Search creation validates MVP inputs
The system SHALL accept only a single-user, one-passenger, one-way ticket search with one origin station, one destination station, one travel date, and one inclusive departure time window.

All date and time evaluation SHALL use `Europe/Istanbul` local time.

#### Scenario: Valid search is accepted
- **WHEN** a search is requested for a travel date that is today or later in `Europe/Istanbul` and a departure window where `departure_time_from` is less than or equal to `departure_time_to`
- **THEN** the system creates an `ACTIVE` ticket search

#### Scenario: Past travel date is rejected
- **WHEN** a search is requested for a travel date earlier than the current date in `Europe/Istanbul`
- **THEN** the system rejects the search without creating an `ACTIVE` record

#### Scenario: Midnight-crossing range is rejected
- **WHEN** a search is requested with `departure_time_from` later than `departure_time_to`
- **THEN** the system rejects the search because midnight-crossing departure windows are not supported

#### Scenario: Departure window boundaries are inclusive
- **WHEN** a stored search has `departure_time_from` of `08:00` and `departure_time_to` of `10:00`
- **THEN** a departure at `08:00` is inside the window
- **AND** a departure at `10:00` is inside the window
- **AND** departures before `08:00` or after `10:00` are outside the window

### Requirement: Only one search can be ACTIVE
The system SHALL prevent more than one `ACTIVE` ticket search from existing at the same time.

This invariant SHALL be protected by persistent storage constraints and by service-level behavior so it remains valid across multiple database connections.

#### Scenario: Second active search is rejected
- **WHEN** an `ACTIVE` search already exists
- **AND** another search is created without replacing the active search
- **THEN** the system rejects the second active search
- **AND** the existing `ACTIVE` search remains unchanged

#### Scenario: Active search lookup returns the single active search
- **WHEN** exactly one `ACTIVE` search exists
- **THEN** active search lookup returns that search

#### Scenario: Active search lookup returns none when inactive
- **WHEN** no search has status `ACTIVE`
- **THEN** active search lookup returns no search

### Requirement: Active search replacement is atomic
The system SHALL replace an existing `ACTIVE` search by cancelling the old active search and creating the new active search as one consistent operation.

#### Scenario: Existing active search is replaced
- **WHEN** an `ACTIVE` search exists
- **AND** a valid replacement search is requested
- **THEN** the old search is persisted with status `CANCELLED` and `cancelled_at` set
- **AND** the replacement search is persisted with status `ACTIVE`
- **AND** no momentary or final state with multiple `ACTIVE` searches is committed

#### Scenario: Replacement rollback preserves consistency
- **WHEN** replacing an active search cannot be fully persisted
- **THEN** the database is not left with both searches active or with the old active search cancelled without the replacement search

### Requirement: Search lifecycle uses only allowed states and transitions
The system SHALL support only the statuses `ACTIVE`, `FOUND`, `COMPLETED`, `CANCELLED`, and `EXPIRED`.

The system SHALL centrally validate state transitions and reject invalid transitions instead of accepting them silently.

#### Scenario: Found search can be completed
- **WHEN** an `ACTIVE` search is marked as found
- **THEN** its status becomes `FOUND` and `found_at` is set
- **WHEN** that `FOUND` search is marked as completed
- **THEN** its status becomes `COMPLETED` and `completed_at` is set

#### Scenario: Active search can be cancelled
- **WHEN** an `ACTIVE` search is cancelled
- **THEN** its status becomes `CANCELLED` and `cancelled_at` is set

#### Scenario: Active search can expire
- **WHEN** an `ACTIVE` search is expired
- **THEN** its status becomes `EXPIRED` and `expired_at` is set

#### Scenario: Completed search can restart before travel window has passed
- **WHEN** a `COMPLETED` search is restarted before the stored travel date and inclusive departure window end have passed in `Europe/Istanbul`
- **THEN** its status becomes `ACTIVE`
- **AND** the single-`ACTIVE` invariant still holds

#### Scenario: Completed search cannot restart after travel window has passed
- **WHEN** a `COMPLETED` search is restarted after the stored travel date and inclusive departure window end have passed in `Europe/Istanbul`
- **THEN** the system rejects the restart
- **AND** the search remains `COMPLETED`

#### Scenario: Invalid transition is rejected
- **WHEN** a transition outside `ACTIVE -> FOUND`, `FOUND -> COMPLETED`, `COMPLETED -> ACTIVE`, `ACTIVE -> CANCELLED`, or `ACTIVE -> EXPIRED` is requested
- **THEN** the system rejects the transition
- **AND** the persisted status remains unchanged

### Requirement: Ticket-search persistence remains integration-independent
The system SHALL keep ticket-search persistence and lifecycle behavior independent from Telegram, background scheduling, TCDD polling, TCDD outage or recovery notifications, Docker deployment, and raw TCDD provider response shapes.

#### Scenario: Search persistence initializes without external integrations
- **WHEN** ticket-search persistence is initialized or tested
- **THEN** it does not require Telegram handlers, background scheduler components, TCDD polling, notification delivery, Docker deployment, or Playwright automation to be imported or initialized

#### Scenario: TCDD provider remains decoupled
- **WHEN** the TCDD provider package is imported or tested
- **THEN** it does not depend on ticket-search SQLite persistence or Telegram bot behavior

### Requirement: Monitoring lifecycle results are persisted safely
The system SHALL persist monitoring-driven lifecycle outcomes through the ticket-search domain boundary so notification and polling behavior can rely on durable state.

Monitoring-driven completion SHALL require the search to already be `FOUND`, and restart shall only reactivate the callback's own persisted `COMPLETED` search before its travel window has passed in `Europe/Istanbul`.

#### Scenario: Found search can be completed after notification
- **WHEN** a monitoring flow has persisted a search as `FOUND`
- **AND** the found-ticket notification has been sent successfully
- **THEN** the domain can persist that same search as `COMPLETED`

#### Scenario: Active search cannot skip found before completion
- **WHEN** a monitoring flow attempts to complete a search that is still `ACTIVE`
- **THEN** the domain rejects the completion
- **AND** the persisted status remains unchanged

#### Scenario: Restart targets the callback search only
- **WHEN** a restart is requested for a persisted search id
- **AND** that search is `COMPLETED`
- **AND** its travel window has not passed in `Europe/Istanbul`
- **THEN** that same search becomes `ACTIVE`
- **AND** no unrelated search is activated

#### Scenario: Expired active search is persisted
- **WHEN** an `ACTIVE` search travel window has passed in `Europe/Istanbul`
- **THEN** the domain can persist that search as `EXPIRED`
- **AND** later active-search lookup does not return the expired search

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

### Requirement: Containerized SQLite path preserves ticket-search state
The system SHALL allow the SQLite database path used for ticket-search persistence to be configured to a container-mounted persistent volume location.

Ticket-search records stored at that configured path SHALL remain readable after the application process restarts or the container is recreated while the persistent volume is retained.

#### Scenario: Active search survives container restart
- **WHEN** an `ACTIVE` ticket search has been persisted to SQLite under the configured persistent volume path
- **AND** the application container restarts
- **THEN** the restarted application can read the same `ACTIVE` search from SQLite

#### Scenario: Found search survives container recreate
- **WHEN** a `FOUND` ticket search has been persisted to SQLite under the configured persistent volume path
- **AND** the application container is recreated while the persistent volume remains
- **THEN** the recreated application can read the same `FOUND` search from SQLite

#### Scenario: Volume path remains the source of truth
- **WHEN** `DATABASE_PATH` points to the mounted persistent volume database file
- **THEN** ticket-search lifecycle state is read from and written to that database file instead of process memory or an ephemeral container filesystem path
