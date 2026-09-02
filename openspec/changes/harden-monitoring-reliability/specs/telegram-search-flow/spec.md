## ADDED Requirements

### Requirement: Monitoring outage notifications are user-visible and de-duplicated
The Telegram notification surface SHALL support monitoring outage messages that inform the authorized user when TCDD cannot currently be queried and background retries will continue.

The same ongoing outage SHALL NOT produce repeated generic outage messages on every poll, and persisted outage notification state SHALL be respected after restart.

#### Scenario: First outage message is sent
- **WHEN** monitoring reports the first TCDD outage for a search whose outage notification state is clear
- **THEN** Telegram sends a short message telling the user that TCDD cannot currently be queried and retries will continue in the background

#### Scenario: Ongoing outage message is not spammed
- **WHEN** monitoring reports another TCDD outage for a search whose outage notification state is already set
- **THEN** Telegram does not send another generic outage message for that ongoing outage

#### Scenario: Authentication outage can be more specific
- **WHEN** monitoring reports a TCDD authentication failure
- **THEN** Telegram may send a short message indicating the TCDD token information may need to be refreshed
- **AND** the message does not include secret token values

### Requirement: Monitoring recovery notification is user-visible once
The Telegram notification surface SHALL support one recovery message after TCDD becomes queryable again following a reported outage.

#### Scenario: Recovery message is sent once
- **WHEN** monitoring reports a successful TCDD check after an outage was previously reported
- **THEN** Telegram sends one short message telling the user that TCDD connection is restored and ticket search continues

#### Scenario: Recovery is not sent without prior outage notification
- **WHEN** monitoring reports a successful TCDD check for a search with no reported outage state
- **THEN** Telegram does not send a recovery message

### Requirement: Found-ticket notification retry is supported
The Telegram notification surface SHALL allow monitoring recovery to retry a found-ticket notification for a persisted `FOUND` search.

The retried notification SHALL preserve the existing found-ticket behavior: one message containing all eligible trains known for that found event and actions for `TCDD'den Bilet Al` and `Bileti Alamadım - Tekrar Ara`.

#### Scenario: Found search retry sends found-ticket message
- **WHEN** startup recovery retries notification for a persisted `FOUND` search
- **THEN** Telegram sends the found-ticket notification for that search
- **AND** the message includes the existing ticket-buy and restart-search actions

#### Scenario: Failed retried notification does not imply completion
- **WHEN** Telegram fails while sending a retried found-ticket notification
- **THEN** monitoring can observe the failure
- **AND** the search is not treated as notification-delivered
