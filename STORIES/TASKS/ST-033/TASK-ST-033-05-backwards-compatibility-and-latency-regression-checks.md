# Backwards-Compatibility and Latency Regression Checks

**Task ID:** TASK-ST-033-05  
**Story:** ST-033  
**Bucket:** tests  
**Requirement Links:** ST-033 Acceptance Criteria #5, REQUIREMENTS §12.3 Web App, REQUIREMENTS §14(3,10)

## Objective

Verify that additive resident-relevance API fields preserve existing client behavior and do not create unacceptable meeting detail latency regressions.

## Scope

- Add compatibility checks for consumers that ignore new resident-relevance fields.
- Validate enabled and disabled flag states for meeting detail responses.
- Capture latency regression evidence for detail endpoint behavior when projection is enabled.
- Out of scope: frontend rendering and rollout communications.

## Inputs / Dependencies

- TASK-ST-033-03 resident-relevance serializer extension.
- TASK-ST-033-04 contract fixture matrix.
- Existing latency verification patterns from ST-027 and ST-028.

## Implementation Notes

- Keep checks focused on additive safety and detail endpoint behavior.
- Use representative payload sizes for relevance-enabled meetings.
- Distinguish contract expansion from behavioral regressions.

## Acceptance Criteria

1. Existing client parsing assumptions remain valid when resident-relevance fields are absent or ignored.
2. Enabled responses remain additive and baseline-compatible.
3. Detail endpoint latency remains within agreed regression bounds for representative test cases.
4. Regression evidence is captured for rollout review.

## Validation

- Run backend integration and contract tests with feature flag on and off.
- Capture representative latency measurements for meeting detail requests.
- Review payload diffs to confirm additive-only changes.

## Deliverables

- Backwards-compatibility verification notes.
- Latency regression evidence for detail endpoint behavior.
- Flag-state regression test coverage.