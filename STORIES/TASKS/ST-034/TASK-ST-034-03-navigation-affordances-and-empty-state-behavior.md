# Navigation Affordances and Empty-State Behavior

**Task ID:** TASK-ST-034-03  
**Story:** ST-034  
**Bucket:** frontend  
**Requirement Links:** ST-034 Acceptance Criteria #3 and #4, REQUIREMENTS §13.2 Trust Outcome, REQUIREMENTS §13.5 Clarity Outcome

## Objective

Add navigation affordances from resident scan cards into supporting detail and evidence sections, with clear empty and sparse states for partial structured data.

## Scope

- Provide affordances from scan cards into supporting detail or evidence references.
- Define neutral handling for incomplete or sparse resident-relevance payloads.
- Preserve accessibility and non-blocking behavior when evidence linkage is absent.
- Out of scope: full accessibility regression suite and broader page verification.

## Inputs / Dependencies

- TASK-ST-034-01 scan-card contract.
- TASK-ST-034-02 scan-card rendering.
- Existing meeting detail evidence presentation patterns.

## Implementation Notes

- Reuse existing evidence and section anchors where possible.
- Avoid forcing navigation controls when the linked detail does not exist.
- Keep empty-state language resident-facing rather than internal.

## Acceptance Criteria

1. Residents can move from a scan card to supporting detail or evidence when links are available.
2. Partial-data cases show neutral fallback messaging without breaking layout.
3. Missing evidence linkage does not produce broken navigation affordances.
4. Behavior remains additive and does not alter baseline meeting detail navigation.

## Validation

- Test cards with and without linked evidence or detailed sections.
- Verify sparse-data states for missing location, scale, or impact tags.
- Confirm navigation affordances remain keyboard accessible.

## Deliverables

- Card-to-detail or card-to-evidence affordances.
- Sparse and empty-state handling for resident scan cards.
- Verification notes for additive navigation behavior.
