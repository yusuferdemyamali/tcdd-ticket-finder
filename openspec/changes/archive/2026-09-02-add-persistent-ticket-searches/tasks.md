## 1. Persistence Foundation

- [x] 1.1 Create the `app/ticket_searches/` package with `TicketSearch`, `TicketSearchStatus`, and domain exceptions, and verify `python -c "from app.ticket_searches import TicketSearchStatus"` succeeds without importing `app.tcdd`.
- [x] 1.2 Implement idempotent SQLite initialization for `ticket_searches` with all required columns, status `CHECK`, and one-`ACTIVE` partial unique index, and verify a schema test can inspect the table and index from an empty database.
- [x] 1.3 Implement focused `TicketSearchRepository` insert/read/update helpers and row mapping, and verify a search saved through one connection can be read through a new database connection.

## 2. Search Validation

- [x] 2.1 Implement `TicketSearchService.create_search`, `get_search`, and `get_active_search` with `Europe/Istanbul` date evaluation, and verify tests cover successful creation plus no-active lookup.
- [x] 2.2 Reject invalid creation inputs for past Istanbul travel dates and `departure_time_from > departure_time_to`, and verify tests assert no `ACTIVE` record is created after each rejection.
- [x] 2.3 Add inclusive departure-window matching behavior and verify tests cover departures exactly at `departure_time_from`, exactly at `departure_time_to`, inside, before, and after the window.
- [x] 2.4 Enforce the single-`ACTIVE` invariant in service code and SQLite, and verify tests reject a second active search including a direct repository/database conflict path.

## 3. State Machine

- [x] 3.1 Implement centralized transition validation for only `ACTIVE -> FOUND`, `FOUND -> COMPLETED`, `COMPLETED -> ACTIVE`, `ACTIVE -> CANCELLED`, and `ACTIVE -> EXPIRED`, and verify an invalid transition test leaves persisted status unchanged.
- [x] 3.2 Implement `mark_found` and `mark_completed`, and verify tests cover the `ACTIVE -> FOUND -> COMPLETED` flow with `found_at` and `completed_at` persisted.
- [x] 3.3 Implement `cancel_search` and `expire_search`, and verify tests cover `ACTIVE -> CANCELLED` and `ACTIVE -> EXPIRED` with lifecycle timestamps persisted.
- [x] 3.4 Implement `restart_search` for `COMPLETED -> ACTIVE` only when the Istanbul local time has not passed `travel_date + departure_time_to`, and verify tests cover successful restart, expired-window rejection, lifecycle timestamp clearing, and active-conflict rejection.
- [x] 3.5 Implement `replace_active_search` as one SQLite transaction that cancels the old active search and creates the new active search, and verify tests cover old `CANCELLED`, new `ACTIVE`, no double-active state, and rollback consistency on failure.

## 4. Verification

- [x] 4.1 Add focused unit tests for the ticket-search repository and service acceptance criteria, and verify `pytest tests/test_ticket_searches.py` passes.
- [x] 4.2 Verify existing TCDD provider behavior is unchanged by running `pytest tests/test_tcdd_provider.py`.
- [x] 4.3 Run the full test suite with `pytest` and verify all existing and new tests pass.
- [x] 4.4 Validate the change artifacts with `openspec validate --changes add-persistent-ticket-searches --strict` and resolve any planning validation errors.
