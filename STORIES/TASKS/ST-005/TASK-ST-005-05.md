# ST-005 Verification and Evidence Retrieval Coverage

**Task ID:** TASK-ST-005-05  
**Story:** ST-005  
**Bucket:** tests  
**Requirement Links:** MVP §4.3(2-4), FR-4, FR-7(3), NFR-7

## Objective
Deliver focused test coverage proving evidence schema validity, limited-confidence behavior, and retrievability for reader consumers.

## Scope (+ Out of scope)
- Add integration tests for evidence pointer retrieval and shape.
- Add tests for limited-confidence labeling behavior.
- Add tests for append-only published record behavior.
- Out of scope: frontend rendering tests.

## Inputs / Dependencies
- TASK-ST-005-03, TASK-ST-005-04.
- Reader-facing meeting retrieval layer.

## Implementation Notes
- Assert exact required evidence fields in payloads.
- Cover both evidence-present and evidence-missing fixtures.
- Keep tests deterministic with fixed fixture artifacts.

## Acceptance Criteria
1. Tests fail if required evidence fields are missing or malformed.
2. Tests fail if weak evidence is not labeled `limited_confidence`.
3. Tests fail if published records can be overwritten in place.

## Validation
- Run targeted backend integration test suite for ST-005.
- Capture test run output for task evidence.

## Deliverables
- New/updated automated tests.
- Brief test evidence note linked from story tracking.
