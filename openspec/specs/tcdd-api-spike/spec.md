## Purpose

Validate that the project can access the real TCDD web API without Playwright and extract the train-service data needed for the MVP availability invariant before production integration begins.

## Requirements

### Requirement: Spike command validates real API access
The system SHALL provide an isolated terminal-run spike that queries the real TCDD web API for a caller-provided origin station, destination station, and travel date without using Playwright.

#### Scenario: Real route query succeeds
- **WHEN** the spike is run with a valid origin station, destination station, and travel date supported by TCDD
- **THEN** it outputs normalized train-service records returned by the real HTTP API
- **AND** it identifies the API endpoint, request method, required headers, payload shape, and any authentication or token behavior used for the successful request

#### Scenario: Playwright is not used
- **WHEN** the spike is run for any route
- **THEN** it completes without launching a browser or depending on Playwright automation

### Requirement: Station canonical records are discoverable
The system SHALL verify that user-facing station names can be resolved to the canonical TCDD station identifiers or records required by the service-search API.

#### Scenario: Station lookup returns canonical records
- **WHEN** the spike is run with valid origin and destination station names
- **THEN** it shows the canonical station records or identifiers used in the subsequent service-search request

#### Scenario: Station lookup failure is explicit
- **WHEN** a station name cannot be resolved to a canonical TCDD record
- **THEN** the spike reports a station lookup failure instead of running a service search with guessed identifiers

### Requirement: Journey times and dates are normalized
The system SHALL parse TCDD service responses into normalized journey records that include origin, destination, departure date, departure time, and arrival time when those fields are available from the API.

#### Scenario: Returned services include parsed times
- **WHEN** the API returns one or more services for the requested route and date
- **THEN** each displayed normalized journey includes a parsed departure time and arrival time

#### Scenario: Different-date services are filtered
- **WHEN** the API response contains services whose departure date differs from the requested travel date
- **THEN** those services are excluded from the normalized available-service output

### Requirement: Normal economy availability is separated from other seat types
The system SHALL identify normal economy seat availability separately from business availability and accessible or special-seat availability.

#### Scenario: Normal economy seats are available
- **WHEN** a returned service has normal economy availability of at least 1
- **THEN** the normalized output marks the service as MVP-eligible and shows the normal economy availability count

#### Scenario: Business-only availability is not eligible
- **WHEN** a returned service has business availability greater than 0 and normal economy availability equal to 0
- **THEN** the normalized output does not mark the service as MVP-eligible

#### Scenario: Accessible-only availability is not eligible
- **WHEN** a returned service has accessible or special-seat availability greater than 0 and normal economy availability equal to 0
- **THEN** the normalized output does not mark the service as MVP-eligible

### Requirement: API failures are distinct from empty results
The system SHALL distinguish HTTP/API access failures from valid responses containing no matching trains or no eligible normal economy seats.

#### Scenario: API access fails
- **WHEN** the request fails because of timeout, network error, authentication failure, rate limiting, HTTP 5xx, invalid JSON, or unexpected response shape
- **THEN** the spike reports an API failure category with diagnostic context
- **AND** it does not report the result as no train or no seat

#### Scenario: Valid response has no matching service
- **WHEN** the API returns a valid response with no services matching the requested route and date
- **THEN** the spike reports a valid empty result separately from API failure

### Requirement: Sanitized real-response fixture can be produced
The system SHALL support saving a sanitized real TCDD response fixture when a real response is available and can be stored without secrets, credentials, personal data, or volatile authentication material.

#### Scenario: Sanitized fixture is saved
- **WHEN** the spike is run with fixture capture enabled and the real API response contains no retained secrets after sanitization
- **THEN** it writes a fixture that preserves the response structure needed for parser and filtering tests

#### Scenario: Fixture cannot be safely sanitized
- **WHEN** the response contains data that cannot be confidently sanitized
- **THEN** the spike skips fixture creation and reports why no fixture was written
