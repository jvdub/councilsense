# Pilot-City Minutes Plus Supplemental Smoke Fixture

**Task ID:** TASK-ST-023-05  
**Story:** ST-023  
**Bucket:** ops  
**Requirement Links:** ST-023 Acceptance Criteria #4-#5, AGENDA_PLAN §5 and §6

## Objective

Establish a pilot-city smoke fixture and execution checklist proving ingest of minutes plus at least one supplemental artifact without duplicate outputs.

## Scope

- Define pilot-city fixture inputs containing minutes and one supplemental source artifact.
- Define repeatable smoke execution steps and expected outputs.
- Capture evidence checklist for bundle creation, dedupe outcomes, and publish continuity.
- Out of scope: multi-city rollout and production alert policy tuning.

## Inputs / Dependencies

- TASK-ST-023-04 deterministic rerun and duplicate-prevention tests.
- Existing local runtime smoke command patterns.
- ST-022 rollout/rollback guidance for safe flag posture.

## Implementation Notes

- Keep fixture small and deterministic for routine verification.
- Include first-run and rerun expected-result tables.
- Capture artifacts needed for release-readiness reviews.

## Acceptance Criteria

1. Pilot-city smoke demonstrates minutes + supplemental artifact ingestion path. (ST-023 AC #4)
2. Rerun of same fixture produces no duplicate documents/artifacts/publications. (ST-023 AC #3)
3. Verification checklist links directly to unit/integration evidence for bundle planning and dedupe. (ST-023 AC #5)

## Validation

- Execute smoke run and immediate rerun using same fixture inputs.
- Confirm output counts and identifiers remain stable across reruns.
- Record checklist evidence and reviewer sign-off.

## Deliverables

- Pilot-city smoke fixture specification.
- Repeatable smoke execution and verification checklist.
- Evidence bundle for ST-023 acceptance review.
