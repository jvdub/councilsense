# Feature Flag Contract and Scan-Card Component Model

**Task ID:** TASK-ST-034-01  
**Story:** ST-034  
**Bucket:** frontend  
**Requirement Links:** ST-034 Acceptance Criteria #1 and #4, FR-4, REQUIREMENTS §13.5 Clarity Outcome

## Objective

Define the feature-flag behavior, render-mode contract, and scan-card component model for additive resident-relevance rendering in meeting detail.

## Scope

- Define frontend flag semantics for resident scan-card exposure.
- Define the component contract for subject, location, action, scale, and impact tags.
- Define fallback behavior when structured relevance fields are missing or partial.
- Out of scope: actual card rendering and evidence navigation wiring.

## Inputs / Dependencies

- ST-028 frontend additive render-mode patterns.
- ST-033 resident-relevance API contract and serializer behavior.

## Implementation Notes

- Follow the same flag-off baseline parity approach used for additive planned/outcomes rendering.
- Keep the component contract additive to the existing meeting detail page.
- Ensure partial-data cases are represented explicitly.

## Acceptance Criteria

1. Frontend flag contract defines when resident scan cards can render.
2. Scan-card component model covers structured relevance fields and optional impact tags.
3. Fallback states are defined for missing and partial structured data.
4. Baseline detail mode remains unchanged when the feature is disabled.

## Validation

- Review flag matrix for enabled, disabled, and malformed additive-data cases.
- Confirm component contract aligns with additive meeting detail patterns.
- Validate fallback rules against current baseline meeting detail behavior.

## Deliverables

- Frontend flag contract for resident scan cards.
- Scan-card component schema and fallback notes.
- Render-mode decision matrix for additive vs baseline states.