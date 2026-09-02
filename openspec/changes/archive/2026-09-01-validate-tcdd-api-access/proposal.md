## Why

Before production TCDD integration begins, the project needs proof that the real TCDD web API can be accessed without Playwright and that its response structure supports the MVP availability rules. This reduces the risk of building `TcddClient`, polling, persistence, or Telegram behavior on unverified assumptions.

## What Changes

- Add an isolated technical spike under `scripts/spike_tcdd.py` to validate real TCDD web API access from the terminal.
- Discover and document the endpoint, request headers, payload shape, authentication or token behavior, and HTTP/TLS constraints needed to fetch train services.
- Normalize real API responses into a secret-free terminal output that shows stations, journeys, dates/times, and normal economy availability separately from business and accessible seats.
- Distinguish API/access failures from valid empty results so failures are not treated as "no train" or "no seat".
- Optionally create sanitized real-response fixtures for later parser/filtering tests when the API response can be captured without secrets.
- Do not implement production `TcddClient`, Telegram bot behavior, SQLite persistence, scheduler behavior, or Playwright automation in this change.

## Capabilities

### New Capabilities
- `tcdd-api-spike`: Defines the behavior and scope for validating real TCDD web API access and normalized availability extraction through an isolated spike script.

### Modified Capabilities
- None.

## Impact

- Affected files are expected to be limited to spike tooling under `scripts/`, optional sanitized fixtures under a test fixture location, and documentation or tests that directly support the spike.
- No production runtime behavior should change.
- No new long-lived dependency should be introduced unless API access cannot be validated with existing HTTP tooling and the reason is documented.
