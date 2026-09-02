## Context

See `proposal.md` for motivation. The current application has an isolated `app/tcdd` provider and no durable ticket-search domain yet. This change introduces the application-layer state and persistence that later Telegram and monitoring work will call, while leaving TCDD integration untouched.

## Goals / Non-Goals

**Goals:**
- Store ticket searches and their lifecycle metadata durably in SQLite.
- Provide a small domain/service/repository layer that enforces MVP validation and state transitions in one place.
- Preserve the single-`ACTIVE` invariant across process restarts and multiple database connections.
- Make time-sensitive behavior deterministic in tests while evaluating dates and times in `Europe/Istanbul`.

**Non-Goals:**
- No Telegram handlers, conversation flow, background scheduler, polling, notifications, or Docker changes.
- No changes to `app/tcdd` request, parsing, errors, or provider imports.
- No generic repository, Unit of Work, CQRS, event sourcing, or broader architecture refactor.
- No multi-user, multi-passenger, round-trip, midnight-crossing, or multi-active-search support.

## Decisions

### Add a dedicated ticket-search package outside `app/tcdd`

Implement the new behavior under a focused application package such as `app/ticket_searches/`:
- `models.py`: `TicketSearch` dataclass and `TicketSearchStatus` enum.
- `repository.py`: SQLite mapping and focused query/update methods.
- `service.py`: input validation, active-search invariant handling, and state transitions.
- `exceptions.py`: domain-specific validation, conflict, not-found, and transition errors.

Database initialization can live in a small module such as `app/database.py` or inside the repository module if that keeps the implementation smaller. The important boundary is that `app/tcdd` does not import this package and this package does not require Telegram or scheduler imports.

Alternative considered: put persistence directly in future Telegram handlers. Rejected because handlers must not contain direct SQL and restart-safe state must be reusable by background monitoring.

### Use stdlib SQLite with explicit schema initialization

Use Python's `sqlite3` module and an idempotent initialization function that creates `ticket_searches` with the requested fields:
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- station ids as integers and station names as text
- `travel_date` as `YYYY-MM-DD` text
- `departure_time_from` and `departure_time_to` as `HH:MM` text
- `status` as text with a `CHECK` for `ACTIVE`, `FOUND`, `COMPLETED`, `CANCELLED`, and `EXPIRED`
- nullable lifecycle/check metadata timestamps as ISO-8601 text
- `tcdd_outage_notified` as integer boolean `0` or `1`
- non-null `created_at` and `updated_at` as ISO-8601 text

Alternative considered: introduce an ORM. Rejected because SQLite plus a small repository is enough for the MVP and avoids a new dependency.

### Enforce one ACTIVE search in SQLite and service code

Create a partial unique index equivalent to:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_ticket_searches_one_active
ON ticket_searches(status)
WHERE status = 'ACTIVE';
```

The service still checks for active searches to return clear domain errors, but the database index is the final safety net for concurrent connections.

Alternative considered: service-only checks. Rejected because two processes or connections could race and create two active searches.

### Keep replacement atomic with a database transaction

`replace_active_search` should run in one transaction, preferably with `BEGIN IMMEDIATE` on the SQLite connection:
1. Validate the new search input.
2. Read the current `ACTIVE` search.
3. Mark the old active search `CANCELLED` and set `cancelled_at`.
4. Insert the replacement search as `ACTIVE`.
5. Commit only after both writes succeed.

If any write fails, rollback must leave the database in its previous consistent state. If no active search exists, the method may create the new active search using the same validation path as `create_search`; this keeps the method safe for future UI code without adding another behavior branch.

Alternative considered: cancel first and then insert outside a transaction. Rejected because a failure between writes could lose the active search.

### Centralize state transition validation in the service layer

Define the allowed transition map once:
- `ACTIVE -> FOUND`
- `FOUND -> COMPLETED`
- `COMPLETED -> ACTIVE`
- `ACTIVE -> CANCELLED`
- `ACTIVE -> EXPIRED`

All methods that change status use the same validation helper. Invalid transitions raise a domain transition error and do not update SQLite.

For transition timestamps:
- `mark_found` sets `found_at`.
- `mark_completed` sets `completed_at`.
- `cancel_search` sets `cancelled_at`.
- `expire_search` sets `expired_at`.
- `restart_search` sets status back to `ACTIVE`, updates `updated_at`, and clears `found_at`, `completed_at`, `cancelled_at`, and `expired_at` for the new active run.

Alternative considered: allow repository callers to update arbitrary statuses. Rejected because invalid transitions would become easy to persist accidentally.

### Evaluate dates and restart cutoff in Europe/Istanbul

Use `zoneinfo.ZoneInfo("Europe/Istanbul")` for all date/time decisions. Injecting a `now` callable into `TicketSearchService` keeps tests deterministic without adding a clock abstraction.

Creation rejects a travel date earlier than the current Istanbul local date. A same-day search is allowed if the date itself is not in the past.

For `COMPLETED -> ACTIVE`, define "travel time has not passed" as: current Istanbul time is less than or equal to `travel_date + departure_time_to`. The inclusive end of the departure window is used because the search window itself is inclusive.

Alternative considered: use UTC or server local time for comparisons. Rejected because project requirements explicitly require `Europe/Istanbul` semantics.

### Keep departure-window matching in the domain layer

Expose a small domain behavior that can answer whether a departure time is inside a search's inclusive window. This can be a method on `TicketSearch` or a focused helper in the ticket-search package. It must not call TCDD or know raw provider response shapes.

Alternative considered: defer all time-window logic to future polling. Rejected because inclusive boundary semantics are part of this change's acceptance criteria and should be covered now.

## Risks / Trade-offs

- SQLite partial-index support depends on the SQLite library version -> Python-supported SQLite versions normally include partial indexes; tests should fail clearly if unavailable.
- Same-day creation may allow a window that already ended -> this follows the requested "past date" rule; restart has the stricter travel-window cutoff.
- Reusing the same row for restart loses previous found/completed timestamps -> acceptable for MVP because no history table is requested; `created_at` and `updated_at` still reflect record lifetime.
- SQLite concurrency is limited -> use short transactions and rely on the partial unique index for correctness.

## Migration Plan

1. Add idempotent database initialization before repository/service tests use SQLite.
2. Create the new table and partial unique index when the application opens its database.
3. No existing data migration is required because ticket-search persistence does not exist yet.
4. Rollback is code removal plus dropping the new table only if local development data should be discarded.
