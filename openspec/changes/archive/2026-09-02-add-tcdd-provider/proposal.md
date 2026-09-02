## Why

The validated TCDD API spike proved that the MVP can query real train availability without Playwright, but the application still lacks a production integration layer. This change turns the verified HTTP behavior into isolated `app/tcdd` production code that returns normalized models and preserves the MVP economy-seat invariant.

## What Changes

- Add a production TCDD provider layer under `app/tcdd/` with client, station, parser, model, and exception modules.
- Resolve canonical TCDD station records from the verified station-pairs CDN source with a simple cache.
- Query the verified `train-availability` endpoint using `httpx`, required headers, `unit-id: 3895`, `passengerTypeId=1`, `count=1`, and `TCDD_TOKEN` as the authentication source.
- Parse real TCDD responses into normalized `TrainAvailability` records without leaking raw TCDD JSON outside `app/tcdd`.
- Preserve the invariant that only normal economy category availability (`categoryId=1`) counts as MVP-eligible availability.
- Map TCDD/API failures to meaningful production exceptions instead of returning empty results.
- Keep `scripts/spike_tcdd.py` as a standalone spike/debug tool and do not make production code depend on it.

## Capabilities

### New Capabilities
- `tcdd-provider`: Production TCDD integration for canonical station lookup, availability search, normalized parsing, and API failure semantics.

### Modified Capabilities
- None.

## Impact

- Affected code: `app/tcdd/client.py`, `app/tcdd/parser.py`, `app/tcdd/stations.py`, `app/tcdd/models.py`, `app/tcdd/exceptions.py`, and focused tests/fixtures for parser and provider behavior.
- External systems: TCDD station-pairs CDN and TCDD `tms/train/train-availability` service.
- Configuration: `TCDD_TOKEN` environment variable becomes the production authentication source for this provider.
- Out of scope: Telegram bot, SQLite ticket-search persistence, scheduler, polling, notifications, Docker deployment, Playwright, token scraping, and automatic token refresh.
