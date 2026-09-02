## 1. Persistence And Domain Boundary

- [x] 1.1 Add durable ticket-search domain methods for `last_checked_at`, `last_successful_check_at`, `next_check_at`, `last_tcdd_error_at`, and `tcdd_outage_notified`, and verify with `pytest tests/test_ticket_searches.py` that each update survives a new SQLite connection.
- [x] 1.2 Add a recovery lookup that returns `ACTIVE` and `FOUND` searches but excludes `COMPLETED`, `CANCELLED`, and `EXPIRED`, and verify with `pytest tests/test_ticket_searches.py`.
- [x] 1.3 Add minimal persisted found-event retry data using normalized train notification fields only, and verify `FOUND` search details survive restart without storing raw TCDD response data.
- [x] 1.4 Ensure existing database initialization/migration remains idempotent for old and new schemas, and verify current ticket-search persistence tests still pass.

## 2. Telegram Notification Surface

- [x] 2.1 Add notifier support for generic TCDD outage, authentication-specific outage, and recovery messages, and verify formatter/notifier tests assert the expected user-visible text without secret token values.
- [x] 2.2 Add notifier support for retrying a found-ticket notification from persisted found-event data, and verify the retried message keeps all eligible trains plus `TCDD'den Bilet Al` and `Bileti Alamadım - Tekrar Ara` actions.
- [x] 2.3 Ensure Telegram notification failures remain observable to monitoring for found-ticket sends, and verify a failed found retry does not mark the search `COMPLETED`.

## 3. Monitoring Reliability

- [x] 3.1 Persist `last_checked_at` for every real TCDD check and `last_successful_check_at` only for successful checks, and verify success and typed-failure monitoring tests.
- [x] 3.2 Persist `next_check_at` for normal polling and TCDD-error retry scheduling, and verify startup can use a past `next_check_at` without an extra normal polling delay.
- [x] 3.3 Catch existing typed TCDD exceptions as outage outcomes rather than empty availability, and verify network/timeout, authentication, rate-limit, server, invalid-response, unexpected-response, TLS, and WAF failures keep the search retryable unless expired.
- [x] 3.4 Send and persist one outage notification per outage period, suppress repeated outage spam across polling and restart, and verify `tcdd_outage_notified` survives restart.
- [x] 3.5 Send one recovery notification after the first successful TCDD check following a reported outage, clear outage state, and verify a later independent outage can notify again.
- [x] 3.6 Implement bounded backoff for consecutive TCDD failures around 120 seconds, 240 seconds, and maximum 300 seconds, and verify successful checks return to random 60-90 second polling.
- [x] 3.7 Keep expiration checks active during outage/backoff and before delayed retries, and verify an expired travel window transitions to `EXPIRED` without requiring TCDD recovery.

## 4. Startup Lifecycle

- [x] 4.1 Add explicit monitoring startup recovery to the existing `build_application_with_monitoring` lifecycle path without starting polling during plain handler construction, and verify handler construction tests remain isolated.
- [x] 4.2 On startup, resume persisted `ACTIVE` polling and retry persisted `FOUND` notification delivery, and verify restart recovery tests do not require the user to run `/ara` again.
- [x] 4.3 Prevent duplicate monitoring loops for the same search within one application instance, and verify repeated startup calls create at most one running task per search.
- [x] 4.4 Ensure monitoring tasks are lifecycle-managed so application shutdown/cancellation does not leave orphaned loops, and verify with async monitoring lifecycle tests.

## 5. Regression Verification

- [x] 5.1 Run `pytest tests/test_monitoring.py tests/test_ticket_searches.py tests/test_tcdd_provider.py` and verify existing monitoring, ticket-search, and TCDD provider behavior still passes.
- [x] 5.2 Run the full test suite with `pytest` and verify restart, outage, backoff, recovery, notification failure, filtering, and Telegram callback scenarios pass together.
- [x] 5.3 Run `openspec validate --change harden-monitoring-reliability --strict` and verify the change artifacts validate before implementation is considered complete.
