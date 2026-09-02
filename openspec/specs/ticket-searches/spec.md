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
