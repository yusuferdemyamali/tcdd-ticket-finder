# tcdd-provider Specification

## Purpose
Provide a production TCDD integration capability that resolves canonical stations, queries the verified train-availability service, and returns normalized train availability without exposing TCDD response internals.

## Requirements

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
The system SHALL compute normal economy availability only from the verified normal economy cabin availability count in TCDD fare information and SHALL NOT count train capacity, booking-class capacity, business availability, accessible availability, or special-seat availability as normal economy availability.

Normal economy availability SHALL be sourced from the economy cabin in `availableFareInfo[].cabinClasses[]` using its `availabilityCount`. When the same normal economy seat inventory appears through multiple fare-family entries, the normalized availability SHALL preserve the single real availability count deterministically and SHALL NOT sum duplicate fare-family entries.

#### Scenario: Economy availability is preserved
- **WHEN** a service has a normal economy cabin entry in fare information with `availabilityCount` greater than 0
- **THEN** the normalized train availability record preserves that count as normal economy availability
- **AND** the count is not replaced by train capacity or booking-class capacity

#### Scenario: Zero economy cabin availability remains unavailable
- **WHEN** a service has a normal economy cabin entry in fare information with `availabilityCount` equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Business-only availability is not economy availability
- **WHEN** a service has business cabin availability greater than 0 and normal economy cabin availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Accessible-only availability is not economy availability
- **WHEN** a service has wheelchair or accessible cabin availability greater than 0 and normal economy cabin availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Special-seat-only availability is not economy availability
- **WHEN** a service has special-seat availability greater than 0 and normal economy cabin availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Capacity fields are not used as availability
- **WHEN** a valid TCDD response contains train capacity, booking-class capacity, or similar total-capacity fields with values greater than the normal economy cabin `availabilityCount`
- **THEN** the normalized train availability record uses the normal economy cabin `availabilityCount`
- **AND** it does not expose capacity values as normal economy availability

#### Scenario: Duplicate fare-family economy entries do not inflate availability
- **WHEN** the same normal economy cabin inventory is represented under more than one fare-family entry in a valid TCDD response
- **THEN** the normalized train availability record preserves one deterministic normal economy availability count for that inventory
- **AND** it does not sum duplicate fare-family entries into an inflated count

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

### Requirement: Typed TCDD errors remain available to monitoring
The TCDD provider SHALL expose typed failures for availability-query problems so monitoring can distinguish outages from valid empty results.

The provider SHALL preserve distinct failure categories for network/timeout, authentication, rate limit, server error, invalid response, unexpected response, TLS, and WAF conditions, and SHALL NOT convert those failures into an empty normalized train list.

#### Scenario: Monitoring can distinguish network outage from no trains
- **WHEN** the availability request fails because of network or timeout behavior
- **THEN** the provider reports a typed TCDD failure to the caller
- **AND** it does not return an empty normalized train list

#### Scenario: Monitoring can distinguish authentication failure from no trains
- **WHEN** the availability request fails because the TCDD token is missing, rejected, or unauthorized
- **THEN** the provider reports an authentication TCDD failure to the caller
- **AND** it does not return an empty normalized train list

#### Scenario: Monitoring can distinguish response failure from no trains
- **WHEN** TCDD returns invalid JSON or an unexpected response shape
- **THEN** the provider reports an invalid-response or unexpected-response TCDD failure to the caller
- **AND** it does not return an empty normalized train list

#### Scenario: Monitoring can distinguish protection-layer failure from no trains
- **WHEN** the request fails because of TLS negotiation or WAF blocking behavior
- **THEN** the provider reports a TLS or WAF TCDD failure to the caller
- **AND** it does not return an empty normalized train list

### Requirement: Configured proxy applies only to TCDD endpoint requests
The production TCDD provider SHALL use `TCDD_PROXY_URL` as an outbound HTTP proxy for TCDD station and train-availability endpoint requests when that runtime environment variable is configured.

The provider SHALL keep proxy configuration scoped to TCDD integration traffic only. It SHALL NOT configure process-wide proxy behavior, route Telegram API traffic, route SQLite access, route monitoring orchestration, or introduce public proxy fallback or rotating proxy behavior.

#### Scenario: Station CDN uses configured proxy
- **WHEN** `TCDD_PROXY_URL` is set to an HTTP proxy URL and station lookup or station search requests canonical station data
- **THEN** the provider sends the station-pairs CDN HTTPS request through the configured proxy
- **AND** successful station responses are still returned as normalized station records

#### Scenario: Train availability uses configured proxy
- **WHEN** `TCDD_PROXY_URL` is set to an HTTP proxy URL and train availability is requested
- **THEN** the provider sends the production train-availability HTTPS request through the configured proxy
- **AND** successful train responses are still returned as normalized train availability records

#### Scenario: Unset proxy keeps direct TCDD access
- **WHEN** `TCDD_PROXY_URL` is unset or blank
- **THEN** the provider sends TCDD station and train-availability requests using direct outbound internet access
- **AND** existing TCDD authentication, request headers, endpoint selection, and response normalization behavior are preserved

#### Scenario: Proxy failures remain TCDD failures
- **WHEN** a configured TCDD proxy is unreachable, times out, fails TLS tunneling, or returns a protocol error during TCDD access
- **THEN** the provider reports the existing typed TCDD failure semantics instead of returning an empty station or train result
- **AND** it does not log `TCDD_TOKEN`, `TCDD_PROXY_URL` credentials if present, `TAILSCALE_AUTHKEY`, or other secret values

#### Scenario: Non-TCDD traffic is unaffected by provider proxy configuration
- **WHEN** `TCDD_PROXY_URL` is configured for the TCDD provider
- **THEN** the provider does not expose a global proxy setting for Telegram, monitoring, persistence, or unrelated HTTP clients
- **AND** only HTTP requests made by the TCDD integration capability use that proxy setting
