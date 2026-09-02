## 1. Runtime Entrypoint

- [ ] 1.1 Inspect existing Telegram, monitoring, TCDD, and ticket-search construction paths and verify the chosen startup wiring does not change existing domain behavior.
- [ ] 1.2 Add the minimal production startup module or command that reads `DATABASE_PATH`, initializes SQLite, builds services/providers, starts Telegram polling, and starts monitoring; verify it can be imported without starting external network calls.
- [ ] 1.3 Ensure startup creates or validates the parent directory for the configured SQLite database path; verify an empty configured path initializes a readable SQLite database file.

## 2. Docker Runtime Files

- [ ] 2.1 Add a single-stage Python 3.12+ `Dockerfile` that installs production dependencies only; verify `docker build` succeeds.
- [ ] 2.2 Decide whether the production image needs the existing `curl` optional dependency by inspecting runtime imports; verify the final install command does not include test dependencies.
- [ ] 2.3 Add `docker-compose.yml` with one application service, environment-variable configuration, restart policy, and a named SQLite data volume; verify `docker compose config` succeeds.
- [ ] 2.4 Add `.env.example` with placeholder values for Telegram, TCDD, database path, and monitoring interval variables; verify no real secret values are present.

## 3. Persistence And Recovery Verification

- [ ] 3.1 Verify the Compose service sets `DATABASE_PATH` to the mounted volume path and that `docker compose up` creates the SQLite database on that volume.
- [ ] 3.2 Verify an `ACTIVE` search persisted before container restart remains readable and eligible for monitoring after restart.
- [ ] 3.3 Verify a `FOUND` search persisted before container restart remains available to the existing notification recovery behavior after restart.
- [ ] 3.4 Verify container recreate with the named volume retained preserves SQLite ticket-search records.

## 4. Safety And Regression Checks

- [ ] 4.1 Run the existing test suite and verify it passes without changing TCDD, Telegram, monitoring, or ticket-search behavior.
- [ ] 4.2 Inspect `Dockerfile`, `docker-compose.yml`, `.env.example`, and repository changes for hardcoded `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, `TCDD_TOKEN`, or real secret values.
- [ ] 4.3 Verify the change does not add CI/CD, Kubernetes, Coolify-specific config, reverse proxy, cloud deployment, dashboards, backups, web panel, or other out-of-scope features.
