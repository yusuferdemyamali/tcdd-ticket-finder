## 1. Production Package Surface

- [x] 1.1 Create the minimal `app/tcdd` package files for client, stations, parser, models, and exceptions; verify `python -c "import app.tcdd"` succeeds without importing Telegram, SQLite, scheduler, notification, Docker, Playwright, or `scripts.spike_tcdd`.
- [x] 1.2 Define normalized `Station` and `TrainAvailability` models with canonical station identifiers and the required train fields; verify unit tests can instantiate them and they contain no raw TCDD JSON field.
- [x] 1.3 Define typed TCDD exception classes for station lookup, ambiguity, network/timeout, authentication, rate limit, server error, invalid JSON, unexpected response, and TLS/WAF failures; verify exception tests assert the expected class for each category.

## 2. Station Lookup

- [x] 2.1 Implement station-pairs fetching from `https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json` with a per-client in-memory cache; verify a mocked station source is fetched once across repeated lookups.
- [x] 2.2 Normalize station-pairs records into `Station` objects; verify tests assert downstream callers receive normalized models rather than raw station-pairs dictionaries.
- [x] 2.3 Implement station search with Turkish-character folding and exact-match priority; verify tests resolve `Söğütlüçeşme`, `sogutlucesme`, and `Ankara` to their canonical TCDD records from station-pairs fixture data.
- [x] 2.4 Implement single-station lookup failure and ambiguity handling; verify unknown stations and ambiguous non-exact queries raise explicit station errors without running train search.

## 3. Response Parsing

- [x] 3.1 Implement train availability parsing for the verified response shape using `tests/fixtures/tcdd_real_response.json`; verify fixture-based tests return normalized `TrainAvailability` records with train ID, train name/number, departure, arrival, and economy availability.
- [x] 3.2 Implement requested travel-date filtering using local departure date; verify wrong-date trains from synthetic data are excluded while same-date trains remain.
- [x] 3.3 Implement booking category extraction with normal economy category `1`; verify economy `0` is preserved as `0` and economy `>=1` is preserved as the returned count.
- [x] 3.4 Keep business category `4`, accessible category `23`, and special categories such as `22` separate from economy; verify business-only, accessible-only, and special-only fixtures never increase `economy_available`.
- [x] 3.5 Treat invalid JSON-compatible objects or incompatible response shapes as parser errors; verify malformed responses raise TCDD invalid/unexpected response exceptions instead of returning `[]`.

## 4. Production Client

- [x] 4.1 Implement `TcddClient` station methods for get/search stations using the station cache; verify mocked tests cover successful canonical lookup and search result ordering.
- [x] 4.2 Implement `TcddClient.search_trains(origin_station_id, destination_station_id, travel_date)` with the verified `gise-api-prod` URL, `unit-id: 3895`, browser-origin headers, `passengerTypeId=1`, and `count=1`; verify an `httpx` mock transport captures the expected URL, headers, and JSON payload.
- [x] 4.3 Read production authorization only from `TCDD_TOKEN`; verify missing token raises an authentication error and tests confirm no hardcoded JWT, bundle scraping, `TCDD_AUTH_TOKEN`, or token refresh path is used.
- [x] 4.4 Map `httpx` network errors, timeouts, 401/403 authentication responses, 429 rate limits, HTTP 5xx responses, invalid JSON, unexpected response shape, and TLS/WAF signals to typed TCDD exceptions; verify mocked client tests distinguish every failure from a valid empty list.
- [x] 4.5 Add optional `curl_cffi` Chrome 120 fallback only for TLS/WAF-compatible failures when the package is installed; verify tests show `httpx` remains the default and `web-api-prod` is never used as the primary endpoint.

## 5. Verification And Scope Control

- [x] 5.1 Add production parser/client/station tests without importing `scripts.spike_tcdd`; verify the existing spike script remains runnable as a standalone debug tool.
- [x] 5.2 Run `pytest`; verify fixture parser tests, station lookup tests, request-construction tests, and failure-mapping tests pass.
- [x] 5.3 Run `openspec validate add-tcdd-provider --strict`; verify the change artifacts and implemented behavior satisfy the `tcdd-provider` spec.
