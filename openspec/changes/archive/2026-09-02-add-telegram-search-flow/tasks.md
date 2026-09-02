## 1. Configuration and Wiring

- [x] 1.1 Add `python-telegram-bot` as the runtime Telegram dependency and verify dependency resolution/install succeeds for the project environment.
- [x] 1.2 Add Telegram configuration loading for `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USER_ID`, rejecting missing/invalid values without logging token contents; verify with unit tests for valid config, missing token, missing user id, and invalid user id.
- [x] 1.3 Add a minimal Telegram bot module/entry wiring for `/start`, `/ara`, `/durum`, and `/iptal` without starting scheduler or polling features; verify handlers can be constructed in a test without contacting Telegram or TCDD network services.

## 2. Authorization and Shared Formatting

- [x] 2.1 Implement a shared authorization guard used by every command and callback handler; verify unauthorized `/start`, `/ara`, `/durum`, `/iptal`, and callback tests do not read or mutate search state.
- [x] 2.2 Implement active-search and confirmation message formatting with route, date, time range, status where applicable, one passenger, and economy-only text; verify formatting tests cover `/durum` and confirmation output.
- [x] 2.3 Ensure Telegram handlers use ticket-search service methods and station-provider results instead of direct SQLite or raw TCDD response shapes; verify by tests with fake services/providers and by reviewing handler code for no direct SQLite calls.

## 3. Search Wizard

- [x] 3.1 Implement `/ara` entry behavior when no active search exists, starting the ORIGIN -> DESTINATION -> DATE -> FROM_TIME -> TO_TIME -> CONFIRM conversation; verify a test reaches the origin prompt.
- [x] 3.2 Implement station text resolution through the existing station provider, including single-match auto-advance, no-match retry, and ambiguous inline-keyboard selection; verify tests cover all three station outcomes.
- [x] 3.3 Implement strict `DD.MM.YYYY` date validation, past-date rejection in `Europe/Istanbul`, and conversion to the domain `YYYY-MM-DD` value only after valid input; verify invalid format, past date, and valid date tests.
- [x] 3.4 Implement strict zero-padded `HH:MM` time validation and reject `from > to` midnight-crossing windows while accepting `from == to`; verify invalid time, crossing range, equal boundary, and valid range tests.
- [x] 3.5 Implement confirmation actions `Aramayı Başlat` and `Vazgeç`, ensuring no search is persisted before confirmation; verify tests for pre-confirmation state, confirmed creation, and cancelled confirmation.

## 4. Active Search Commands and Replacement

- [x] 4.1 Implement `/durum` to show the active search route, date, time range, and status, or an explicit no-active-search message; verify tests for both states.
- [x] 4.2 Implement `/iptal` to cancel only the current active search and send success/no-active-search messages; verify tests for active cancellation and no-active-search behavior.
- [x] 4.3 Implement `/ara` behavior when an active search exists, showing the existing search plus `Aramayı Değiştir` and `Vazgeç` actions instead of starting the wizard immediately; verify the existing active search remains unchanged at this step.
- [x] 4.4 Implement replacement wizard mode so the old active search remains active until the new confirmation is accepted, then use existing atomic replacement behavior; verify tests for replacement-in-progress preservation and confirmed old-`CANCELLED` plus new-`ACTIVE` state.
- [x] 4.5 Implement wizard/replacement cancellation so cancelling during replacement leaves the old active search unchanged and creates no new search; verify with a replacement cancellation test.

## 5. Callback Safety and Regression Verification

- [x] 5.1 Add current wizard/session validation for station, confirmation, cancellation, and replacement callbacks; verify stale callback tests do not create, replace, or cancel searches and return an invalid-action message.
- [x] 5.2 Verify callback payloads use compact stable identifiers for station candidates/search-related actions where possible and do not encode raw station objects; verify with callback payload unit tests or assertions.
- [x] 5.3 Run the full Telegram flow test suite and verify all new critical paths pass.
- [x] 5.4 Run the existing TCDD provider and ticket-search tests and verify they still pass unchanged.
- [x] 5.5 Run OpenSpec validation for `add-telegram-search-flow` and verify the change artifacts are valid.
