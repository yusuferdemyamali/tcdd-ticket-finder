## Why

The MVP needs a Telegram-facing flow so the single allowed user can create, inspect, and cancel a persistent ticket search without direct database access. This is the next layer above the already isolated TCDD provider and durable ticket-search domain.

## What Changes

- Add Telegram bot configuration for `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USER_ID` without logging secret values.
- Add authorization checks so only the configured Telegram user can read or mutate search state.
- Add `/start`, `/ara`, `/durum`, and `/iptal` Telegram behavior for the MVP single-user flow.
- Add a `/ara` conversation that resolves canonical TCDD stations, validates `DD.MM.YYYY` dates and `HH:MM` time windows, shows a confirmation summary, and creates a search only after confirmation.
- Preserve an existing `ACTIVE` search during a replacement wizard and use the existing atomic `replace_active_search` behavior only after the user confirms the new search.
- Keep Telegram handlers behind the existing TCDD station-provider and `TicketSearchService`/repository boundaries; handlers must not execute SQLite directly.
- Exclude background polling, scheduler work, seat-found notifications, retry/backoff, outage/recovery messaging, restart buttons, and Docker deployment from this change.

## Capabilities

### New Capabilities
- `telegram-search-flow`: Telegram command and conversation behavior for authorized MVP ticket-search creation, replacement, status viewing, and cancellation.

### Modified Capabilities

## Impact

- Affected code areas: new Telegram bot entry/handler code, configuration loading, and tests for Telegram flows.
- Existing integrations: uses `app/tcdd` station resolution and `app/ticket_searches` service/repository behavior without exposing raw TCDD response shapes or direct SQL in Telegram handlers.
- Dependencies: likely adds `python-telegram-bot` if not already present; no Playwright, scheduler, Docker, or background polling dependency is part of this change.
