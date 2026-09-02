## 1. Parser Semantics

- [ ] 1.1 Add cabin-fare economy extraction in `app/tcdd/parser.py` from `availableFareInfo[].cabinClasses[].availabilityCount` and verify a focused parser test returns the economy cabin count instead of `bookingClassCapacities[].capacity`
- [ ] 1.2 Identify normal economy by `cabinClass.id == 2` with normalized economy-name fallback and verify business (`id == 1`) and wheelchair/accessible (`id == 12`) cabin entries are ignored when economy is unavailable
- [ ] 1.3 Replace capacity-derived economy logic so `bookingClassCapacities.capacity` and similar total-capacity fields are not used for availability and verify capacity-only fixture data yields `economy_available == 0` unless fare cabin availability exists
- [ ] 1.4 Handle repeated economy cabin entries across fare families with deterministic non-summing selection, preferably `max(availabilityCount)`, and verify duplicate economy fare-family entries do not inflate the count

## 2. Regression Coverage

- [ ] 2.1 Update `tests/test_tcdd_provider.py::test_parse_real_fixture` to assert known `tests/fixtures/tcdd_real_response.json` trains return fixture `availabilityCount` values rather than capacity values and verify `pytest tests/test_tcdd_provider.py::test_parse_real_fixture` passes
- [ ] 2.2 Add focused parser tests for economy `availabilityCount == 0`, economy `availabilityCount > 0`, business-only availability, accessible-only availability, and duplicate fare-family economy entries, then verify those tests pass
- [ ] 2.3 Add or update a provider-boundary regression asserting parsed `TrainAvailability` records do not expose raw TCDD fields and verify monitoring tests still consume only normalized records

## 3. Verification

- [ ] 3.1 Run the TCDD provider test subset and verify `pytest tests/test_tcdd_provider.py` passes
- [ ] 3.2 Run the existing test suite and verify it passes without changing the `TrainAvailability` interface
- [ ] 3.3 When `TCDD_TOKEN` and network access are available, run a real `TcddClient` availability query and verify returned `economy_available` values match cabin availability counts rather than capacity values
- [ ] 3.4 Confirm no runtime monitoring activation bug changes were made and verify the diff is limited to parser semantics and tests for this change
