# Shadow Gate Evaluation and Diagnostics Artifacts

**Task ID:** TASK-ST-021-02  
**Story:** ST-021  
**Bucket:** backend  
**Requirement Links:** ST-021 Acceptance Criteria #2, GAP_PLAN §Gate Matrix (A/B/C), NFR-4

## Objective

Implement report-only shadow gate evaluation that emits pass/fail diagnostics for Gate A/B/C without blocking publish outcomes.

## Scope

- Define shadow-mode evaluation flow for Gate A/B/C prerequisites and checks.
- Produce diagnostics artifact schema that captures gate-level pass/fail and reason codes.
- Ensure publish path remains non-blocking while shadow mode is enabled.
- Out of scope: enforced blocking/downgrade decisions and promotion eligibility state changes.

## Inputs / Dependencies

- TASK-ST-021-01 feature flag contract and cohort resolution.
- ST-017 fixture scorecard baseline used by gate checks.
- ST-018 evidence references contract for diagnostic attribution.

## Implementation Notes

- Keep diagnostics stable and machine-readable for downstream promotion checks.
- Include identifiers needed to trace gate outcomes per run and per city/source.
- Treat missing diagnostics as failure for rollout readiness.

## Acceptance Criteria

1. Shadow mode evaluates Gate A/B/C checks and emits diagnostics for each run.
2. Diagnostics include gate identifier, result, and explicit reason codes.
3. Shadow mode does not block or downgrade publish decisions.
4. Shadow diagnostics are queryable for promotion analysis windows.

## Validation

- Run fixture-based scenarios with shadow mode on and confirm diagnostics emission.
- Verify publish outputs are unchanged between shadow mode off vs on.
- Confirm diagnostics completeness for pass and fail scenarios across Gate A/B/C.

## Deliverables

- Shadow gate evaluation flow documentation.
- Diagnostics artifact contract and sample outputs.
- Validation evidence comparing publish behavior with and without shadow mode.
