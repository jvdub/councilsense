# Replay Idempotency and Duplicate Prevention Test Gate

**Task ID:** TASK-ST-014-05  
**Story:** ST-014  
**Bucket:** tests  
**Requirement Links:** ST-014 Acceptance Criteria #5, ST-009 idempotency guarantees

## Objective
Prove replay hardening does not violate idempotency and does not produce duplicate user notifications.

## Scope
- Add end-to-end replay test scenarios for duplicate and retry edge cases.
- Validate idempotent behavior across normal retry and replay paths.
- Record measurable replay quality outputs for release sign-off.
- Out of scope: adding new feature behavior outside replay safety checks.

## Inputs / Dependencies
- TASK-ST-014-03 replay implementation.
- TASK-ST-014-04 metrics definitions.

## Implementation Notes
- Include concurrent replay attempts on same DLQ item.
- Track duplicate notification emissions as a release-blocking metric.
- Include golden-path and failure-path replay coverage.

## Acceptance Criteria
1. Duplicate notification emission rate from replay tests is 0.
2. Replaying same DLQ item twice does not enqueue duplicates.
3. Idempotency behavior remains unchanged for non-replay notification flow.
4. Test report includes replay success/failure counts and duplicate metrics.

## Validation
- Run replay-focused integration suite in CI.
- Execute controlled concurrency replay test.
- Verify metrics and audit records align with test outcomes.

## Deliverables
- Replay safety test suite and fixtures.
- CI gating configuration for replay idempotency checks.
- Hardening evidence report with measurable outputs.
