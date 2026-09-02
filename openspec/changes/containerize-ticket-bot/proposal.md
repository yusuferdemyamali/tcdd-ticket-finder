## Why

The completed MVP currently depends on local process setup, local environment variables, and a local SQLite path, which makes restart recovery and repeatable operation fragile outside the developer machine. Containerizing the bot makes production startup reproducible while preserving SQLite-backed ticket-search state across container restarts and recreates.

## What Changes

- Add a minimal Python 3.12+ Docker image for production runtime dependencies only.
- Add Docker Compose configuration that starts the existing Telegram bot plus monitoring lifecycle.
- Add runtime/startup configuration so the application can be launched consistently inside the container.
- Store SQLite data under a Docker persistent volume and align `DATABASE_PATH` with that mounted path.
- Add `.env.example` with placeholders for required runtime configuration.
- Keep `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, and `TCDD_TOKEN` outside the image and repository.
- Do not add CI/CD, Kubernetes, Coolify-specific config, cloud deployment, reverse proxy, dashboards, backups, or new application features.

## Capabilities

### New Capabilities
- `container-runtime`: Defines the Docker and Docker Compose runtime behavior required to run the Telegram ticket bot, monitoring lifecycle, and persistent SQLite storage safely.

### Modified Capabilities
- `ticket-searches`: Clarifies that persisted ticket-search state must survive container restart and recreate when SQLite is stored on the configured persistent volume.
- `ticket-monitoring`: Clarifies that monitoring restart recovery for `ACTIVE` and `FOUND` searches must operate after a container restart using persisted state.

## Impact

- Adds Docker runtime files such as `Dockerfile`, `docker-compose.yml`, and `.env.example`.
- Adds or wires an application startup command if the current codebase lacks a single production entrypoint.
- Uses existing Python package dependencies, including optional `curl_cffi` only where needed for production TCDD behavior.
- Does not change TCDD provider behavior, Telegram command behavior, monitoring rules, ticket-search state transitions, or database schema beyond path/runtime configuration needed for container operation.
