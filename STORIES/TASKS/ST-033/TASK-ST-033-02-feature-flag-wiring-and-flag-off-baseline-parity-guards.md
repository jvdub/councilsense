# Feature Flag Wiring and Flag-Off Baseline Parity Guards

**Task ID:** TASK-ST-033-02  
**Story:** ST-033  
**Bucket:** backend  
**Requirement Links:** ST-033 Acceptance Criteria #1 and #5, FR-6, REQUIREMENTS §13.5 Clarity Outcome

## Objective

Add flag wiring and parity guards so resident-relevance API fields can be enabled safely without changing baseline meeting detail behavior by default.

## Scope

- Introduce backend gating for resident-relevance field exposure.
- Preserve baseline meeting detail responses when the new fields are disabled.
- Define safe defaults for local, test, and rollout configurations.
- Out of scope: frontend flag consumption and rendering behavior.

## Inputs / Dependencies

- TASK-ST-033-01 resident-relevance API contract.
- Existing additive-field gating patterns from ST-027.

## Implementation Notes

- Follow existing flag-off parity behavior used for planned/outcomes additive fields.
- Keep defaults conservative so legacy consumers see no contract expansion unless enabled.
- Ensure flag handling is deterministic and testable.

## Acceptance Criteria

1. Backend flag wiring controls exposure of resident-relevance fields.
2. Flag-off meeting detail responses are baseline-compatible.
3. Missing or invalid structured data does not override flag-off parity behavior.
4. Rollout defaults are documented for safe additive exposure.

## Validation

- Compare flag-off responses against current baseline fixtures.
- Verify enabled vs disabled states in integration tests.
- Confirm invalid structured values do not leak partial fields unexpectedly.

## Deliverables

- Backend feature-flag contract for resident-relevance field exposure.
- Flag-off parity rules and test scenarios.
- Rollout default notes for safe deployment.
