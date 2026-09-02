## Why

Ticket searches can currently be created and persisted, but an `ACTIVE` search is not yet automatically checked against TCDD until a normal economy seat is found or the search window expires. This change adds the MVP monitoring loop so the bot can notify the user without manual polling while preserving the existing TCDD provider, ticket-search domain, and Telegram boundaries.

## What Changes

- Add an application-level monitoring worker/service that periodically checks the single `ACTIVE` search using random intervals from `POLL_MIN_SECONDS` and `POLL_MAX_SECONDS`, defaulting to the MVP 60-90 second range.
- Filter normalized `TrainAvailability` records by travel date, inclusive departure time window, and `economy_available >= 1`, sorted by departure time.
- Transition matching searches through `ACTIVE -> FOUND -> COMPLETED` only after a successful Telegram notification containing all matching trains in one message.
- Keep searches in `FOUND` if the Telegram found-seat notification fails, so a search is never completed before the user is notified.
- Expire `ACTIVE` searches whose travel date and inclusive `departure_time_to` have passed in `Europe/Istanbul`, and notify the user once.
- Add Telegram notification actions for opening TCDD ticket purchase and restarting the same completed search through a stale-safe callback.
- Do not add outage suppression, recovery notifications, exponential backoff, Docker changes, multi-user behavior, Playwright, token refresh, or ticket purchase automation in this change.

## Capabilities

### New Capabilities
- `ticket-monitoring`: Automatic polling, filtering, notification, and completion/expiration behavior for the active ticket search.

### Modified Capabilities
- `ticket-searches`: Restart and lifecycle operations are used by monitoring callbacks and expiration/completion flow with the existing state invariants.
- `telegram-search-flow`: Telegram adds found-ticket and expiration notifications plus stale-safe restart callback behavior without moving polling into conversation handlers.

## Impact

- Affected code: monitoring worker/service composition, configuration loading, `app/ticket_searches` service usage, `app/tcdd` normalized availability usage, Telegram notification/callback surface, and tests around filtering and lifecycle flow.
- Affected systems: TCDD HTTP provider will be called periodically only when an `ACTIVE` search exists; Telegram will send found-ticket, restart-action, and expiration messages.
- Dependencies: no new dependency is expected; use existing Python scheduling/application lifecycle facilities unless implementation proves a minimal dependency is necessary.
