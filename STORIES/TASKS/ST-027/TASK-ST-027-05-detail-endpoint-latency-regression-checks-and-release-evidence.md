# Detail Endpoint Latency Regression Checks and Release Evidence

**Task ID:** TASK-ST-027-05  
**Story:** ST-027  
**Bucket:** ops  
**Requirement Links:** ST-027 Acceptance Criteria #5, AGENDA_PLAN §5 Phase 3 — API/frontend additive planned/outcomes + mismatches, AGENDA_PLAN §7 Observability, operations, and runbook updates

## Objective

Establish repeatable latency regression checks and release evidence that additive meeting detail fields stay within p95 performance budget.

## Scope

- Define benchmark scenarios for flag-off baseline and flag-on additive payload paths.
- Add p95 measurement/reporting procedure for meeting detail endpoint.
- Document acceptance thresholds and release evidence expectations.
- Out of scope: broad pipeline latency optimization or infrastructure resizing.

## Inputs / Dependencies

- TASK-ST-027-03 additive serializer implementation.
- TASK-ST-027-04 flag-state integration test matrix.
- Existing API observability metrics/logging infrastructure.

## Implementation Notes

- Keep workload fixtures representative of high-contention city/meeting payload sizes.
- Compare additive-on performance against baseline-off under equivalent load.
- Capture reproducible measurement parameters (sample size, duration, environment).

## Acceptance Criteria

1. p95 latency checks exist for both flag-off and flag-on detail endpoint paths.
2. Regression process can detect additive-field performance degradation.
3. Release evidence includes measured p95 results against agreed budget.
4. Runbook guidance exists for mitigation/rollback when latency budget is exceeded.

## Validation

- Execute repeatable detail endpoint benchmark runs for both flag states.
- Verify reported p95 metrics are stable across repeated runs.
- Confirm runbook includes response steps for additive-field latency regressions.

## Deliverables

- Detail endpoint latency benchmark procedure and thresholds.
- Release evidence artifact template for p95 checks.
- Runbook update notes for latency regression handling.
