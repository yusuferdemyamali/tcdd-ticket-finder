## ADDED Requirements

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
