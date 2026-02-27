# Confidence Calibration Policy Controls

**Task ID:** TASK-ST-015-04  
**Story:** ST-015  
**Bucket:** backend  
**Requirement Links:** NFR-4, ST-015 Acceptance Criteria #2

## Objective
Implement configurable confidence/evidence policy thresholds and labeling behavior for limited-confidence outputs.

## Scope
- Externalize confidence and evidence thresholds.
- Enforce limited-confidence labeling based on configured policy.
- Track threshold version applied to each processed output.
- Out of scope: human reviewer UI and weekly reporting dashboards.

## Inputs / Dependencies
- TASK-ST-015-03 reviewer outcomes (feedback signal).
- Existing summarization quality gate outputs from ST-005.

## Implementation Notes
- Support safe threshold rollout with versioned policy records.
- Keep defaults aligned with current MVP behavior until explicitly changed.
- Emit metrics on label distribution before/after calibration changes.

## Acceptance Criteria
1. Thresholds are configurable without code deployment.
2. Claims below evidence/confidence policy are labeled limited-confidence.
3. Threshold policy version is attached to processed outputs.
4. Calibration changes produce measurable label-distribution deltas.

## Validation
- Unit tests for threshold decision logic.
- Integration tests for policy version propagation.
- Regression tests to ensure known high-quality outputs remain unlabeled.

## Deliverables
- Threshold policy config and enforcement logic.
- Labeling behavior updates and metadata propagation.
- Tests and tuning guidance documentation.
