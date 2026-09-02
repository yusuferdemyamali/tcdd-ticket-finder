## MODIFIED Requirements

### Requirement: Normal economy availability is isolated from other categories
The system SHALL compute normal economy availability only from the verified normal economy cabin availability count in TCDD fare information and SHALL NOT count train capacity, booking-class capacity, business availability, accessible availability, or special-seat availability as normal economy availability.

Normal economy availability SHALL be sourced from the economy cabin in `availableFareInfo[].cabinClasses[]` using its `availabilityCount`. When the same normal economy seat inventory appears through multiple fare-family entries, the normalized availability SHALL preserve the single real availability count deterministically and SHALL NOT sum duplicate fare-family entries.

#### Scenario: Economy availability is preserved
- **WHEN** a service has a normal economy cabin entry in fare information with `availabilityCount` greater than 0
- **THEN** the normalized train availability record preserves that count as normal economy availability
- **AND** the count is not replaced by train capacity or booking-class capacity

#### Scenario: Zero economy cabin availability remains unavailable
- **WHEN** a service has a normal economy cabin entry in fare information with `availabilityCount` equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Business-only availability is not economy availability
- **WHEN** a service has business cabin availability greater than 0 and normal economy cabin availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Accessible-only availability is not economy availability
- **WHEN** a service has wheelchair or accessible cabin availability greater than 0 and normal economy cabin availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Special-seat-only availability is not economy availability
- **WHEN** a service has special-seat availability greater than 0 and normal economy cabin availability equal to 0
- **THEN** the normalized train availability record has normal economy availability equal to 0

#### Scenario: Capacity fields are not used as availability
- **WHEN** a valid TCDD response contains train capacity, booking-class capacity, or similar total-capacity fields with values greater than the normal economy cabin `availabilityCount`
- **THEN** the normalized train availability record uses the normal economy cabin `availabilityCount`
- **AND** it does not expose capacity values as normal economy availability

#### Scenario: Duplicate fare-family economy entries do not inflate availability
- **WHEN** the same normal economy cabin inventory is represented under more than one fare-family entry in a valid TCDD response
- **THEN** the normalized train availability record preserves one deterministic normal economy availability count for that inventory
- **AND** it does not sum duplicate fare-family entries into an inflated count
