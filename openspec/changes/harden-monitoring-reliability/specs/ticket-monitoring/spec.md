## ADDED Requirements

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

Lifecycle startup SHALL keep Telegram handler construction testable without requiring automatic polling to start during handler-only tests.

#### Scenario: Startup does not duplicate loop for one search
- **WHEN** application startup recovery is invoked more than once in the same application instance for the same `ACTIVE` search
- **THEN** no more than one monitoring loop runs for that search

#### Scenario: Handler construction remains isolated from polling
- **WHEN** Telegram handlers are constructed in tests
- **THEN** automatic monitoring does not start unless the application lifecycle explicitly starts it
