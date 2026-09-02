## Purpose

Provide a production TCDD integration capability that resolves canonical stations, queries the verified train-availability service, and returns normalized train availability without exposing TCDD response internals.

## ADDED Requirements

### Requirement: Canonical TCDD stations are discoverable
The system SHALL provide production station lookup and search using canonical TCDD station records from the verified station-pairs source.

#### Scenario: Known station names resolve to canonical records
- **WHEN** station lookup is requested for user-facing names such as `Söğütlüçeşme` or `Ankara`
- **THEN** the system returns the matching canonical TCDD station records and identifiers from the station-pairs source

#### Scenario: Station search returns normalized station records
- **WHEN** station search is requested with a partial or display-form station name
- **THEN** the system returns normalized station records suitable for a train-availability request
- **AND** the returned records do not expose raw station-pairs JSON objects outside the TCDD integration capability

#### Scenario: Unknown station is explicit
- **WHEN** no canonical station matches the requested name
- **THEN** the system reports a station lookup failure instead of guessing an identifier or running a train search

### Requirement: Train availability search uses the verified production API contract
The system SHALL query TCDD train availability through the verified production service contract and return a normalized result for the requested origin, destination, and travel date.

#### Scenario: Availability request is formed for the primary service
- **WHEN** a train availability search is requested with canonical origin and destination station identifiers and a travel date
- **THEN** the system sends the request to `https://gise-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability`
- **AND** the request uses `passengerTypeId=1`, `count=1`, `unit-id: 3895`, and the required browser-origin headers

#### Scenario: Production authentication comes from environment
- **WHEN** a train availability search is requested
- **THEN** the system authenticates with the JWT provided by `TCDD_TOKEN`
- **AND** the system does not attempt token scraping, bundled-token discovery, or automatic token refresh

#### Scenario: WAF-blocked endpoint is not primary
- **WHEN** the production provider chooses a train availability endpoint
- **THEN** it does not use the `web-api-prod` endpoint as the primary endpoint

### Requirement: Train availability responses are normalized
The system SHALL parse valid TCDD train availability responses into normalized train availability records containing only stable fields needed by downstream application code.

#### Scenario: Valid response returns normalized train records
- **WHEN** TCDD returns one or more services for the requested route and date
- **THEN** each returned train availability record includes train identifier, train name or number, departure timestamp, arrival timestamp, and normal economy availability count
- **AND** no raw TCDD JSON response shape is exposed outside the TCDD integration capability

#### Scenario: Wrong-date trains are excluded
- **WHEN** a valid TCDD response contains services whose departure date differs from the requested travel date
- **THEN** those services are excluded from the normalized train availability results

#### Scenario: Valid empty response remains valid
- **WHEN** TCDD returns a valid response with no trains for the requested route and date
- **THEN** the system returns an empty normalized train availability list
- **AND** it does not report an API failure

### Requirement: Normal economy availability is isolated from other categories
The system SHALL compute normal economy availability only from the verified normal economy category and SHALL NOT count business, accessible, or special-seat availability as normal economy availability.

#### Scenario: Economy availability is preserved
- **WHEN** a service has category `1` normal economy availability of at least 1
- **THEN** the normalized train availability record preserves that count as normal economy availability

#### Scenario: Business-only availability is not economy availability
- **WHEN** a service has category `4` business availability greater than 0 and category `1` normal economy availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Accessible-only availability is not economy availability
- **WHEN** a service has category `23` accessible availability greater than 0 and category `1` normal economy availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Special-seat-only availability is not economy availability
- **WHEN** a service has category `22` special-seat availability greater than 0 and category `1` normal economy availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

### Requirement: API failures are distinct from valid empty results
The system SHALL map TCDD access, protocol, and response failures to meaningful production errors instead of returning an empty availability list.

#### Scenario: Network or timeout failure is reported
- **WHEN** the availability request fails because of a network error or timeout
- **THEN** the system raises a network or timeout TCDD error
- **AND** it does not return an empty train list

#### Scenario: Authentication failure is reported
- **WHEN** the token is missing, rejected, or otherwise unauthorized by TCDD
- **THEN** the system raises an authentication TCDD error
- **AND** it does not log the token value

#### Scenario: Rate limit is reported
- **WHEN** TCDD responds with a rate-limit response
- **THEN** the system raises a rate-limit TCDD error
- **AND** it does not return an empty train list

#### Scenario: Server failure is reported
- **WHEN** TCDD responds with an HTTP 5xx response
- **THEN** the system raises a server TCDD error
- **AND** it does not return an empty train list

#### Scenario: Invalid or unexpected response is reported
- **WHEN** TCDD returns invalid JSON or a response shape that cannot be normalized safely
- **THEN** the system raises an invalid-response or unexpected-response TCDD error
- **AND** it does not return an empty train list

#### Scenario: TLS or WAF failure is reported distinctly
- **WHEN** the request fails because of TLS negotiation or WAF blocking behavior
- **THEN** the system raises a TLS or WAF TCDD error
- **AND** it does not return an empty train list

### Requirement: TCDD provider remains application-layer independent
The system SHALL keep the production TCDD integration independent from Telegram bot handling, SQLite ticket-search persistence, scheduler polling, notification delivery, Docker deployment, and Playwright automation.

#### Scenario: Provider can be used without application orchestration
- **WHEN** the TCDD provider is imported or exercised in tests
- **THEN** it does not require Telegram, SQLite ticket-search persistence, scheduler, notification, Docker, or Playwright components to be imported or initialized

#### Scenario: Spike remains separate
- **WHEN** production TCDD integration code runs
- **THEN** it does not depend on `scripts/spike_tcdd.py` for station lookup, request construction, response parsing, or error handling
