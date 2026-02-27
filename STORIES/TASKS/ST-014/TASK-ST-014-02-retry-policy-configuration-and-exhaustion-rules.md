# Retry Policy Configuration and Exhaustion Rules

**Task ID:** TASK-ST-014-02  
**Story:** ST-014  
**Bucket:** backend  
**Requirement Links:** FR-5, NFR-4

## Objective
Make retry limits/backoff behavior configuration-driven and enforceable with clear exhaustion rules.

## Scope
- Externalize retry count, delay curve, and jitter settings.
- Implement policy validation and safe defaults.
- Emit policy version in attempt logs for auditability.
- Out of scope: operator replay and dashboards.

## Inputs / Dependencies
- TASK-ST-014-01 DLQ transition path.
- Existing queue/worker runtime configuration mechanism.

## Implementation Notes
- Validate config at startup to prevent unsafe runtime behavior.
- Track attempts against effective policy version.
- Keep current MVP idempotency semantics unchanged.

## Acceptance Criteria
1. Retry/backoff policy is configurable without code changes.
2. Invalid policy config fails fast with clear error messages.
3. Exhaustion behavior routes to DLQ consistently under configured limits.
4. Policy version is visible in processing telemetry/audit records.

## Validation
- Unit tests for policy parsing and validation.
- Integration tests for configured retry counts and exhaustion outcomes.
- Negative test with invalid policy to verify fail-fast behavior.

## Deliverables
- Retry policy config schema and defaults.
- Updated worker logic applying policy values.
- Tests and operations documentation for policy tuning.
