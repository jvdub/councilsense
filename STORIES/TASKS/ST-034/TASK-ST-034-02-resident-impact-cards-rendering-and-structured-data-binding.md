# Resident Impact Cards Rendering and Structured Data Binding

**Task ID:** TASK-ST-034-02  
**Story:** ST-034  
**Bucket:** frontend  
**Requirement Links:** ST-034 Acceptance Criteria #1 and #2, REQUIREMENTS §13.1 Resident Outcome, REQUIREMENTS §14(10)

## Objective

Render resident impact cards from additive structured relevance fields in meeting detail without disturbing the current baseline section layout.

## Scope

- Bind subject, location, action, scale, and impact tags into scan-card UI.
- Render cards only when resident-relevance mode is enabled and required data is present.
- Keep the existing summary, decisions/actions, topics, and evidence sections intact underneath.
- Out of scope: card-to-evidence navigation behavior and empty-state copy tuning.

## Inputs / Dependencies

- TASK-ST-034-01 scan-card component and flag contract.
- TASK-ST-033-03 resident-relevance serializer behavior.
- Existing meeting detail composition and styling patterns from ST-007 and ST-028.

## Implementation Notes

- Preserve layout hierarchy so cards act as a scan layer, not a replacement for detailed sections.
- Ensure deterministic card ordering for unchanged payloads.
- Keep rendering robust for partial field availability.

## Acceptance Criteria

1. Enabled resident-relevance mode renders scan cards from additive structured fields.
2. Impact tags render only when valid fields are present.
3. Baseline sections remain available and unchanged in structure.
4. Card rendering is deterministic for repeated payloads.

## Validation

- Exercise meetings with full, partial, and absent structured relevance payloads.
- Confirm no cards render in baseline mode.
- Verify ordering and content mapping remain stable across repeated renders.

## Deliverables

- Resident scan-card rendering in meeting detail.
- Structured field mapping notes for UI components.
- Representative render evidence for full and partial payloads.