## ADDED Requirements

### Requirement: Monitoring lifecycle results are persisted safely
The system SHALL persist monitoring-driven lifecycle outcomes through the ticket-search domain boundary so notification and polling behavior can rely on durable state.

Monitoring-driven completion SHALL require the search to already be `FOUND`, and restart shall only reactivate the callback's own persisted `COMPLETED` search before its travel window has passed in `Europe/Istanbul`.

#### Scenario: Found search can be completed after notification
- **WHEN** a monitoring flow has persisted a search as `FOUND`
- **AND** the found-ticket notification has been sent successfully
- **THEN** the domain can persist that same search as `COMPLETED`

#### Scenario: Active search cannot skip found before completion
- **WHEN** a monitoring flow attempts to complete a search that is still `ACTIVE`
- **THEN** the domain rejects the completion
- **AND** the persisted status remains unchanged

#### Scenario: Restart targets the callback search only
- **WHEN** a restart is requested for a persisted search id
- **AND** that search is `COMPLETED`
- **AND** its travel window has not passed in `Europe/Istanbul`
- **THEN** that same search becomes `ACTIVE`
- **AND** no unrelated search is activated

#### Scenario: Expired active search is persisted
- **WHEN** an `ACTIVE` search travel window has passed in `Europe/Istanbul`
- **THEN** the domain can persist that search as `EXPIRED`
- **AND** later active-search lookup does not return the expired search
