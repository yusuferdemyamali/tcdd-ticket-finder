## ADDED Requirements

### Requirement: Typed TCDD errors remain available to monitoring
The TCDD provider SHALL expose typed failures for availability-query problems so monitoring can distinguish outages from valid empty results.

The provider SHALL preserve distinct failure categories for network/timeout, authentication, rate limit, server error, invalid response, unexpected response, TLS, and WAF conditions, and SHALL NOT convert those failures into an empty normalized train list.

#### Scenario: Monitoring can distinguish network outage from no trains
- **WHEN** the availability request fails because of network or timeout behavior
- **THEN** the provider reports a typed TCDD failure to the caller
- **AND** it does not return an empty normalized train list

#### Scenario: Monitoring can distinguish authentication failure from no trains
- **WHEN** the availability request fails because the TCDD token is missing, rejected, or unauthorized
- **THEN** the provider reports an authentication TCDD failure to the caller
- **AND** it does not return an empty normalized train list

#### Scenario: Monitoring can distinguish response failure from no trains
- **WHEN** TCDD returns invalid JSON or an unexpected response shape
- **THEN** the provider reports an invalid-response or unexpected-response TCDD failure to the caller
- **AND** it does not return an empty normalized train list

#### Scenario: Monitoring can distinguish protection-layer failure from no trains
- **WHEN** the request fails because of TLS negotiation or WAF blocking behavior
- **THEN** the provider reports a TLS or WAF TCDD failure to the caller
- **AND** it does not return an empty normalized train list
