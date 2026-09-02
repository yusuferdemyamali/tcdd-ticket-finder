## Context

See `proposal.md` for motivation. The repository currently has OpenSpec and project documentation but no production Python package, dependency file, or test suite. The project rules require the first TCDD development step to validate the real undocumented web API through `scripts/spike_tcdd.py` before making production assumptions.

The spike must be disposable and diagnostic: it can contain direct request and parsing logic while the API is being understood, but it must not establish production abstractions, persistence, bot handlers, a scheduler, or Playwright usage.

## Goals / Non-Goals

**Goals:**

- Provide a terminal command that can query a real TCDD route/date and print normalized, secret-free diagnostics.
- Verify station canonical lookup, journey search, date/time parsing, and seat-category extraction against live API responses.
- Preserve enough response structure in optional sanitized fixtures to support future parser/filter tests.
- Capture failure categories clearly so API failure is never confused with valid empty results.

**Non-Goals:**

- No production `TcddClient`, `app/tcdd/` integration, Telegram handlers, SQLite schema, scheduler, restart behavior, or domain service implementation.
- No Playwright fallback in this change.
- No automated booking, login, passenger selection, or checkout behavior.
- No guarantee that the spike's internal structure is a future production API.

## Decisions

### Keep the spike as a standalone script

Implement the first validation surface as `scripts/spike_tcdd.py` with command-line arguments for origin, destination, and date.

Rationale: the goal is to validate live HTTP behavior before production code exists. A script can expose raw diagnostics and evolve quickly without locking in package APIs.

Alternatives considered:

- Production package first: rejected because it would encode unverified response-shape and auth assumptions.
- Notebook or ad-hoc shell commands: rejected because acceptance criteria require a repeatable terminal command.

### Use HTTP-first discovery and fail before browser automation

The implementation should inspect TCDD web requests and reproduce them with Python HTTP tooling. If a basic client fails, diagnostics should focus on endpoint, token, header, payload, TLS/fingerprint, and HTTP behavior rather than switching to Playwright.

Rationale: Playwright is explicitly outside MVP scope, and using it in the spike would not prove that the production HTTP integration is viable.

Alternatives considered:

- Add Playwright as fallback: rejected by scope and because it hides the HTTP contract the project needs to understand.
- Assume documented endpoints: rejected because the integration target is undocumented and must be verified against live behavior.

### Normalize output separately from raw response capture

The spike should print a normalized summary with station records, journey identifiers if present, departure/arrival values, requested-date match status, normal economy availability, business availability, accessible/special availability, and MVP eligibility.

Raw responses should only be written when an explicit fixture-capture flag is provided and sanitization can remove volatile or sensitive fields.

Rationale: normalized output proves the MVP invariant, while optional fixtures preserve future test value without leaking secrets.

Alternatives considered:

- Print raw JSON only: rejected because it does not directly prove the MVP availability logic.
- Always save raw responses: rejected because of secret and volatility risk.

### Classify outcomes explicitly

The spike should use distinct terminal statuses for station lookup failure, API/access failure, valid empty route/date results, valid results with no MVP-eligible seats, and valid results with eligible normal economy seats.

Rationale: project error semantics require TCDD errors not to be treated as empty results. The spike should validate that distinction before production polling exists.

Alternatives considered:

- Return an empty list for all failures: rejected because it violates the project error semantics and masks integration problems.

## Risks / Trade-offs

- TCDD may require browser-like TLS/fingerprint behavior → Diagnose with headers, TLS behavior, and HTTP client differences; introduce `curl_cffi` only if standard HTTP tooling cannot reproduce the request and document why.
- TCDD response shape may vary by route, date, or train type → Use real response diagnostics and sanitized fixtures, then keep parser assumptions narrow.
- Station names may be ambiguous or localized → Show canonical station records before journey search and fail explicitly when resolution is not exact enough.
- Fixture sanitization may remove fields needed for future tests → Prefer preserving response shape and field names while removing secrets, tokens, request IDs, and volatile authentication material.
- Live API behavior can change after the spike passes → Record endpoint/header/payload/auth observations in the spike output or companion notes so future implementation can compare failures against the validated baseline.

## Migration Plan

No migration is required because this change creates isolated spike artifacts only and does not change production behavior. Rollback is deleting the spike files and optional fixtures created by the apply phase.

## Open Questions

- None.
