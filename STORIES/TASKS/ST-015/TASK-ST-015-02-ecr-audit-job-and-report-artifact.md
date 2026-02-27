# ECR Audit Job and Weekly Report Artifact

**Task ID:** TASK-ST-015-02  
**Story:** ST-015  
**Bucket:** backend  
**Requirement Links:** FR-4, Success Metrics §8 (ECR), ST-015 Acceptance Criteria #1 and #4

## Objective
Implement scheduled audit computation that produces weekly ECR report artifacts from sampled published outputs.

## Scope
- Build scheduled audit job using sampling spec.
- Compute ECR and supporting counts.
- Persist and publish weekly report artifacts.
- Out of scope: manual reviewer actions and confidence threshold tuning controls.

## Inputs / Dependencies
- TASK-ST-015-01 sampling spec and report schema.
- Evidence grounding signals from ST-005.

## Implementation Notes
- Version the audit formula and report schema.
- Include confidence-bucket breakdowns for downstream operations.
- Store job runtime metadata (start/end, sample size, failures).

## Acceptance Criteria
1. Weekly job generates an ECR report artifact on schedule.
2. Report includes ECR percentage, numerator/denominator, and sample metadata.
3. Failed audit runs are visible with retryable status.
4. ECR trend can be computed week-over-week from stored artifacts.

## Validation
- Integration test for scheduled run and artifact persistence.
- Formula correctness test with fixed fixture dataset.
- Backfill test for at least two historical weeks.

## Deliverables
- Audit job implementation and scheduler integration.
- ECR report artifact schema and storage path.
- Automated tests for formula and job reliability.
