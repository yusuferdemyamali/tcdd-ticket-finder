## Context

See `proposal.md` for motivation. Current monitoring has a deterministic `run_once()` and a thin `run_loop()`, and `build_application_with_monitoring()` constructs but does not auto-start monitoring. Ticket-search records already carry polling/outage metadata fields, but monitoring does not yet durably update them on each TCDD check. `FOUND` currently preserves the completion invariant, but retry after restart needs durable found-event notification data rather than process memory.

## Goals / Non-Goals

**Goals:**

- Make startup recovery explicit for persisted `ACTIVE` and `FOUND` searches.
- Persist check timing, outage notification state, and found-event retry data through the ticket-search domain boundary.
- Keep monitoring orchestration independent from raw TCDD response shapes, direct SQLite access, and Telegram handler conversation state.
- Keep successful polling behavior at the existing random 60-90 second interval.
- Keep handler construction and lifecycle startup separately testable.

**Non-Goals:**

- No automatic TCDD token refresh, token scraping, or new endpoint discovery.
- No generic scheduler framework, queue system, repository abstraction, or multi-search concurrency model.
- No changes to the allowed domain states or state transition graph unless needed by the existing `ACTIVE`, `FOUND`, `COMPLETED`, `CANCELLED`, `EXPIRED` rules.

## Decisions

1. Use the ticket-search service as the only persistence boundary for monitoring metadata.

   Add small service/repository methods for recording check attempts, successful checks, next scheduled checks, outage notification state, outage recovery, and recovery-required searches. Monitoring should not mutate model fields and call repository internals directly from orchestration code.

   Alternative considered: let monitoring update the dataclass and repository directly. Rejected because it weakens the existing domain boundary and makes Telegram or monitoring code more likely to grow direct persistence behavior.

2. Persist a minimal found-event notification snapshot before sending found-ticket Telegram notification.

   `FOUND` recovery after restart needs enough data to rebuild the found-ticket message. If the current schema cannot store that data, add the smallest internal persistence shape needed, such as a JSON column/table containing normalized train fields used by notification formatting: train id, train name/number, departure/arrival timestamp, and normal economy availability. Do not store raw TCDD JSON.

   Alternative considered: re-query TCDD for every `FOUND` recovery. Rejected as the primary path because the originally found seat can disappear or TCDD can be down, which conflicts with reliable delivery of a found event. A fresh query may still be an explicit fallback only if no snapshot exists from older data.

3. Split monitoring into deterministic actions and lifecycle scheduling.

   Keep `run_once()` testable for one check. Add startup/lifecycle methods that inspect recovery-required searches, schedule immediate or delayed work based on persisted `next_check_at`, and retry `FOUND` notifications. Track running task/search ids in the monitoring service instance so repeated startup hooks do not create duplicate loops.

   Alternative considered: start a loop immediately inside `build_application_with_monitoring()`. Rejected because handler construction tests must remain isolated and PTB lifecycle should own startup/shutdown timing.

4. Treat TCDD errors as outage outcomes inside monitoring, not empty results.

   Catch the existing `TcddError` hierarchy around availability checks. On failure, persist `last_checked_at`, `last_tcdd_error_at`, set/send outage notification only if not already reported, calculate backoff, and keep the search retryable unless expired. Let non-TCDD programming errors remain visible to tests/logging rather than classifying them as outage.

   Alternative considered: catch all exceptions in the same retry path. Rejected because notification failures and coding errors have different semantics from typed TCDD outages.

5. Use consecutive-error backoff derived in monitoring without a new state machine.

   Use simple in-process consecutive failure count for active loops and reconstruct a conservative retry behavior after restart from persisted outage/check timestamps where needed. Persist only `next_check_at`, `last_checked_at`, `last_successful_check_at`, `last_tcdd_error_at`, and `tcdd_outage_notified`; do not add a dedicated backoff state unless tests prove it is necessary.

   Alternative considered: persist a formal retry counter/state. Rejected because the requested behavior can be satisfied with `next_check_at` plus simple loop-local counting, and the MVP asks to avoid unnecessary abstractions.

6. Run expiration checks independently of TCDD availability success.

   Check expiration before each TCDD call and before sleeping until a delayed retry if the travel window can pass earlier than `next_check_at`. Expiration should not wait for TCDD to recover.

   Alternative considered: only expire during normal `run_once()` checks. Rejected because outage/backoff could delay expiration beyond the travel window.

## Risks / Trade-offs

- Duplicate found notification after restart -> Mitigation: persist `COMPLETED` only after send succeeds and check current state before retry; accept rare duplicates over lost notification.
- Found-event snapshot adds persistence surface -> Mitigation: store only normalized notification fields and keep raw TCDD data inside `app/tcdd/`.
- Backoff count is partly in-memory -> Mitigation: persisted `next_check_at` remains authoritative across restart; after success polling returns to normal.
- Outage/recovery Telegram send can fail -> Mitigation: found-ticket completion remains strict; outage/recovery messages should not block polling forever, but their persisted flags must avoid spam when a send succeeds.
- Lifecycle hooks can be invoked repeatedly by tests or PTB startup -> Mitigation: monitor tracks active tasks per search id and makes startup recovery idempotent inside one application instance.

## Migration Plan

1. Add persistence support for any missing found-event retry data and initialize it safely for existing databases.
2. Existing rows without found-event retry data can still recover `ACTIVE` polling normally; `FOUND` rows without retry data may use a conservative fallback path documented in tests.
3. Rollback is safe if new nullable persistence fields are ignored by old code, but any migration should avoid deleting existing ticket-search data.
