## Purpose

Provide automatic monitoring for the single active ticket search by polling TCDD, applying the MVP normal-economy filter, and stopping the search only after a reliable Telegram notification or expiration.

## Requirements

### Requirement: Active search is polled automatically
The system SHALL automatically monitor the single `ACTIVE` ticket search by polling TCDD at random intervals between configured `POLL_MIN_SECONDS` and `POLL_MAX_SECONDS` values.

When no `ACTIVE` search exists, the system SHALL NOT call TCDD for availability.

#### Scenario: Active search triggers TCDD polling
- **WHEN** exactly one `ACTIVE` search exists
- **THEN** the monitor queries TCDD availability for that search route and travel date

#### Scenario: No active search avoids TCDD request
- **WHEN** no search has status `ACTIVE`
- **THEN** the monitor does not call TCDD availability

#### Scenario: Polling interval uses configured random range
- **WHEN** normal monitoring continues after a check
- **THEN** the next check is scheduled using a random interval between `POLL_MIN_SECONDS` and `POLL_MAX_SECONDS`, inclusive

#### Scenario: Completed search is not polled
- **WHEN** a search has status `COMPLETED`
- **THEN** the monitor does not continue polling that search

### Requirement: Train availability is filtered by search criteria
The system SHALL evaluate only normalized train availability records and SHALL match a train only when its departure date equals the search travel date, its departure time is within the inclusive stored departure window, and `economy_available >= 1`.

The system SHALL sort matching trains by departure time ascending.

#### Scenario: Matching train with economy availability is included
- **WHEN** a normalized train departs on the search travel date within the inclusive time window and has `economy_available` of 1 or more
- **THEN** the monitor includes that train as eligible

#### Scenario: Economy unavailable train is excluded
- **WHEN** a normalized train otherwise matches the search but has `economy_available` equal to 0
- **THEN** the monitor excludes that train from eligible results

#### Scenario: Departure time boundaries are inclusive
- **WHEN** normalized trains depart exactly at `departure_time_from` or exactly at `departure_time_to`
- **THEN** both trains are inside the search window

#### Scenario: Wrong travel date is excluded
- **WHEN** a normalized train departure date differs from the search travel date
- **THEN** the monitor excludes that train from eligible results

#### Scenario: Results are sorted by departure time
- **WHEN** multiple normalized trains are eligible for the same search
- **THEN** the monitor returns the eligible trains in ascending departure-time order

### Requirement: Found trains stop monitoring only after notification succeeds
The system SHALL transition an `ACTIVE` search to `FOUND` when one or more eligible trains are found, send all eligible trains in one Telegram notification, and transition the search to `COMPLETED` only after that notification succeeds.

If the Telegram found-ticket notification fails, the system SHALL leave the search in `FOUND` and SHALL NOT mark it `COMPLETED`.

#### Scenario: Found notification completes search after success
- **WHEN** the monitor finds one or more eligible trains for an `ACTIVE` search
- **AND** the Telegram notification is sent successfully
- **THEN** the search is persisted as `FOUND` before notification
- **AND** the search is persisted as `COMPLETED` after notification
- **AND** polling stops for that search

#### Scenario: Notification failure does not complete search
- **WHEN** the monitor finds one or more eligible trains for an `ACTIVE` search
- **AND** the Telegram notification fails
- **THEN** the search remains `FOUND`
- **AND** the search is not persisted as `COMPLETED`

#### Scenario: Multiple eligible trains share one notification
- **WHEN** the monitor finds multiple eligible trains for one search check
- **THEN** all eligible trains are included in a single Telegram notification
- **AND** the monitor does not send one found-ticket notification per train

### Requirement: Expired active searches are stopped
The system SHALL expire an `ACTIVE` search when the current `Europe/Istanbul` time is later than the search travel date combined with its inclusive `departure_time_to` value.

An expired search SHALL NOT be polled again.

#### Scenario: Active search expires after time window
- **WHEN** the current `Europe/Istanbul` time is later than the search travel date and `departure_time_to`
- **THEN** the monitor transitions the search from `ACTIVE` to `EXPIRED`
- **AND** the user receives one expiration notification

#### Scenario: Active search at end boundary is still valid
- **WHEN** the current `Europe/Istanbul` time is exactly the search travel date and `departure_time_to`
- **THEN** the search is not expired by that check

### Requirement: Monitoring preserves integration boundaries
The system SHALL keep monitoring orchestration separate from Telegram conversation state, raw TCDD response parsing, and direct SQLite access.

The monitor SHALL use the ticket-search domain boundary for search reads and lifecycle changes, the TCDD provider boundary for normalized train availability, and the Telegram notification surface for messages.

#### Scenario: Monitor does not parse raw TCDD response
- **WHEN** the monitor evaluates availability
- **THEN** it uses normalized train availability records from the TCDD provider
- **AND** it does not inspect raw TCDD response JSON

#### Scenario: Monitor does not execute direct SQL
- **WHEN** the monitor reads or changes search state
- **THEN** it uses the ticket-search domain boundary
- **AND** it does not execute direct SQLite queries

#### Scenario: Telegram handler tests remain isolated
- **WHEN** Telegram conversation behavior is tested
- **THEN** tests can run without starting automatic TCDD polling

### Requirement: Monitoring recovers persisted searches on startup
The system SHALL inspect persisted ticket-search state during application startup and resume monitoring work for restart-recoverable searches without requiring the user to create a new search.

Only `ACTIVE` and `FOUND` searches SHALL trigger startup recovery work. Searches in `COMPLETED`, `CANCELLED`, or `EXPIRED` SHALL NOT trigger monitoring work.

#### Scenario: Active search resumes after startup
- **WHEN** the application starts and a persisted search has status `ACTIVE`
- **THEN** automatic monitoring resumes for that search
- **AND** the user is not required to run `/ara` again

#### Scenario: Found search retries notification after startup
- **WHEN** the application starts and a persisted search has status `FOUND`
- **THEN** the found-ticket notification flow is retried for that search
- **AND** the system prioritizes notification delivery without requiring a fresh TCDD availability query first

#### Scenario: Terminal and inactive searches do not resume
- **WHEN** the application starts and persisted searches have status `COMPLETED`, `CANCELLED`, or `EXPIRED`
- **THEN** those searches do not start background monitoring work

### Requirement: Polling schedule is restart-safe
The system SHALL persist monitoring timestamps for each real TCDD availability check so an `ACTIVE` search can continue from durable state after restart.

For every real TCDD availability check attempt, successful or failed, the system SHALL persist `last_checked_at`. For successful TCDD availability checks only, the system SHALL persist `last_successful_check_at`. The system SHALL persist `next_check_at` whenever the next monitoring attempt is scheduled.

#### Scenario: Failed TCDD check records attempt time
- **WHEN** monitoring performs a real TCDD availability check and TCDD returns a typed failure
- **THEN** `last_checked_at` is persisted for that search
- **AND** `last_successful_check_at` is not advanced for that failed check

#### Scenario: Successful TCDD check records success time
- **WHEN** monitoring performs a real TCDD availability check and receives a valid TCDD result
- **THEN** `last_checked_at` is persisted for that search
- **AND** `last_successful_check_at` is persisted for that search

#### Scenario: Next check survives restart
- **WHEN** monitoring schedules the next attempt for an `ACTIVE` search
- **THEN** `next_check_at` is persisted for that search
- **AND** application startup can use the persisted value to decide when to check again

#### Scenario: Past next check runs without extra delay
- **WHEN** the application starts and an `ACTIVE` search has `next_check_at` earlier than or equal to the current time
- **THEN** monitoring performs the next check without adding a normal polling delay first

### Requirement: Found notification retry controls completion
The system SHALL retry delivery for persisted `FOUND` searches and SHALL transition a search to `COMPLETED` only after the found-ticket Telegram notification succeeds.

The system SHALL prefer reliable delivery over suppressing every possible duplicate notification caused by process restart.

When notification retry data for the found event is persisted, retry SHALL use that data instead of requiring a fresh TCDD availability query before notifying the user.

#### Scenario: Found search completes after retried notification succeeds
- **WHEN** startup recovery or monitoring retries notification for a persisted `FOUND` search
- **AND** the found-ticket Telegram notification succeeds
- **THEN** the search is transitioned to `COMPLETED`
- **AND** monitoring stops for that search

#### Scenario: Found retry uses persisted found event when available
- **WHEN** startup recovery retries notification for a persisted `FOUND` search with persisted found-event details
- **THEN** the found-ticket notification is sent from the persisted found-event details
- **AND** no fresh TCDD availability query is required before that notification attempt

#### Scenario: Found search remains found after retried notification fails
- **WHEN** startup recovery or monitoring retries notification for a persisted `FOUND` search
- **AND** the found-ticket Telegram notification fails
- **THEN** the search remains `FOUND`
- **AND** the search is not transitioned to `COMPLETED`

### Requirement: TCDD outage is not treated as no availability
The system SHALL treat typed TCDD client failures as outage conditions and SHALL NOT interpret them as an empty availability result.

TCDD network/timeout, authentication, rate-limit, server, invalid-response, unexpected-response, TLS, and WAF failures SHALL leave the search eligible for future retry unless the search has expired.

#### Scenario: Typed TCDD failure keeps search retryable
- **WHEN** monitoring checks an `ACTIVE` search and TCDD returns a typed failure
- **THEN** the monitor does not treat the check as "no eligible train found"
- **AND** the search remains retryable unless its travel window has passed

#### Scenario: Authentication failure is not empty availability
- **WHEN** monitoring receives a TCDD authentication failure
- **THEN** the monitor does not treat the result as an empty availability list
- **AND** the search remains retryable unless its travel window has passed

### Requirement: Outage notifications are persisted and de-duplicated
The system SHALL send one outage notification to the user for the first TCDD outage in an outage period and SHALL persist that the outage was reported.

While the outage continues, repeated polling failures SHALL NOT send the same outage notification again, including after application restart. After recovery clears the outage state, a later independent outage SHALL be eligible to send a new outage notification.

#### Scenario: First outage notifies user once
- **WHEN** monitoring encounters the first typed TCDD failure for a search whose outage notification state is clear
- **THEN** the user receives one outage notification saying TCDD cannot currently be queried and retries will continue in the background
- **AND** the search persists `tcdd_outage_notified` as true
- **AND** the search persists `last_tcdd_error_at`

#### Scenario: Ongoing outage does not spam notification
- **WHEN** monitoring encounters another typed TCDD failure while `tcdd_outage_notified` is already true
- **THEN** the user does not receive another generic outage notification for the same outage period
- **AND** retry scheduling continues

#### Scenario: Outage notification state survives restart
- **WHEN** the application restarts during a TCDD outage and the persisted search has `tcdd_outage_notified` true
- **THEN** continued TCDD failures do not resend the same outage notification

### Requirement: TCDD recovery notification is sent once
The system SHALL send one recovery notification after the first successful TCDD availability check that follows a reported outage and SHALL then clear the persisted outage state.

#### Scenario: Successful check after outage notifies recovery
- **WHEN** monitoring receives a valid TCDD result for a search with `tcdd_outage_notified` true
- **THEN** the user receives one notification saying TCDD connection is restored and the search continues
- **AND** the persisted outage state is cleared

#### Scenario: Cleared outage allows future outage notification
- **WHEN** a search has recovered from a reported outage
- **AND** a later independent TCDD outage occurs
- **THEN** the later outage can send one new outage notification

### Requirement: TCDD error retries use bounded backoff
The system SHALL apply simple bounded backoff for repeated TCDD failures and SHALL return to the normal random polling interval after the next successful TCDD check.

Normal successful monitoring SHALL continue to use the configured random interval between 60 and 90 seconds. Repeated TCDD errors SHALL schedule approximately 120 seconds after the first error, approximately 240 seconds after the second consecutive error, and no more than approximately 300 seconds for subsequent consecutive errors.

#### Scenario: First TCDD failure schedules longer retry
- **WHEN** an `ACTIVE` search encounters the first consecutive TCDD failure
- **THEN** the next check is scheduled approximately 120 seconds later

#### Scenario: Repeated TCDD failures cap retry delay
- **WHEN** an `ACTIVE` search encounters repeated consecutive TCDD failures
- **THEN** the retry delay increases toward approximately 240 seconds
- **AND** later retry delays do not exceed approximately 300 seconds

#### Scenario: Successful check returns to normal interval
- **WHEN** an `ACTIVE` search receives a successful TCDD availability result after one or more failures
- **THEN** the next check is scheduled using the normal random 60-90 second interval

### Requirement: Expiration continues during outage and backoff
The system SHALL continue to evaluate search expiration while TCDD is unavailable or retry backoff is delaying the next availability check.

#### Scenario: Search expires during outage
- **WHEN** an `ACTIVE` search travel window has passed in `Europe/Istanbul` during a TCDD outage
- **THEN** the search transitions to `EXPIRED` without requiring a successful TCDD check first
- **AND** the user receives one expiration notification

#### Scenario: Search expires before delayed retry
- **WHEN** an `ACTIVE` search has a future backoff retry scheduled
- **AND** the search travel window passes before that retry
- **THEN** the search transitions to `EXPIRED` at the appropriate expiration check
- **AND** no further TCDD availability check is required for that search

### Requirement: Monitoring lifecycle prevents duplicate loops
The system SHALL prevent more than one concurrent monitoring loop for the same persisted search within a single application instance.

The system SHALL also prevent concurrent duplicate TCDD availability checks for the same search within a single application instance, including when runtime pickup and startup recovery are both invoked for the same persisted `ACTIVE` search.

Lifecycle startup SHALL keep Telegram handler construction testable without requiring automatic polling to start during handler-only tests.

#### Scenario: Startup does not duplicate loop for one search
- **WHEN** application startup recovery is invoked more than once in the same application instance for the same `ACTIVE` search
- **THEN** no more than one monitoring loop runs for that search

#### Scenario: Runtime pickup does not duplicate loop for one search
- **WHEN** runtime pickup is invoked more than once in the same application instance for the same `ACTIVE` search
- **THEN** no more than one monitoring loop runs for that search

#### Scenario: Restart after runtime pickup does not duplicate worker
- **WHEN** a search was picked up during runtime before application shutdown
- **AND** the application starts again with that persisted search still `ACTIVE`
- **THEN** startup recovery resumes monitoring for that search
- **AND** the new application instance runs no more than one monitoring loop for that search

#### Scenario: Concurrent duplicate TCDD checks are prevented
- **WHEN** a TCDD availability check is already in progress for an `ACTIVE` search
- **AND** another pickup or lifecycle trigger is received for the same search in the same application instance
- **THEN** the system does not start a second concurrent TCDD availability check for that search

#### Scenario: Handler construction remains isolated from polling
- **WHEN** Telegram handlers are constructed in tests
- **THEN** automatic monitoring does not start unless the application lifecycle explicitly starts it

### Requirement: Runtime active searches are picked up automatically
The system SHALL automatically pick up a ticket search that becomes `ACTIVE` during application runtime without requiring container or application restart.

The runtime pickup behavior SHALL apply to newly created searches, replacement searches created by cancelling an existing active search, and completed searches restarted before their travel window has passed. Searches in `CANCELLED`, `COMPLETED`, or `EXPIRED` status SHALL NOT produce TCDD availability checks.

Runtime pickup SHALL preserve the existing normal polling behavior: real TCDD checks SHALL persist monitoring timestamps, and subsequent successful normal polling SHALL schedule the next check using the configured random range between `POLL_MIN_SECONDS` and `POLL_MAX_SECONDS`.

#### Scenario: New active search is monitored without restart
- **WHEN** the application is running with no `ACTIVE` search
- **AND** a new search is created and persisted as `ACTIVE`
- **THEN** monitoring picks up that search without requiring application restart
- **AND** a real TCDD availability check is performed for that search
- **AND** `last_checked_at` is persisted for that search after the check attempt

#### Scenario: Runtime polling schedule is persisted
- **WHEN** monitoring performs a runtime-picked-up TCDD availability check for an `ACTIVE` search
- **AND** normal monitoring continues after that check
- **THEN** `next_check_at` is persisted for that search
- **AND** the next check uses the configured random polling interval between `POLL_MIN_SECONDS` and `POLL_MAX_SECONDS`, inclusive

#### Scenario: Replacement active search is monitored
- **WHEN** an existing `ACTIVE` search is replaced by a new valid search
- **THEN** the cancelled old search is not polled again
- **AND** the replacement `ACTIVE` search is picked up by monitoring without requiring application restart

#### Scenario: Restarted completed search is monitored
- **WHEN** a `COMPLETED` search is restarted before its travel window has passed
- **THEN** the same search becomes `ACTIVE`
- **AND** monitoring picks up that reactivated search without requiring application restart

#### Scenario: Non-active search is not picked up
- **WHEN** a search has status `CANCELLED`, `COMPLETED`, or `EXPIRED`
- **THEN** monitoring does not perform a TCDD availability check for that search

#### Scenario: Startup recovery still monitors active search
- **WHEN** the application starts and a persisted search has status `ACTIVE`
- **THEN** startup recovery resumes monitoring for that search
- **AND** runtime pickup support does not require the user to create another search

### Requirement: Container restart uses persisted monitoring recovery
The containerized runtime SHALL preserve the existing monitoring recovery semantics by starting monitoring against persisted ticket-search state after application startup.

An `ACTIVE` search persisted before container restart SHALL be eligible for automatic polling after restart, and a `FOUND` search persisted before container restart SHALL remain available to the existing notification recovery behavior.

#### Scenario: Active search resumes monitoring after container restart
- **WHEN** an `ACTIVE` search exists in the SQLite database on the persistent volume
- **AND** the application container restarts
- **THEN** monitoring starts after application startup
- **AND** the existing monitoring behavior can continue checking that `ACTIVE` search without requiring the user to recreate it

#### Scenario: Found search remains recoverable after container restart
- **WHEN** a `FOUND` search exists in the SQLite database on the persistent volume
- **AND** the application container restarts
- **THEN** the existing notification recovery behavior can process that `FOUND` search using persisted state
- **AND** the search is not lost because of container restart or recreate

#### Scenario: Containerization does not change monitoring decisions
- **WHEN** monitoring runs inside the containerized runtime
- **THEN** it still applies the existing TCDD polling, normal-economy filtering, outage handling, notification, and lifecycle transition behavior
