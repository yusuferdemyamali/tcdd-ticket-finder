## Why

The current TCDD provider parser can report total train or booking-class capacity as `TrainAvailability.economy_available`, producing unrealistic counts such as 354, 424, 778, or 848. Sanitized real runtime fixtures confirm that sellable normal economy availability is under `trainLegs -> ... -> availableFareInfo -> cabinClasses` as the economy cabin's `availabilityCount`, so the parser contract must be corrected and protected with regression tests.

## What Changes

- Parse normal economy availability from the `EKONOMI`/`EKONOMI` economy cabin in `availableFareInfo[].cabinClasses[]`, using `availabilityCount` rather than capacity fields.
- Ensure business and wheelchair/accessible cabin availability never contributes to normal economy availability.
- Ensure `bookingClassCapacities.capacity` and other total-capacity fields are never used for availability counts.
- Deduplicate repeated economy cabin entries across fare families using a deterministic single-inventory approach so duplicate fare-family exposure does not inflate availability.
- Add regression coverage using `tests/fixtures/tcdd_real_response.json` and focused parser cases for zero economy, business-only, accessible-only, positive economy, and duplicate fare-family data.
- Preserve the existing `TrainAvailability` interface and keep raw TCDD response parsing isolated within `app/tcdd`.
- Exclude the runtime monitoring activation bug from this change; it will be handled separately.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tcdd-provider`: Normal economy availability parsing must use cabin `availabilityCount` semantics from verified real TCDD responses instead of capacity-derived values.

## Impact

- Affected code is expected to be limited to the TCDD provider parser and its tests, primarily under `app/tcdd/` and `tests/`.
- Downstream monitoring should continue consuming normalized `TrainAvailability` records without parsing raw TCDD responses.
- No new dependency, database schema change, Telegram handler change, or public provider interface change is expected.
