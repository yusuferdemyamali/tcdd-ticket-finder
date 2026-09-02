## Why

The current ticket monitoring flow must not silently stop after a process/container restart, temporary TCDD outage, retry delay, or Telegram notification failure. This change hardens the existing MVP monitoring behavior so an active search continues reliably and a found-ticket notification is not lost before completion.

## What Changes

- Recover persisted `ACTIVE` and `FOUND` searches during application startup without requiring the user to run `/ara` again.
- Persist monitoring check timestamps, restart-safe `next_check_at`, TCDD outage state, and last TCDD error metadata during real TCDD checks.
- Retry found-ticket notification for persisted `FOUND` searches and keep the search out of `COMPLETED` until Telegram delivery succeeds.
- Treat typed TCDD failures as outages, not empty availability, with one persisted outage notification per outage and one recovery notification after the first successful check.
- Apply simple retry backoff for repeated TCDD failures while preserving the normal random 60-90 second polling interval after success.
- Keep expiration checks active during outage/backoff so searches can still become `EXPIRED` after the travel window passes.
- Prevent duplicate monitoring loops for the same search in one application instance and keep Telegram handler construction testable without starting polling.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `ticket-monitoring`: Add restart recovery, persisted polling scheduling, notification retry, outage/recovery handling, backoff, expiration during outage, and duplicate-loop prevention requirements.
- `ticket-searches`: Clarify durable monitoring metadata updates, found notification retry data, and persisted outage notification state needed by monitoring recovery.
- `telegram-search-flow`: Add user-facing outage, authentication, recovery, and retried found-ticket notification behavior.
- `tcdd-provider`: Clarify that existing typed TCDD errors remain distinct from valid empty results for monitoring reliability.

## Impact

- Affected code areas: application startup/lifecycle wiring, monitoring orchestration, ticket-search domain persistence/service methods, Telegram notification surface, and tests around monitoring and providers.
- No new product features, dependencies, TCDD endpoint discovery, token refresh, Docker changes, multi-user support, web panel, Playwright, or purchase automation.
- Existing MVP behavior remains: single user, single active search, normal economy only, random 60-90 second successful polling, all eligible trains in one notification, and completion only after successful Telegram notification.
