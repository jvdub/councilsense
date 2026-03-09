# Carry-Through Rules and Limited-Confidence Behavior

**Task ID:** TASK-ST-032-04  
**Story:** ST-032  
**Bucket:** backend  
**Requirement Links:** ST-032 Acceptance Criteria #3 and #5, FR-4, REQUIREMENTS §13.2 Trust Outcome, REQUIREMENTS §14(11)

## Objective

Enforce carry-through rules that prefer concrete subject phrasing over generic action-only summaries while preserving explicit uncertainty when evidence is insufficient or conflicting.

## Scope

- Upgrade generic summary and decision text when structured relevance fields support more specific phrasing.
- Define downgrade and omission behavior for conflicting or low-specificity cases.
- Keep carry-through behavior compatible with existing limited-confidence publication rules.
- Out of scope: scorecard verification and API serialization.

## Inputs / Dependencies

- TASK-ST-032-02 subject, location, action, and scale extraction.
- TASK-ST-032-03 impact classification.
- ST-025 authority-aware limited-confidence behavior.

## Implementation Notes

- Prefer concrete phrasing only when supported by grounded structured fields.
- Do not force structured detail into every summary sentence if support is partial or contested.
- Ensure fallback text remains fluent and explicit about uncertainty.

## Acceptance Criteria

1. Generic phrases are upgraded when a concrete, evidence-backed subject or location is available.
2. Conflicting or sparse evidence does not produce overconfident structured summary text.
3. Carry-through behavior preserves existing publication continuity and limited-confidence safeguards.
4. Outputs remain deterministic for unchanged inputs.

## Validation

- Compare generic-source and concrete-source fixture outputs.
- Verify low-specificity cases remain explicit about uncertainty.
- Confirm no regression in limited-confidence behavior for sparse evidence meetings.

## Deliverables

- Carry-through policy for structured relevance fields.
- Low-confidence and conflict fallback matrix.
- Representative before/after examples for generic vs concrete output phrasing.