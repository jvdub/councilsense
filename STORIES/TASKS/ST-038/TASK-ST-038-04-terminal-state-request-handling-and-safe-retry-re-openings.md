# Terminal-State Request Handling and Safe Retry Re-Openings

**Task ID:** TASK-ST-038-04  
**Story:** ST-038  
**Bucket:** backend  
**Requirement Links:** ST-038 Acceptance Criteria #4, FR-7, NFR-1, NFR-4

## Objective

Define and implement the rules for new resident requests after terminal work states so failures can be retried safely without creating duplicate artifacts or losing audit history.

## Scope

- Define when terminal states allow a new on-demand request to create a fresh attempt.
- Reuse replay/retry safeguards to prevent duplicate side effects on reopen.
- Preserve full audit lineage across terminal failure and later re-request flows.
- Out of scope: operator replay UI, frontend copy, and non-terminal duplicate suppression.

## Inputs / Dependencies

- TASK-ST-038-03 on-demand lifecycle integration.
- ST-029 replay guards and side-effect protection.
- Existing publication/artifact idempotency constraints.

## Implementation Notes

- Treat completed and failed states differently where appropriate, but keep rules explicit.
- Preserve traceability from original terminal work to any reopened attempt.
- Ensure reopen behavior remains compatible with publication/artifact dedupe guarantees.

## Acceptance Criteria

1. Terminal failures can be retried or reopened without creating duplicate artifacts or publications. (ST-038 AC #4)
2. Reopened work preserves audit linkage to prior terminal attempts.
3. New requests are allowed only when the prior work is terminal, not merely delayed or in progress.

## Validation

- Integration tests for failure-then-retry request flows.
- Assertions that side-effect guards still prevent duplicate publication/artifact writes.
- Audit-history checks for reopened attempts.

## Deliverables

- Terminal-state reopen and retry rules.
- Safe integration with replay/idempotency safeguards.
- Integration tests for terminal failure to new-attempt flows.
