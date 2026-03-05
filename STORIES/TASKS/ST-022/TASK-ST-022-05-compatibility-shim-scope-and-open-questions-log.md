# Compatibility Shim Scope and Open Questions Log

**Task ID:** TASK-ST-022-05  
**Story:** ST-022  
**Bucket:** docs  
**Requirement Links:** ST-022 Scope (compatibility shim optional), ST-022 Acceptance Criteria #4-#5, AGENDA_PLAN §10

## Objective
Document optional compatibility mapping scope and create a tracked decision log for unresolved contract questions with owners and due dates.

## Scope
- Define what legacy compatibility mappings are in-scope vs explicitly deferred.
- Mark compatibility work as non-blocking for pre-launch release criteria.
- Record open contract/schema questions, owners, due dates, and decision status.
- Out of scope: building compatibility shims or changing release gates beyond documented policy.

## Inputs / Dependencies
- TASK-ST-022-01 approved v1 contract and fixtures.
- TASK-ST-022-04 rollout/rollback matrix.
- Product/platform ownership for contract decisions.

## Implementation Notes
- Keep log format easy to audit in planning and release reviews.
- Include explicit blocker status field (`blocking` or `non-blocking`) per question.
- Require closure criteria for each open item.

## Acceptance Criteria
1. Compatibility mapping scope is documented as optional and explicitly non-blocking. (ST-022 AC #4)
2. Open questions list includes owner, due date, and current status for each item. (ST-022 AC #5)
3. Resolved items include recorded decision outcome and date. (ST-022 AC #5)

## Validation
- Verify every unresolved question has owner and due date.
- Confirm release criteria do not require compatibility shims.
- Review decision log in cross-team planning meeting.

## Deliverables
- Compatibility shim scope statement.
- Open questions and decision log register.
- Updated release-readiness checklist references.
