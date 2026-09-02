## 1. Configuration and Monitoring Structure

- [x] 1.1 Add monitoring configuration for `POLL_MIN_SECONDS` and `POLL_MAX_SECONDS` with 60 and 90 second defaults, and verify unit tests cover defaults, env overrides, and invalid min/max values.
- [x] 1.2 Create a dedicated monitoring module/service separate from Telegram conversation handlers, and verify it can be imported without starting Telegram polling or making TCDD requests.
- [x] 1.3 Add a deterministic one-check monitoring entry point plus a thin random-interval polling loop, and verify tests can run the one-check path without sleeping.

## 2. Filtering Behavior

- [x] 2.1 Implement filtering over normalized `TrainAvailability` records by `departure_date == search.travel_date`, inclusive `departure_time_from <= departure_time <= departure_time_to`, and `economy_available >= 1`, and verify tests cover matching, wrong date, outside time window, and boundary times.
- [x] 2.2 Sort eligible trains by departure time ascending, and verify a test with out-of-order provider results returns sorted matches.
- [x] 2.3 Verify economy-only eligibility with tests where `economy_available=0` never matches and `economy_available>=1` matches, relying only on normalized provider data.

## 3. Monitoring State Flow

- [x] 3.1 Implement no-active-search behavior so no TCDD provider call is made, and verify with a fake provider call counter.
- [x] 3.2 Implement active-search TCDD query behavior using the stored origin station id, destination station id, and travel date, and verify the fake provider receives those criteria.
- [x] 3.3 Implement no-match behavior that leaves the search `ACTIVE` and continues scheduling, and verify no found-ticket notification is sent.
- [x] 3.4 Implement found-match behavior as `ACTIVE -> FOUND -> Telegram notification -> COMPLETED`, and verify persisted state order with fakes or repository assertions.
- [x] 3.5 Implement notification-failure behavior that leaves the search `FOUND` and never marks it `COMPLETED`, and verify the failure test preserves the invariant.
- [x] 3.6 Implement expiration when current `Europe/Istanbul` time is later than the travel date plus `departure_time_to`, and verify `ACTIVE -> EXPIRED`, one expiration notification, and no TCDD call after expiration.

## 4. Telegram Notification and Callback Surface

- [x] 4.1 Add found-ticket message formatting for route, travel date, train name or number, departure time, and economy availability count for all eligible trains, and verify a multi-train test produces one message containing every train.
- [x] 4.2 Add found-ticket actions for `TCDD'den Bilet Al` and `Bileti Alamadım - Tekrar Ara`, and verify the restart callback payload includes the related search id.
- [x] 4.3 Add expiration notification formatting/sending, and verify the monitor sends one ended-search message when expiring an active search.
- [x] 4.4 Add a global restart callback handler that reads the current persisted search by id before restarting, and verify it does not rely on Telegram `user_data` wizard state.
- [x] 4.5 Enforce restart callback guards for authorization, matching search id, `COMPLETED` status, and unpassed travel window, and verify stale, wrong-status, unauthorized, and expired-window callbacks do not activate a search.
- [x] 4.6 Verify a valid restart callback calls `restart_search`, returns the same criteria to `ACTIVE`, and allows monitoring to pick it up again.

## 5. Integration and Regression Verification

- [x] 5.1 Wire monitoring startup into the application lifecycle with injected `TicketSearchService`, `TcddClient`, and Telegram notifier while keeping command handler construction testable without starting the worker; verify existing Telegram handler tests still pass.
- [x] 5.2 Verify polling uses random intervals in the configured 60-90 second default range under normal continuation without adding outage backoff or recovery notification behavior.
- [x] 5.3 Run the ticket-search test suite and verify existing lifecycle, restart, and transition behavior still passes.
- [x] 5.4 Run the TCDD provider tests and verify parser/provider boundaries and economy availability invariants still pass.
- [x] 5.5 Run the full test suite and verify monitoring, filtering, notification state flow, Telegram, TCDD provider, and ticket-search tests pass together.
