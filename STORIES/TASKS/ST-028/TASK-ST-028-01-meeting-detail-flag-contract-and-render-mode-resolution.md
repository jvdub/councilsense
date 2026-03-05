# Meeting Detail Flag Contract and Render Mode Resolution

**Task ID:** TASK-ST-028-01  
**Story:** ST-028  
**Bucket:** frontend  
**Requirement Links:** ST-028 Acceptance Criteria #1 and #4, AGENDA_PLAN §2 Scope and non-goals, AGENDA_PLAN §3 Target architecture (frontend), AGENDA_PLAN §5 Phase 3

## Objective
Define and implement deterministic render-mode resolution for meeting detail so flag-off remains baseline and additive mode activates only when required fields are available.

## Scope
- Define frontend flag contract for planned/outcomes and mismatch rendering gates.
- Implement meeting-detail mode resolution (`baseline` vs `additive`) from flags and payload shape.
- Define fallback behavior when additive blocks are missing, partial, or null.
- Out of scope: planned/outcomes component content rendering and mismatch severity UI details.

## Inputs / Dependencies
- ST-028 story scope and acceptance criteria.
- ST-027 additive API payload expectations.
- Existing meeting detail route and flag-loading patterns.

## Implementation Notes
- Treat mode resolution as reusable logic consumed by downstream rendering tasks.
- Ensure missing additive fields never break baseline sections.
- Record explicit precedence: hard-disable flag -> baseline, otherwise additive only when required data contract is satisfied.

## Acceptance Criteria
1. Render-mode contract is documented and deterministic for all flag and payload combinations.
2. Flag-off behavior routes to baseline rendering equivalent to current behavior.
3. Missing or partial additive fields route to baseline fallback without user-visible errors.
4. Downstream tasks can consume a single resolved mode/state contract.

## Validation
- Execute scenario matrix for flag-on/off with full/partial/missing additive payloads.
- Verify baseline route rendering output is unchanged for flag-off and fallback states.
- Review mode-resolution contract with API/frontend owners for rollout alignment.

## Deliverables
- Render-mode resolution specification.
- Flag and payload state matrix with expected UI mode.
- Meeting-detail integration notes for downstream tasks.
