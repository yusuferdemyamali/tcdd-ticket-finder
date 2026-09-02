## ADDED Requirements

### Requirement: Container restart uses persisted monitoring recovery
The containerized runtime SHALL preserve the existing monitoring recovery semantics by starting monitoring against persisted ticket-search state after application startup.

An `ACTIVE` search persisted before container restart SHALL be eligible for automatic polling after restart, and a `FOUND` search persisted before container restart SHALL remain available to the existing notification recovery behavior.

#### Scenario: Active search resumes monitoring after container restart
- **WHEN** an `ACTIVE` search exists in the SQLite database on the persistent volume
- **AND** the application container restarts
- **THEN** monitoring starts after application startup
- **AND** the existing monitoring behavior can continue checking that `ACTIVE` search without requiring the user to recreate it

#### Scenario: Found search remains recoverable after container restart
- **WHEN** a `FOUND` search exists in the SQLite database on the persistent volume
- **AND** the application container restarts
- **THEN** the existing notification recovery behavior can process that `FOUND` search using persisted state
- **AND** the search is not lost because of container restart or recreate

#### Scenario: Containerization does not change monitoring decisions
- **WHEN** monitoring runs inside the containerized runtime
- **THEN** it still applies the existing TCDD polling, normal-economy filtering, outage handling, notification, and lifecycle transition behavior
