# Meeting Detail Page with Evidence and Confidence

**Task ID:** TASK-ST-007-03  
**Story:** ST-007  
**Bucket:** frontend  
**Requirement Links:** MVP §4.5(2-3), FR-4

## Objective
Implement `/meetings/[meetingId]` page displaying summary, decisions/actions, notable topics, evidence references, and confidence labeling.

## Scope (+ Out of scope)
- Render required sections from detail payload.
- Display evidence snippets/links per claim/section.
- Render explicit `limited_confidence` banner/label when applicable.
- Out of scope: notification deep-link parameter parsing.

## Inputs / Dependencies
- TASK-ST-007-01.
- ST-006 detail endpoint payload.

## Implementation Notes
- Keep section order and hierarchy stable for readability.
- Make confidence indicator prominent and unambiguous.
- Handle missing optional fields gracefully without layout break.

## Acceptance Criteria
1. Detail page shows summary, decisions/actions, topics, and evidence references.
2. Limited-confidence meetings show explicit confidence banner/label.
3. Detail page handles loading/error state transitions cleanly.

## Validation
- Run component tests for normal and limited-confidence fixtures.
- Manual smoke check opening detail from list page.

## Deliverables
- `/meetings/[meetingId]` route/page and evidence/confidence components.
- Tests for detail rendering and confidence-state behavior.
