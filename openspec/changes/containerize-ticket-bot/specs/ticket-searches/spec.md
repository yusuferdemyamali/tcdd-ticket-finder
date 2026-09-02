## ADDED Requirements

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
