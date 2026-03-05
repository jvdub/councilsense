# Planned and Outcomes Sections and Data Binding

**Task ID:** TASK-ST-028-02  
**Story:** ST-028  
**Bucket:** frontend  
**Requirement Links:** ST-028 Acceptance Criteria #2 and #4, AGENDA_PLAN §3 Target architecture (frontend), AGENDA_PLAN §5 Phase 3

## Objective
Implement additive planned and outcomes section rendering in the existing meeting detail view using additive API fields when additive mode is active.

## Scope
- Add planned section rendering from agenda/packet-derived additive fields.
- Add outcomes section rendering from minutes-derived additive fields.
- Bind additive data into existing meeting detail layout without introducing new top-level route surfaces.
- Out of scope: mismatch indicator semantics and fallback mode resolution logic.

## Inputs / Dependencies
- TASK-ST-028-01 render-mode contract.
- ST-027 API response fields for planned/outcomes blocks.
- Existing meeting detail composition and section layout conventions.

## Implementation Notes
- Keep planned and outcomes blocks optional and additive.
- Preserve baseline typography/spacing patterns to avoid UX redesign.
- Ensure deterministic ordering and section headers for consistent snapshots/tests.

## Acceptance Criteria
1. Additive mode renders planned and outcomes sections from additive API fields.
2. Section rendering does not alter baseline mode structure.
3. Missing subfields within additive blocks degrade gracefully with neutral placeholders.
4. Section outputs are stable for repeated payloads.

## Validation
- Run UI scenarios for full additive payload and partial additive payload variants.
- Confirm additive sections mount only in additive mode.
- Capture component-level verification for section ordering and content mapping.

## Deliverables
- Planned section rendering contract and mapping notes.
- Outcomes section rendering contract and mapping notes.
- Additive mode UI evidence for representative payloads.
