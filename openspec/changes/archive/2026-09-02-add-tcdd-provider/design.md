## Context

See `proposal.md` for motivation. The repository currently has a validated TCDD spike in `scripts/spike_tcdd.py`, spike-focused parser tests, and a real sanitized fixture at `tests/fixtures/tcdd_real_response.json`, but no production `app/tcdd` package.

The prior spike validated the station CDN, the `gise-api-prod` train-availability endpoint, required request headers, passenger count shape, booking-class category IDs, and failure categories. Production code should use those verified facts without importing or depending on the spike script.

## Goals / Non-Goals

**Goals:**

- Introduce a minimal production `app/tcdd` provider surface for station search/lookup and train availability search.
- Normalize station and train availability data into stable Python models before any caller sees it.
- Keep raw TCDD response shape, request diagnostics, and category details contained inside `app/tcdd`.
- Preserve the normal economy invariant with fixture-backed parser tests.
- Convert TCDD access and response failures into typed production exceptions.

**Non-Goals:**

- No Telegram handlers, SQLite search persistence, scheduler, polling loop, notification workflow, Docker deployment, or Playwright automation.
- No token scraping, JavaScript bundle parsing, hardcoded JWT fallback, or automatic token refresh.
- No production dependency on `scripts/spike_tcdd.py`.

## Decisions

### Create a small isolated `app/tcdd` package

Add the production integration behind `app/tcdd/client.py`, `app/tcdd/stations.py`, `app/tcdd/parser.py`, `app/tcdd/models.py`, and `app/tcdd/exceptions.py`. Add package marker files only if needed for imports.

Rationale: the project rules require the TCDD integration to stay isolated and prevent raw response formats from leaking into Telegram, persistence, or search-domain layers.

Alternatives considered:

- Reuse spike functions directly: rejected because the spike contains diagnostics, hardcoded-token discovery behavior, raw fields, and CLI concerns that should not become production API.
- Put TCDD calls into future search or bot services: rejected because it would couple external API behavior to application orchestration too early.

### Keep public models minimal and normalized

Expose `Station` records with canonical TCDD identifiers and display fields needed for requests. Expose `TrainAvailability` with `train_id`, `train_name`, `train_number`, `departure_at`, `arrival_at`, and `economy_available`.

The parser may compute business, accessible, and special-seat counts internally to protect the invariant, but those counts should not be carried into the MVP domain model unless a later requirement needs them.

Rationale: downstream code needs stable data, not TCDD's nested response shape or non-MVP categories.

Alternatives considered:

- Include every booking category in `TrainAvailability`: rejected because it expands the domain model beyond MVP needs.
- Return raw dictionaries plus helper functions: rejected because it leaks TCDD response structure outside `app/tcdd`.

### Use lazy station loading with a simple in-memory cache

Load `station-pairs-INTERNET.json` through the station source on first station search/lookup, normalize names with Turkish-character folding, and keep the parsed `Station` list in the provider instance for subsequent calls. Provide search returning candidate stations and canonical lookup that returns a single station or raises an explicit lookup/ambiguity error.

Rationale: station data is external but relatively static; a per-process cache avoids repeated CDN calls without adding persistence or invalidation complexity.

Alternatives considered:

- Persist station data in SQLite: rejected because persistence is out of scope for this change.
- Fetch station data on every lookup: rejected because it adds avoidable network dependency to every search request.

### Use `httpx` first and keep `curl_cffi` optional

Use `httpx` for station and train-availability HTTP calls. If a TLS/WAF failure is detected and `curl_cffi` is installed, retry with Chrome 120 impersonation. Do not use the `web-api-prod` host as the primary endpoint.

Rationale: the spike verified that `httpx` works in the target environment, while `curl_cffi` is only a fallback for TLS/WAF variance.

Alternatives considered:

- Add `curl_cffi` as a required dependency: rejected because `httpx` is verified and already a required dependency.
- Keep the spike's `web-api-prod` fallback: rejected because the validated environment returned WAF 403 there and the user explicitly excluded it as primary.

### Read authentication only from `TCDD_TOKEN`

Read the production JWT from `TCDD_TOKEN` when constructing availability requests. Missing or rejected tokens map to authentication exceptions. Authorization values must be omitted or redacted from logs and exception messages.

Rationale: token scraping and hardcoded JWTs are outside scope and would create secret-handling risk.

Alternatives considered:

- Reuse the spike's bundled-token discovery: rejected by scope and security constraints.
- Support multiple env var aliases: rejected because the request names `TCDD_TOKEN` as the production source.

### Treat parser shape failures as API failures, not empty availability

Validate top-level response containers before parsing. For each train, require usable identifiers, segment times, and booking capacities to produce a normalized result; wrong-date trains are filtered intentionally, while invalid JSON or incompatible response shape raises typed parser/client exceptions.

Rationale: returning `[]` for protocol or shape failures would violate the project error semantics and hide outages from future polling behavior.

Alternatives considered:

- Skip malformed trains silently: rejected because a changed TCDD response could look like no seats.
- Expose partial raw response for diagnostics: rejected because raw response leakage is explicitly forbidden outside the integration layer.

## Risks / Trade-offs

- TCDD token expiry or revocation -> Raise authentication errors clearly and require the operator to update `TCDD_TOKEN`; do not add refresh automation in this change.
- Station name ambiguity -> Return candidates from search and make canonical lookup raise an explicit ambiguity error instead of guessing.
- TCDD response shape changes -> Fixture-backed parser tests cover the known shape, and unexpected shape maps to typed errors rather than empty results.
- Optional TLS/WAF fallback may be unavailable -> Keep `curl_cffi` optional; if fallback is needed but not installed, raise a TLS/WAF error with no token leakage.
- Real endpoint tests can be flaky -> Use mocked HTTP clients for request construction/failure tests and fixture data for parser tests; do not require live API in the unit suite.

## Migration Plan

No data or deployment migration is required. This change adds an isolated provider package and tests without wiring it into Telegram, persistence, or scheduling.

Rollback is removing the new `app/tcdd` package and its focused tests. Existing spike behavior remains unchanged.

## Open Questions

- None.
