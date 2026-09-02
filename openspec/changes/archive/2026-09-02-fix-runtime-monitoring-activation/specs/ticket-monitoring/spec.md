## ADDED Requirements

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

## MODIFIED Requirements

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
