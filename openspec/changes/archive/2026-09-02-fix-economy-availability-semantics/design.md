## Context

See `proposal.md` for motivation. The current parser in `app/tcdd/parser.py` derives `TrainAvailability.economy_available` from `bookingClassCapacities[].capacity`, while the sanitized real fixture shows sellable cabin availability under each train's `availableFareInfo[].cabinClasses[].availabilityCount`.

The normalized provider boundary is already correct for downstream callers: `TrainAvailability` exposes only `economy_available`, and monitoring consumes normalized records. The fix should change parser semantics without changing that model or moving raw response parsing outside `app/tcdd`.

## Goals / Non-Goals

**Goals:**

- Make `economy_available` represent normal economy sellable availability, not total capacity.
- Keep business, wheelchair/accessible, and special-seat availability isolated from normal economy.
- Prevent duplicate fare-family entries for the same economy inventory from inflating the count.
- Preserve the existing TCDD provider interface and downstream monitoring boundary.

**Non-Goals:**

- Do not fix the runtime monitoring activation bug in this change.
- Do not add token refresh, endpoint discovery, Playwright, Telegram flow changes, or persistence changes.
- Do not expose `availableFareInfo`, cabin classes, or any raw TCDD response shape outside `app/tcdd`.

## Decisions

1. Source economy availability from `availableFareInfo[].cabinClasses[]`.

   The parser should scan each train's fare information and identify normal economy cabin class entries by stable cabin identity, primarily `cabinClass.id == 2`, with normalized cabin name matching as a defensive fallback for fixture variations. It should read the cabin entry's `availabilityCount` and ignore `bookingClassCapacities[].capacity` for availability.

   Alternative considered: read `bookingClassAvailabilities[].availability`. That is more nested, fare-family-specific, and repeats information already summarized at cabin level in the verified fixture. Cabin-level `availabilityCount` is the clearer source of the normalized cabin result.

2. Use one deterministic economy count, not a sum across fare families.

   If multiple economy cabin entries are found across fare families, the parser should not add them together. It should select one deterministic inventory-preserving value, with `max(availabilityCount)` as the preferred rule because it avoids duplicate inflation and preserves the best observed sellable count when fare-family entries represent the same seat inventory with different commercial views.

   Alternative considered: first-seen value. That avoids inflation but depends on response ordering and can under-report if TCDD lists a restricted fare family before the full inventory view.

3. Keep the provider model unchanged.

   `TrainAvailability.economy_available` remains an `int`. The parser hides all TCDD-specific cabin and fare-family response details inside `app/tcdd`, so monitoring and persistence continue to operate only on normalized records.

   Alternative considered: expose cabin-level detail in `TrainAvailability`. That would leak raw provider semantics and expand downstream responsibilities without an MVP need.

4. Treat missing economy fare information as zero availability for that train.

   A train with valid timing and identifiers but no normal economy cabin entry should still normalize with `economy_available=0`, matching existing downstream filtering semantics.

   Alternative considered: raise an unexpected-response error when economy cabin data is absent. That would make business-only or accessible-only trains look like provider failures instead of valid unavailable economy results.

## Risks / Trade-offs

- [Risk] TCDD may use localized cabin names with Turkish dotted characters or ASCII variants -> Mitigation: prefer `cabinClass.id == 2` and normalize names only as fallback.
- [Risk] Future TCDD responses may represent genuinely separate economy inventories -> Mitigation: do not sum until verified by real fixtures; add regression tests around duplicate fare-family behavior.
- [Risk] Existing tests assert capacity-derived fixture values -> Mitigation: update those assertions to known `availabilityCount` values from `tests/fixtures/tcdd_real_response.json`.
- [Risk] A live TCDD query requires valid `TCDD_TOKEN` and network access -> Mitigation: make automated regression tests fixture-based and treat live verification as an environment-dependent check.

## Migration Plan

No data migration is required. Deploying the parser fix changes only future normalized availability results. Rollback is the previous parser behavior, but rollback would reintroduce capacity-derived false positives and should be avoided unless the new fixture-based tests reveal a parser regression.
