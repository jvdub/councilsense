# Structured Relevance Data Model and Internal Fields

**Task ID:** TASK-ST-032-01  
**Story:** ST-032  
**Bucket:** backend  
**Requirement Links:** ST-032 Acceptance Criteria #1 and #2, FR-4, REQUIREMENTS §12.2 Summarization & Relevance Service

## Objective

Define the internal structured relevance model for `subject`, `location`, `action`, `scale`, and `impact_tags` used by summarization output assembly.

## Scope

- Define field-level semantics and omission rules for structured resident-relevance data.
- Specify how structured relevance attaches to meeting-level and item-level summarization outputs.
- Identify evidence-linkage expectations for every structured field category.
- Out of scope: extraction heuristics, classification logic, and reader API exposure.

## Inputs / Dependencies

- ST-020 specificity and evidence precision hardening outputs.
- ST-025 authority-aware compose and limited-confidence policy.
- ST-026 evidence v2 linkage and deterministic ordering.

## Implementation Notes

- Keep the model additive to current summary structures.
- Favor omission over null-filled placeholders for unsupported fields.
- Ensure downstream API projection can preserve provenance for each structured value.

## Acceptance Criteria

1. Internal field definitions exist for `subject`, `location`, `action`, `scale`, and `impact_tags`.
2. Omission and low-confidence semantics are explicit for each field.
3. Structured relevance can be attached without changing baseline summary publication behavior.
4. Evidence-linkage expectations are documented for downstream projection and testing.

## Validation

- Review field model against current summarization output and evidence pointer contracts.
- Verify the model can represent both meeting-level and item-level relevance without required-field regressions.
- Confirm omission semantics are compatible with additive reader APIs.

## Deliverables

- Structured resident-relevance field specification.
- Omission and confidence behavior notes.
- Mapping notes for downstream API and frontend consumers.
