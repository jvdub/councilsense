# Report-Only Gate Diagnostics and Artifacts

**Task ID:** TASK-ST-030-02  
**Story:** ST-030  
**Bucket:** backend  
**Requirement Links:** ST-030 Acceptance Criteria #1, AGENDA_PLAN §5 Phase 4 — Hardening, AGENDA_PLAN §7 Observability, operations, and runbook updates

## Objective
Implement report-only evaluation for document-aware gates and emit diagnostics artifacts without blocking publish outputs.

## Scope
- Run authority-alignment, coverage-balance, and citation-precision checks in report-only mode.
- Emit machine-readable diagnostics artifacts with gate-level results, score details, and reason codes.
- Add trace fields needed for run/city/meeting/source correlation and promotion analysis.
- Out of scope: enforced publish blocking/downgrade decisions and rollout promotion control.

## Inputs / Dependencies
- TASK-ST-030-01 gate dimensions and threshold contract.
- Existing report-only/shadow gate execution pathways from ST-021.
- Existing observability field conventions from AGENDA_PLAN §7.

## Implementation Notes
- Publish behavior must remain non-blocking in report-only mode.
- Diagnostics completeness is required; missing artifact fields are rollout-readiness failures.
- Artifact schema should support consecutive-green promotion calculations.

## Acceptance Criteria
1. Report-only mode emits diagnostics for authority alignment, coverage balance, and citation precision per run.
2. Diagnostics include gate status, score, threshold, and explicit reason codes.
3. Report-only evaluation does not block or downgrade publish decisions.
4. Diagnostics are queryable for promotion readiness analysis windows.

## Validation
- Run fixture scenarios with report-only mode enabled and confirm artifact emission.
- Compare publish outputs with report-only mode on/off to verify non-blocking behavior.
- Confirm artifact completeness for pass/fail/missing-input scenarios.

## Deliverables
- Report-only gate evaluation flow documentation.
- Diagnostics artifact schema and sample outputs.
- Validation evidence showing unchanged publish behavior in report-only mode.
