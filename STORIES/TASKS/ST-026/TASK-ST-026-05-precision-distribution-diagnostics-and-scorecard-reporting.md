# Precision Distribution Diagnostics and Scorecard Reporting

**Task ID:** TASK-ST-026-05  
**Story:** ST-026  
**Bucket:** ops  
**Requirement Links:** ST-026 Acceptance Criteria #3, AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision, AGENDA_PLAN §7 Observability, operations, and runbook updates

## Objective

Add diagnostics that measure evidence precision distribution so release readiness can verify majority finer-than-file references where parser metadata exists.

## Scope

- Define precision-distribution metrics for offset/span/section/file reference classes.
- Add scorecard/ops reporting output for precision ratio by run/city/source.
- Add release-readiness check guidance for majority finer-than-file expectation.
- Out of scope: automatic gate enforcement and alert policy changes.

## Inputs / Dependencies

- TASK-ST-026-02 precision ladder and deterministic ordering outputs.
- TASK-ST-026-03 v2 evidence projection fields.
- Existing scorecard diagnostics reporting framework.

## Implementation Notes

- Measure only grounded references included in final projection output.
- Keep metrics source-aware to support parser drift and city-level triage.
- Include explicit handling for runs where precision metadata is unavailable.

## Acceptance Criteria

1. Diagnostics report precision distribution across offset/span/section/file levels.
2. Reporting supports verifying majority finer-than-file references where precision is extractable.
3. Outputs are stable and comparable across reruns for the same fixtures.
4. Reporting artifacts are suitable for ops scorecard and release readiness review.

## Validation

- Run scorecard diagnostics on baseline fixtures with precision metadata present/absent mixes.
- Verify precision ratio calculations for deterministic repeatability.
- Confirm reports can be consumed in existing ops/release review workflows.

## Deliverables

- Precision distribution metric definitions and reporting schema.
- Scorecard/ops artifacts showing per-run precision mix.
- Release-readiness checklist for precision majority checks.
