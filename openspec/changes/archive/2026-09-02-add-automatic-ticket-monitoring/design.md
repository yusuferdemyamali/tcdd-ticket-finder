## Context

See `proposal.md` for motivation. The current codebase already has durable ticket-search lifecycle behavior in `app/ticket_searches`, normalized TCDD train availability in `app/tcdd`, and Telegram command/conversation handlers in `app/telegram`. Existing specs require single-user, single-active-search MVP behavior, no raw TCDD response leakage outside `app/tcdd`, no direct SQL in Telegram handlers, and `Europe/Istanbul` time evaluation.

There is no application-level monitoring component yet. The design should add one without turning Telegram conversation handlers into polling workers and without changing the TCDD provider parser contract.

## Goals / Non-Goals

**Goals:**
- Keep monitoring as an orchestration layer that composes `TicketSearchService`, `TcddClient.search_trains`, and a small Telegram notification surface.
- Make filtering deterministic and testable without real TCDD or Telegram network calls.
- Preserve the notification reliability invariant: `COMPLETED` is written only after the found-ticket Telegram message succeeds.
- Add config for `POLL_MIN_SECONDS` and `POLL_MAX_SECONDS`, with normal MVP defaults of 60 and 90 seconds.
- Keep restart callback handling database-current and search-id scoped.

**Non-Goals:**
- No outage suppression, recovery notification, retry hardening for `FOUND` after process restart, or exponential backoff.
- No Docker or deployment changes.
- No multi-user or multiple-active-search design.
- No Playwright, automatic token refresh, or ticket purchasing automation.

## Decisions

### Decision: Add a dedicated monitoring module

Create a new monitoring module, likely under `app/monitoring/`, containing a small worker/service. It should own one-shot check behavior and the polling loop, while depending on injected ticket-search, TCDD, and notifier objects.

Alternative considered: put polling inside Telegram handlers. Rejected because existing Telegram specs require handler tests to run without external polling and because conversation handlers should not own background TCDD orchestration.

### Decision: Split one-check logic from the sleep loop

Implement a deterministic `run_once`-style method for the worker that performs one monitoring check: read active search, expire if needed, query TCDD, filter, mark found, notify, and complete on notification success. Keep random sleep scheduling in a thin loop around that method.

Alternative considered: test only the full long-running loop. Rejected because random 60-90 second sleeps would make unit tests slow and fragile.

### Decision: Filter normalized `TrainAvailability` only

Filtering should use `TrainAvailability.departure_date`, `TrainAvailability.departure_time`, and `economy_available`. The worker must not parse raw TCDD JSON or infer availability from business, accessible, or special categories.

Alternative considered: pass raw provider responses to the worker and filter there. Rejected because it violates the TCDD provider boundary and duplicates parser responsibilities.

### Decision: Use a Telegram notification adapter outside conversation state

Add a notification surface that can send found-ticket and expiration messages to the allowed user/chat. It should format all eligible trains into one found-ticket message and attach the two required actions. The adapter can be injected into the worker so tests can simulate success/failure without PTB network calls.

Alternative considered: reuse command handler methods directly from the worker. Rejected because command handlers depend on `Update`/conversation context, while monitoring notifications are outbound application events.

### Decision: Register restart callback globally

Add a global callback handler for the restart action payload. On callback, check authorization, parse the search id from the payload, read the current persisted search by id, require `COMPLETED`, require the travel window to be unpassed, then call `restart_search` for that same id.

Alternative considered: store restart state in Telegram `user_data`. Rejected because stale messages must be validated against current persisted search state, not in-memory conversation state.

### Decision: Keep failure semantics minimal in this change

For TCDD provider errors, the one-check method should not treat errors as empty results and should not transition to `FOUND`, `COMPLETED`, or `EXPIRED` because of TCDD access failure. It may let the exception surface to the loop/logging layer or record check metadata if existing service support is available; outage suppression and recovery notification are deferred.

Alternative considered: implement full outage state and recovery notification now. Rejected because it is explicitly out of scope for this change.

## Risks / Trade-offs

- [Risk] `FOUND` searches are not retried after a failed notification in this change -> Mitigation: preserve the `FOUND` state and cover the invariant with tests; restart/recovery hardening remains a later change.
- [Risk] The application entry point for starting the monitoring loop may be minimal or absent -> Mitigation: add the smallest integration point needed to start the worker alongside the Telegram application without Docker changes.
- [Risk] Telegram purchase URL details may be route/date-specific later -> Mitigation: the action only needs to open TCDD purchase surface in this change; exact deep-linking can remain simple unless existing code already supports route-aware URLs.
- [Risk] Random polling can make tests nondeterministic -> Mitigation: inject random/sleep functions or interval provider in tests and assert chosen values are inside configured bounds.

## Migration Plan

1. Add config and monitoring code with defaults so existing environment files are not required to change.
2. Add tests for filtering, state transitions, notification success/failure, expiration, and restart callbacks using fakes.
3. Wire the worker into application construction with injected dependencies while keeping Telegram handler tests isolated.
4. Rollback by disabling worker startup; existing `/ara`, `/durum`, `/iptal`, TCDD provider, and ticket-search persistence behavior remain usable.
