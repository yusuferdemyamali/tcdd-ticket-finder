## Purpose

Provide the MVP Telegram user interface for one authorized user to create, view, replace, and cancel a persistent TCDD ticket search while relying on the existing station-resolution and ticket-search domain boundaries.

## Requirements

### Requirement: Telegram access is restricted to the configured user
The system SHALL allow only the Telegram user identified by `TELEGRAM_ALLOWED_USER_ID` to read or change ticket-search state through the bot.

The system SHALL require `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USER_ID` configuration to start Telegram bot handling, and SHALL NOT log secret token values.

#### Scenario: Authorized user can open the bot
- **WHEN** the configured Telegram user sends `/start`
- **THEN** the bot responds with the main actions for ticket search creation and current-search viewing

#### Scenario: Unauthorized user cannot read search state
- **WHEN** a Telegram user whose id does not match `TELEGRAM_ALLOWED_USER_ID` sends `/durum`
- **THEN** the bot does not disclose route, date, time window, status, or any other current-search details

#### Scenario: Unauthorized user cannot mutate search state
- **WHEN** a Telegram user whose id does not match `TELEGRAM_ALLOWED_USER_ID` sends `/ara`, `/iptal`, or a search-related callback
- **THEN** the bot does not create, replace, cancel, or otherwise mutate ticket-search state

### Requirement: Search creation wizard collects MVP search inputs
The system SHALL provide a `/ara` conversation that collects origin station, destination station, travel date, departure start time, departure end time, and explicit confirmation before creating a search.

The wizard SHALL collect exactly one passenger, one-way travel, one travel date, and a non-midnight-crossing inclusive departure time window for normal economy seats.

#### Scenario: Wizard completes with valid inputs
- **WHEN** the authorized user provides a valid origin, destination, `DD.MM.YYYY` travel date, `HH:MM` start time, `HH:MM` end time, and confirms the summary
- **THEN** the system creates one `ACTIVE` ticket search using canonical origin and destination stations
- **AND** the bot tells the user the search has started

#### Scenario: Search is not created before confirmation
- **WHEN** the authorized user has entered some or all wizard fields but has not confirmed the summary
- **THEN** no new ticket search is created

#### Scenario: User cancels wizard before confirmation
- **WHEN** the authorized user chooses the cancel action during the wizard before confirming
- **THEN** no new ticket search is created
- **AND** the bot reports that the operation was cancelled

### Requirement: Station text resolves to canonical TCDD stations
The system SHALL resolve station text entered by the user through the existing TCDD station provider and SHALL use canonical station identifiers and display names for created searches.

Raw TCDD station response objects SHALL NOT be exposed in Telegram messages or stored as Telegram conversation state.

#### Scenario: Single station match continues automatically
- **WHEN** the authorized user enters a station name that resolves to exactly one canonical station
- **THEN** the bot records that canonical station for the wizard step
- **AND** the wizard advances to the next input

#### Scenario: Ambiguous station match asks for selection
- **WHEN** the authorized user enters station text that resolves to more than one candidate
- **THEN** the bot shows an inline keyboard with the candidate station choices
- **AND** the wizard advances only after the user selects one candidate

#### Scenario: Unknown station asks for input again
- **WHEN** the authorized user enters station text that resolves to no canonical station
- **THEN** the bot explains that the station was not found
- **AND** asks for the same station input again

### Requirement: Date and time input validation is strict
The system SHALL accept travel dates only in `DD.MM.YYYY` format and departure times only in zero-padded `HH:MM` format.

The system SHALL reject past travel dates and SHALL reject departure windows where the start time is later than the end time.

#### Scenario: Invalid date format is rejected
- **WHEN** the authorized user enters a travel date that is not in `DD.MM.YYYY` format
- **THEN** the bot rejects the input
- **AND** asks for the travel date again without creating a search

#### Scenario: Past date is rejected
- **WHEN** the authorized user enters a valid-format travel date earlier than the current date in `Europe/Istanbul`
- **THEN** the bot rejects the input
- **AND** asks for the travel date again without creating a search

#### Scenario: Invalid time format is rejected
- **WHEN** the authorized user enters a departure time that is not in zero-padded `HH:MM` format
- **THEN** the bot rejects the input
- **AND** asks for the same time input again without creating a search

#### Scenario: Midnight-crossing range is rejected
- **WHEN** the authorized user enters a departure start time later than the departure end time
- **THEN** the bot rejects the departure window because midnight-crossing ranges are not supported
- **AND** asks for the relevant time input again without creating a search

#### Scenario: Equal start and end time is accepted
- **WHEN** the authorized user enters the same valid `HH:MM` value for departure start and end time
- **THEN** the wizard accepts the inclusive time window

### Requirement: Confirmation clearly summarizes the pending search
The system SHALL show a confirmation message before creating or replacing a search.

The confirmation message SHALL include departure station, arrival station, travel date, departure time range, one passenger, and normal-economy-only search scope.

#### Scenario: Confirmation provides start and cancel actions
- **WHEN** the wizard has collected all valid inputs
- **THEN** the bot shows a confirmation message with `Aramayı Başlat` and `Vazgeç` actions

#### Scenario: Confirmed search uses summarized inputs
- **WHEN** the authorized user selects `Aramayı Başlat`
- **THEN** the created search uses the same route, date, and time window shown in the confirmation message

#### Scenario: Cancelled confirmation does not create search
- **WHEN** the authorized user selects `Vazgeç` on the confirmation message
- **THEN** no new ticket search is created

### Requirement: Active search replacement preserves the old search until confirmation
The system SHALL NOT immediately cancel an existing `ACTIVE` search when the authorized user starts `/ara` while an active search exists.

If the user confirms a replacement search, the system SHALL atomically cancel the old `ACTIVE` search and create the new `ACTIVE` search through the existing ticket-search domain behavior.

#### Scenario: Active search blocks immediate wizard start
- **WHEN** the authorized user sends `/ara` while an `ACTIVE` search exists
- **THEN** the bot shows the existing active search summary
- **AND** offers `Aramayı Değiştir` and `Vazgeç` actions instead of immediately starting a new wizard

#### Scenario: Replacement wizard leaves old search active
- **WHEN** the authorized user selects `Aramayı Değiştir`
- **AND** the replacement wizard is in progress but not confirmed
- **THEN** the previous search remains `ACTIVE`

#### Scenario: Confirmed replacement is atomic
- **WHEN** the authorized user completes and confirms the replacement wizard
- **THEN** the previous active search becomes `CANCELLED`
- **AND** the replacement search becomes `ACTIVE`
- **AND** the system does not commit a final state with two `ACTIVE` searches

#### Scenario: Replacement cancellation preserves old active search
- **WHEN** the authorized user cancels the replacement wizard before confirmation
- **THEN** the previous search remains `ACTIVE`
- **AND** no replacement search is created

### Requirement: Current search status is visible to the authorized user
The system SHALL provide `/durum` behavior that reports the currently active search to the authorized user.

#### Scenario: Active search status is shown
- **WHEN** the authorized user sends `/durum` and an `ACTIVE` search exists
- **THEN** the bot shows the route, travel date, departure time range, and `ACTIVE` status

#### Scenario: No active search is explicit
- **WHEN** the authorized user sends `/durum` and no `ACTIVE` search exists
- **THEN** the bot clearly reports that there is no active search

### Requirement: Active search can be cancelled from Telegram
The system SHALL provide `/iptal` behavior that cancels only the current `ACTIVE` search for the authorized user.

#### Scenario: Active search is cancelled
- **WHEN** the authorized user sends `/iptal` and an `ACTIVE` search exists
- **THEN** that search becomes `CANCELLED`
- **AND** the bot confirms successful cancellation

#### Scenario: No active search to cancel
- **WHEN** the authorized user sends `/iptal` and no `ACTIVE` search exists
- **THEN** the bot reports that there is no active search to cancel

### Requirement: Telegram callbacks are state-safe
The system SHALL reject stale or invalid Telegram callback actions instead of applying them to the wrong wizard or search state.

Callback payloads SHOULD use stable identifiers when they refer to persisted records or station candidates.

#### Scenario: Stale confirmation callback does not mutate search state
- **WHEN** the authorized user submits a callback from an older or no-longer-current wizard confirmation
- **THEN** the system does not create, replace, or cancel a search from that stale callback
- **AND** the bot reports that the action is no longer valid

#### Scenario: Stale replacement callback does not cancel active search
- **WHEN** the authorized user submits an old replacement-related callback after the replacement wizard has been cancelled or superseded
- **THEN** the current `ACTIVE` search remains unchanged

### Requirement: Telegram layer preserves domain boundaries
The Telegram command and callback layer SHALL use the existing ticket-search domain boundary for search create, replace, cancel, and read operations.

The Telegram command and callback layer SHALL NOT execute direct SQLite queries for ticket-search behavior and SHALL NOT depend on raw TCDD provider response shapes.

#### Scenario: Search creation goes through domain behavior
- **WHEN** a Telegram confirmation creates a new search
- **THEN** search validation and single-active-search enforcement are applied by the existing ticket-search domain behavior

#### Scenario: Search replacement goes through domain behavior
- **WHEN** a Telegram confirmation replaces an active search
- **THEN** the existing atomic ticket-search replacement behavior performs the old-search cancellation and new-search creation

#### Scenario: Handler tests do not require external polling behavior
- **WHEN** Telegram flow behavior is tested
- **THEN** tests can exercise command and callback behavior without starting a scheduler, background TCDD polling, seat-found notification flow, retry/backoff loop, or Docker runtime

### Requirement: Found-ticket notification contains all eligible trains
The system SHALL send a found-ticket Telegram notification that includes the route, travel date, train name or number, departure time, and normal economy availability count for every eligible train found in the search check.

The found-ticket notification SHALL include actions for `TCDD'den Bilet Al` and `Bileti Alamadım - Tekrar Ara`.

#### Scenario: Multiple trains are shown in one message
- **WHEN** monitoring finds more than one eligible train for the same search
- **THEN** Telegram sends one found-ticket message containing all eligible trains
- **AND** each listed train includes train name or number, departure time, and normal economy availability count

#### Scenario: Found-ticket actions are available
- **WHEN** a found-ticket notification is sent
- **THEN** it includes a `TCDD'den Bilet Al` action
- **AND** it includes a `Bileti Alamadım - Tekrar Ara` action whose callback payload contains the related search id

### Requirement: Restart callback is stale-safe
The system SHALL process `Bileti Alamadım - Tekrar Ara` by reading the current persisted search before restarting it.

The system SHALL restart only the search referenced by the callback, only when that persisted search is currently `COMPLETED`, and only when the search travel window has not passed in `Europe/Istanbul`.

#### Scenario: Completed search restarts from matching callback
- **WHEN** the authorized user submits `Bileti Alamadım - Tekrar Ara` for a search id
- **AND** the current persisted search with that id is `COMPLETED`
- **AND** the search travel window has not passed in `Europe/Istanbul`
- **THEN** the same search criteria become `ACTIVE` again
- **AND** automatic monitoring can check that search again

#### Scenario: Expired travel window cannot restart
- **WHEN** the authorized user submits `Bileti Alamadım - Tekrar Ara` for a `COMPLETED` search whose travel window has passed in `Europe/Istanbul`
- **THEN** the search is not restarted
- **AND** the bot reports that the action is no longer valid

#### Scenario: Stale callback does not activate another search
- **WHEN** the authorized user submits a restart callback whose search id does not refer to the current persisted `COMPLETED` search being acted on
- **THEN** the system does not activate any different search
- **AND** the bot reports that the action is no longer valid

### Requirement: Expiration notification is sent for ended active search
The system SHALL notify the authorized user when an `ACTIVE` search is expired because its travel window has passed.

#### Scenario: Expired search is reported once
- **WHEN** monitoring expires an `ACTIVE` search
- **THEN** Telegram sends one message telling the user the search has ended
- **AND** the expired search is not offered as an active search to monitor
