## Context

See `proposal.md` for motivation. The repository currently has isolated `app/tcdd` station/provider behavior and durable `app/ticket_searches` lifecycle behavior. There is no Telegram bot layer yet, and `python-telegram-bot` is not currently listed as a project dependency.

The Telegram flow must remain a thin application boundary: it should translate Telegram updates into station resolution and ticket-search service calls, not duplicate search validation, run SQL, or start background polling.

## Goals / Non-Goals

**Goals:**

- Add a minimal Telegram bot layer for `/start`, `/ara`, `/durum`, `/iptal`, and the required inline callbacks.
- Keep user authorization centralized so every command and callback rejects non-allowed users before reading or changing search state.
- Store only in-progress wizard state in Telegram conversation/user context; persist only confirmed searches through the ticket-search service.
- Use canonical station objects from the TCDD station provider and convert the Telegram date format to the domain date format only at the application boundary.
- Test critical command, wizard, validation, replacement, stale-callback, and unauthorized-user paths without contacting Telegram or TCDD network services.

**Non-Goals:**

- No scheduler, background polling, periodic TCDD availability checks, seat-found notification flow, outage/recovery notification, retry/backoff, restart button, or Docker deployment.
- No generic bot framework abstraction beyond what is needed to wire `python-telegram-bot` handlers.
- No change to raw TCDD parsing, availability filtering, or ticket-search persistence invariants unless needed to call existing APIs correctly.

## Decisions

1. Add a small `app/telegram/` package instead of putting handlers in existing domains.

   Rationale: Telegram code has its own dependency and update/callback concepts. Keeping it separate preserves `app/tcdd` and `app/ticket_searches` independence.

   Alternative considered: place command handlers in `app/ticket_searches`. Rejected because that would couple persistence/domain behavior to Telegram.

2. Use `python-telegram-bot` conversation handlers and lightweight callback payloads.

   Rationale: The MVP is a linear wizard with inline buttons, so the framework's built-in conversation state is sufficient. Callback payloads should encode action names plus a short wizard/session identifier or stable station/search identifier where applicable.

   Alternative considered: build a custom conversation engine. Rejected as unnecessary abstraction for one MVP flow.

3. Centralize authorization in a guard used by all command and callback handlers.

   Rationale: Unauthorized users must not see search details or mutate state. A common guard reduces the risk of one handler forgetting the check.

   Alternative considered: checking authorization only at `/start`. Rejected because callbacks and direct commands can arrive independently.

4. Keep replacement wizard state separate from persisted search state.

   Rationale: An old active search must keep running while the user edits a replacement. The handler should call normal create behavior when there was no active search at wizard start, and existing atomic replacement behavior only after confirming a replacement wizard.

   Alternative considered: cancel the old search when replacement starts. Rejected because it violates the required safety behavior.

5. Resolve station candidates at the station step and store canonical selections in wizard state.

   Rationale: Confirmation and creation should use stable station ids/names rather than user-entered free text. Ambiguous station callbacks can refer to a candidate id captured in current wizard state, preventing arbitrary payloads from injecting unknown stations.

   Alternative considered: defer station resolution until final confirmation. Rejected because it delays user feedback and makes ambiguous station selection harder.

6. Validate user-facing date/time format in Telegram before calling the domain service, then rely on domain validation again at creation.

   Rationale: Telegram needs friendly retry prompts for invalid input, while the domain remains the final guard for past dates and invalid ranges.

   Alternative considered: let only the domain reject all validation errors at confirmation time. Rejected because it gives poor wizard UX and could collect unusable intermediate state.

## Risks / Trade-offs

- In-memory wizard state is lost on process restart -> acceptable for MVP because only confirmed searches must be durable; the user can restart the wizard.
- Station candidate callback data may exceed Telegram callback limits if full names are encoded -> encode compact identifiers and keep candidate details in conversation state.
- Concurrent commands from the same authorized user can stale an older wizard -> include a current wizard/session token and reject callbacks that do not match current state.
- Adding `python-telegram-bot` changes the dependency set -> keep it as the only new runtime dependency for this change.
- Tests can become brittle if they depend on Telegram internals -> isolate formatting and handler dependencies enough to test with fake updates/services without adding a large abstraction layer.

## Migration Plan

1. Add the Telegram dependency and configuration fields.
2. Add the Telegram package and handlers while keeping existing tests green.
3. Add Telegram flow tests using fake station provider and ticket-search service/repository instances.
4. Verify current TCDD provider and ticket-search tests still pass.

Rollback: remove the Telegram package and dependency; no data migration is required because this change introduces no new persistent schema.
