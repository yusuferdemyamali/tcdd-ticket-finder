## Why

The application needs a restart-safe ticket-search domain before Telegram handlers and background monitoring can coordinate on the same search state. Persisting search state in SQLite prevents active or found searches from being lost when the process or container restarts.

## What Changes

- Add a persistent ticket-search domain model with the MVP search fields and allowed lifecycle states.
- Add SQLite database initialization for a `ticket_searches` table that stores critical search state and polling metadata.
- Add a focused `TicketSearchRepository` for durable reads and writes, without generic repository abstractions.
- Add a `TicketSearchService` that centrally validates search creation, replacement, restart, cancellation, found, completed, and expiry transitions.
- Enforce the single ACTIVE search invariant at the service and database levels.
- Keep Telegram, scheduler, polling, notification, Docker, and TCDD provider changes out of scope.

## Capabilities

### New Capabilities
- `ticket-searches`: Persistent ticket-search lifecycle, SQLite storage, and service-level state-machine behavior for the MVP.

### Modified Capabilities
- None.

## Impact

- Affected code areas: new application-layer modules outside `app/tcdd`, SQLite initialization, and unit tests for persistence and domain behavior.
- Affected systems: local SQLite database only.
- Dependencies: use Python standard-library SQLite and time-zone support; do not add a new runtime dependency unless implementation proves it necessary.
- Explicitly not affected: `app/tcdd` provider behavior, Telegram bot flow, background scheduler, TCDD polling, notification messaging, and Docker deployment.
