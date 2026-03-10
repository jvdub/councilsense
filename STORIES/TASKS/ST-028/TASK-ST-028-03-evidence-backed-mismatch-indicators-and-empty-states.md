# Evidence-Backed Mismatch Indicators and Empty States

**Task ID:** TASK-ST-028-03  
**Story:** ST-028  
**Bucket:** frontend  
**Requirement Links:** ST-028 Acceptance Criteria #3 and #5, AGENDA_PLAN §3 Target architecture (frontend), AGENDA_PLAN §5 Phase 3

## Objective

Implement compact mismatch indicator rendering that appears only when mismatch entries include evidence-backed support, with explicit neutral/empty states.

## Scope

- Define indicator visibility rules keyed to mismatch evidence availability.
- Implement compact mismatch severity representation for supported mismatch entries.
- Implement neutral and empty states when no evidence-backed mismatches are present.
- Out of scope: deep-link behavior and API contract redesign.

## Inputs / Dependencies

- TASK-ST-028-01 render-mode and fallback contract.
- ST-028 mismatch acceptance criteria and additive-field payload shape.
- Existing evidence display conventions used in meeting detail surfaces.

## Implementation Notes

- Treat absence of evidence support as non-render for mismatch signal components.
- Keep mismatch UI non-disruptive and additive to planned/outcomes sections.
- Ensure severity visual semantics remain deterministic for automated UI testing.

## Acceptance Criteria

1. Mismatch indicators render only for entries with evidence-backed support.
2. Entries without evidence-backed support do not show mismatch indicators.
3. Neutral and empty states are explicit and consistent when mismatch list is empty or unsupported.
4. Severity rendering behavior is documented for tests.

## Validation

- Execute UI cases for evidence-backed mismatch, unsupported mismatch, and empty mismatch lists.
- Verify indicator visibility logic across severity variants.
- Review mismatch rendering spec with product/frontend stakeholders.

## Deliverables

- Mismatch indicator visibility and severity rules.
- Neutral/empty-state behavior notes.
- UI verification artifacts for mismatch rendering permutations.
