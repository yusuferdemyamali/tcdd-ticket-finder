## Context

See `proposal.md` for motivation. The current monitoring service already owns polling, durable timestamp updates, startup recovery, shutdown, and duplicate active-task tracking. Telegram application construction wires `MonitoringService.startup_recovery()` into lifecycle hooks, while plain handler construction remains isolated from automatic polling.

The observed gap is not search persistence: runtime-created and restarted searches become `ACTIVE` in SQLite. The gap is activation: the monitoring lifecycle only starts work from startup recovery, so a process that began with no active search has no background worker to notice the later active search.

## Goals / Non-Goals

**Goals:**

- Add a runtime pickup path owned by the monitoring service.
- Let application-level wiring notify monitoring after a search becomes `ACTIVE` without making Telegram handlers manage polling loops directly.
- Preserve the existing startup recovery path for persisted `ACTIVE` and `FOUND` searches.
- Guard both long-lived loop creation and individual TCDD check execution against duplicates for the same search in one application instance.
- Keep existing polling interval and timestamp persistence behavior.

**Non-Goals:**

- No TCDD parser or endpoint changes.
- No retry/backoff redesign.
- No Telegram text, button, or conversation UX changes.
- No Docker topology or process model changes.
- No multi-user scheduling model.

## Decisions

1. Add an explicit monitoring-service runtime pickup entry point.

   The monitoring service should expose a small async method that reads current persisted state and starts monitoring only when the target/current search is `ACTIVE`. It should reuse the same task registry and active-loop implementation used by startup recovery instead of introducing a second scheduler.

   Alternative considered: have Telegram handlers call `startup_recovery()` after creating searches. That would work but blurs startup semantics, can also retry `FOUND` notifications from a runtime create path, and makes the bug fix depend on a startup-only method name.

2. Wire pickup through application-level composition, not direct SQL or raw Telegram polling logic.

   The Telegram layer may receive an injected callback or activation notifier from `build_application_with_monitoring`, invoked only after `create_search`, `replace_active_search`, or `restart_search` returns a persisted `ACTIVE` search. Handlers should not create tasks themselves or inspect monitoring internals. The callback should be absent/no-op in handler-only tests so construction stays isolated.

   Alternative considered: make the ticket-search domain service depend on monitoring and emit the wake-up directly. That would create a reverse dependency from domain lifecycle behavior into background orchestration, making ticket-search tests require monitoring concerns.

3. Reuse startup active-loop behavior for runtime pickup.

   A runtime-picked-up search with no `next_check_at` should check immediately, matching the existing startup behavior for past or missing `next_check_at`. After the first check, existing monitoring code should persist `last_checked_at` and schedule `next_check_at` using normal 60-90 second polling when no outage/backoff behavior applies.

   Alternative considered: create a separate one-shot immediate check and only then start the loop. That increases the chance of duplicated check paths and makes in-flight guarding more important than necessary.

4. Add a per-search in-flight check guard in monitoring.

   The existing `_active_tasks` registry prevents duplicate loops, but concurrent triggers can still race before a task is registered or can call deterministic check paths directly in tests. A lightweight per-search guard around the actual TCDD availability call should prevent simultaneous checks for the same persisted search within one application instance.

   Alternative considered: rely only on SQLite's single-active invariant. That protects persisted active state, not concurrent background execution inside one process.

## Risks / Trade-offs

- Runtime pickup called before the application event loop is fully running -> only invoke pickup from async Telegram callbacks or lifecycle-aware application code; keep handler-only construction no-op.
- Race between replacement cancellation and old loop wake-up -> each loop iteration must re-read the search by id and stop when status is no longer `ACTIVE`.
- In-flight guard accidentally suppresses the only check after a task failure -> clear the guard in `finally` around the check operation.
- Startup recovery and runtime pickup both target the same search after restart -> share one task registry path and make duplicate pickup idempotent.
- Tests with zero sleep can create busy loops -> runtime regression tests should use controlled sleep functions, direct task inspection, or one-check synchronization rather than unbounded real-time sleeps.

## Migration Plan

No data migration is expected. Deploying the code change should preserve existing persisted searches: startup recovery continues to resume `ACTIVE` searches and retry `FOUND` notifications, while runtime pickup only affects searches activated after the process is already running.

Rollback is code-only. If rolled back, persisted search data remains compatible, but runtime-created active searches again require application restart for monitoring pickup.
