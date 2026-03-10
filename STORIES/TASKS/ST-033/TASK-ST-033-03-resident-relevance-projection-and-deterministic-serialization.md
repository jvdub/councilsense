# Resident-Relevance Projection and Deterministic Serialization

**Task ID:** TASK-ST-033-03  
**Story:** ST-033  
**Bucket:** backend  
**Requirement Links:** ST-033 Acceptance Criteria #2 and #4, FR-4, REQUIREMENTS §12.2 Summarization & Relevance Service, REQUIREMENTS §14(3)

## Objective

Project structured resident-relevance values into meeting detail payloads with deterministic serialization and evidence linkage behavior.

## Scope

- Map structured relevance values from summarization outputs into meeting detail response models.
- Preserve deterministic ordering for `impact_tags` and any linked evidence references.
- Support both meeting-level and additive item-level projection where data is available.
- Out of scope: contract fixture pack and latency regression verification.

## Inputs / Dependencies

- TASK-ST-033-02 feature flag gating.
- TASK-ST-032-04 carry-through and limited-confidence behavior.
- Existing meeting detail serialization patterns from ST-006 and ST-027.

## Implementation Notes

- Preserve additive-only behavior for all projected fields.
- Ensure serialization is stable across repeated requests for unchanged publications.
- Reuse evidence v2 ordering conventions where supporting evidence is surfaced.

## Acceptance Criteria

1. Meeting detail serializer can emit resident-relevance fields when available and enabled.
2. `impact_tags` ordering is deterministic across reruns for unchanged inputs.
3. Linked evidence references remain stable and additive.
4. Omitted or partial structured values do not break baseline serializer behavior.

## Validation

- Validate deterministic payload snapshots for unchanged representative publications.
- Compare projection outputs across present, partial, and absent structured relevance states.
- Confirm evidence linkage behavior aligns with existing precision and ordering rules.

## Deliverables

- Serializer mapping for resident-relevance projection.
- Deterministic ordering rules for emitted structured fields.
- Representative payload snapshots for review.
