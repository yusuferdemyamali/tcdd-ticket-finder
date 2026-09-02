## Why

Runtime-created `ACTIVE` searches are currently persisted but not picked up by monitoring until the container restarts. This leaves a newly started Telegram search idle with empty monitoring timestamps, even though startup recovery can later resume it.

## What Changes

- Add a runtime activation path so newly created `ACTIVE` searches are picked up by the existing monitoring lifecycle without requiring application restart.
- Ensure searches activated through `replace_active_search` and `restart_search` are also picked up by monitoring.
- Keep startup recovery behavior for persisted `ACTIVE` and `FOUND` searches intact.
- Prevent duplicate monitoring loops/tasks within one application instance and prevent concurrent duplicate TCDD checks for the same search.
- Preserve the existing 60-90 second normal polling semantics and durable `last_checked_at` / `next_check_at` updates.
- Keep monitoring orchestration cleanly behind the monitoring service instead of tightly coupling Telegram handlers to scheduling internals.
- Exclude TCDD parser semantics, new TCDD endpoints, retry/backoff redesign, Telegram UX changes, Docker architecture changes, and multi-user support.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `ticket-monitoring`: Monitoring must discover or be woken for runtime `ACTIVE` searches, not only startup-recovered searches, while preserving duplicate-loop and non-active-search protections.

## Impact

- Affected code is expected around the monitoring lifecycle/service, application startup wiring, and tests that exercise runtime activation.
- Ticket-search domain behavior may be used as the activation source, but Telegram handlers should not directly own monitoring loop management.
- Existing startup recovery, Telegram flow, ticket-search, monitoring, and TCDD provider tests should continue to pass.
- No database schema change, TCDD provider contract change, Telegram UX change, Docker change, or new dependency is expected.
