## 1. Monitoring Pickup

- [x] 1.1 Add an idempotent runtime pickup entry point to `MonitoringService` that starts monitoring only for persisted `ACTIVE` searches and verify non-active ids return without creating tasks or TCDD calls.
- [x] 1.2 Reuse the existing active-loop path for runtime pickup and verify a newly picked-up search with empty `next_check_at` performs a real TCDD check without waiting for restart.
- [x] 1.3 Add a per-search in-flight check guard around TCDD availability checks and verify concurrent triggers for the same search produce no duplicate concurrent TCDD requests.

## 2. Application Wiring

- [x] 2.1 Inject a runtime activation callback through `build_application_with_monitoring` without starting polling during plain handler construction and verify handler-only tests remain isolated from monitoring.
- [x] 2.2 Invoke the activation callback after successful Telegram search creation and verify the persisted new `ACTIVE` search is picked up by monitoring.
- [x] 2.3 Invoke the activation callback after successful `replace_active_search` and verify the old `CANCELLED` search is not polled while the replacement `ACTIVE` search is picked up.
- [x] 2.4 Invoke the activation callback after successful `restart_search` and verify the same restarted search becomes monitored without requiring restart.

## 3. Lifecycle Safety

- [x] 3.1 Keep `startup_recovery()` behavior unchanged for persisted `ACTIVE` and `FOUND` searches and verify the existing startup recovery tests still pass.
- [x] 3.2 Share duplicate-task protection between startup recovery and runtime pickup and verify repeated pickup/recovery calls create no more than one active monitoring task for the same search in one application instance.
- [x] 3.3 Ensure active loops re-read persisted search status before each check and verify `CANCELLED`, `COMPLETED`, and `EXPIRED` searches do not produce later TCDD calls.

## 4. Regression Tests

- [x] 4.1 Add a regression test for the sequence: app starts with no `ACTIVE` search, runtime search is created, monitoring checks TCDD without container restart, and `last_checked_at` is persisted.
- [x] 4.2 Add regression coverage that runtime pickup persists `next_check_at` during normal polling and verify the configured 60-90 second interval semantics remain intact.
- [x] 4.3 Add regression coverage for replacement and restart activation and verify both paths result in monitored `ACTIVE` searches.
- [x] 4.4 Add regression coverage for duplicate prevention after runtime pickup plus application restart simulation and verify no duplicate worker/check is created in the new instance.

## 5. Verification

- [x] 5.1 Run `pytest tests/test_monitoring.py` and verify monitoring lifecycle, timestamp, duplicate, and non-active polling behavior passes.
- [x] 5.2 Run `pytest tests/test_ticket_searches.py tests/test_tcdd_provider.py` and verify ticket-search domain behavior and TCDD provider parser semantics were not changed.
- [x] 5.3 Run the full test suite with `pytest` and verify existing monitoring, Telegram, ticket-search, and TCDD provider tests all pass.
- [x] 5.4 Run `openspec validate fix-runtime-monitoring-activation --strict` and verify the change artifacts validate before implementation is considered complete.
