## ADDED Requirements

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
