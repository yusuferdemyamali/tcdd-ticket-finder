## 1. Spike Setup

- [x] 1.1 Create `scripts/spike_tcdd.py` with command-line arguments for origin station, destination station, travel date, and optional fixture capture; verify `python scripts/spike_tcdd.py --help` documents the inputs.
- [x] 1.2 Add only the minimal Python project/test scaffolding needed to run the spike and its checks; verify dependency installation or the chosen no-new-dependency path is documented in the repository.

## 2. TCDD HTTP Discovery

- [x] 2.1 Identify the real TCDD web endpoint, method, headers, payload, and auth/token behavior for station lookup; verify the spike prints the canonical station records or identifiers for a real route.
- [x] 2.2 Identify the real TCDD web endpoint, method, headers, payload, and auth/token behavior for service search; verify the spike fetches services for a real origin, destination, and date without Playwright.
- [x] 2.3 If the HTTP request fails, diagnose endpoint, token, header, payload, TLS/fingerprint, and HTTP behavior without adding Playwright; verify the spike reports the failure category and diagnostic context.

## 3. Normalization and Classification

- [x] 3.1 Normalize returned services into route, departure date, departure time, arrival time, and raw journey identifier fields where available; verify terminal output shows these fields for live data.
- [x] 3.2 Filter services whose departure date differs from the requested travel date; verify a parser or fixture-based test covers wrong-date exclusion.
- [x] 3.3 Extract normal economy availability separately from business and accessible/special availability; verify tests cover economy `0`, economy `>= 1`, business-only, and accessible-only cases.
- [x] 3.4 Mark MVP eligibility only when normal economy availability is at least `1`; verify terminal output distinguishes eligible services from valid services with no eligible normal economy seats.

## 4. Failure Semantics and Fixtures

- [x] 4.1 Represent station lookup failure, API/access failure, valid empty results, no eligible seats, and eligible seats as distinct outcomes; verify tests or scripted runs show API failures are not reported as empty results.
- [x] 4.2 Add optional sanitized fixture capture for real responses when safe; verify generated fixture content preserves parser-relevant structure and excludes secrets, credentials, tokens, personal data, and volatile authentication material.
- [x] 4.3 If fixture capture cannot be safely sanitized, skip writing the fixture and report the reason; verify this path does not create a fixture file.

## 5. End-to-End Validation

- [x] 5.1 Run the spike against a real TCDD origin, destination, and travel date; verify the terminal output proves station resolution, service retrieval, parsed times, separated seat categories, requested-date filtering, and final outcome classification.
- [x] 5.2 Run the project test/validation commands added for the spike; verify all tests pass and no production `TcddClient`, Telegram, SQLite, scheduler, or Playwright implementation was added.
