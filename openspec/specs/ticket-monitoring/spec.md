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
