## Context

See `proposal.md` for motivation. The current codebase has separate building blocks for Telegram application construction, monitoring orchestration, SQLite initialization, ticket-search service/repository, and TCDD provider access. Configuration is already environment-driven for Telegram credentials, monitoring interval values, and `TCDD_TOKEN`, but the repository does not expose a single production startup module for running Telegram polling and monitoring together.

SQLite is already the source of truth for ticket-search records. The containerization work should therefore keep persistence behavior unchanged and make the runtime path durable by pointing `DATABASE_PATH` at a mounted volume location.

## Goals / Non-Goals

**Goals:**
- Provide a minimal production Docker image based on Python 3.12 or newer.
- Provide Compose configuration that runs one application service and mounts a persistent SQLite data volume.
- Add a small startup entrypoint only if needed to connect the existing Telegram, monitoring, TCDD, and ticket-search components.
- Keep secrets runtime-only through environment variables and `.env.example` placeholders.
- Verify Docker build, Compose config validity, and the existing test suite.

**Non-Goals:**
- No CI/CD, Kubernetes, Coolify-specific files, reverse proxy, cloud deployment, dashboards, backups, or web panel.
- No changes to TCDD parsing, Telegram conversation behavior, monitoring eligibility rules, or ticket-search state transitions.
- No new database engine or persistence abstraction.

## Decisions

1. Use a single-stage Python slim image.

   Rationale: The user explicitly requested a simple image without unnecessary multi-stage complexity. A slim Python 3.12+ base keeps the runtime small enough while avoiding extra build orchestration.

   Alternative considered: Multi-stage build with wheels copied into a runtime image. Rejected because the project is small and the added complexity is not needed for this MVP containerization.

2. Install the project with production extras only where production behavior needs them.

   Rationale: The base dependencies are declared in `pyproject.toml`; `curl_cffi` is optional. If current production TCDD behavior can run with `httpx` alone, install the base project. If the TCDD client has an optional production path that imports `curl_cffi`, include the existing optional extra without changing TCDD behavior.

   Alternative considered: Install test extras in the image. Rejected because test dependencies and development tools should not be included in the production image.

3. Add a minimal application startup module if no production entrypoint exists.

   Rationale: Compose needs one stable command that initializes SQLite from `DATABASE_PATH`, builds the ticket-search service, builds the TCDD provider, starts Telegram polling, and starts monitoring for persisted searches. Keeping that wiring in one thin module avoids moving domain logic into Docker files or Telegram handlers.

   Alternative considered: Put orchestration in a shell entrypoint script. Rejected because lifecycle coordination between Telegram polling and async monitoring belongs in Python where the components already exist.

4. Use a Docker named volume mounted to a fixed app data directory.

   Rationale: A named volume survives container recreate by default and keeps local setup simple with `docker compose up`. The Compose service should set `DATABASE_PATH` to a file under that mount, for example `/data/tcdd-ticket.sqlite3`.

   Alternative considered: Bind-mount a host path. Rejected as the default because it is less portable and more host-specific, though users can still override Compose locally if needed.

5. Keep secrets out of build arguments and committed files.

   Rationale: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, and `TCDD_TOKEN` are runtime configuration. Compose should read them from the operator environment or `.env`, and `.env.example` should contain placeholders only.

   Alternative considered: Use Docker build args for secrets. Rejected because build args can appear in image metadata/history and are not needed for runtime configuration.

## Risks / Trade-offs

- Entrypoint lifecycle mismatch -> Mitigation: implement startup using existing Telegram application and monitoring service APIs, then verify Telegram polling and monitoring startup behavior in a targeted test or smoke path.
- SQLite directory missing or unwritable -> Mitigation: create the parent directory for `DATABASE_PATH` during startup or ensure the image/Compose runtime prepares the mounted directory with writable permissions.
- Optional `curl_cffi` production need is unclear -> Mitigation: inspect current imports during implementation and include only the existing optional extra if production TCDD code imports it or requires it for verified behavior.
- Existing `FOUND` notification recovery may be in an in-progress change -> Mitigation: do not redesign recovery; wire container startup so persisted `FOUND` state remains available to whichever existing recovery behavior the codebase provides.
- OpenSpec config parse warning can hide validation issues -> Mitigation: run the required OpenSpec status/validation commands and report the config warning separately if it remains unrelated to this change.

## Migration Plan

1. Build the Docker image locally with no secrets passed at build time.
2. Start the service with `docker compose up` using a real local `.env` that is not committed.
3. Confirm SQLite is created under the mounted volume path and an `ACTIVE` search remains present after container restart.
4. Recreate the container while retaining the named volume and confirm persisted search state is still readable.
5. Roll back by stopping the Compose service; the named volume can be retained for data or removed manually by the operator if no longer needed.
