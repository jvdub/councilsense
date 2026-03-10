# Agenda Plan: Frontend Planned/Outcomes and Mismatch Rendering

**Story ID:** ST-028  
**Phase:** Phase 3 (Frontend additive UX)  
**Requirement Links:** AGENDA_PLAN §3 Target architecture (frontend), AGENDA_PLAN §5 Phase 3 — API/frontend additive planned/outcomes + mismatches (Weeks 6–7), AGENDA_PLAN §2 Scope and non-goals

## User Story

As a resident, I want planned and outcomes sections with concise mismatch signals so I can compare what was planned versus what happened in one meeting detail view.

## Scope

- Implement planned/outcomes split rendering in existing meeting detail route from AGENDA_PLAN section "Target architecture (frontend)".
- Render compact mismatch indicators only when evidence-backed from AGENDA_PLAN section "Target architecture (frontend)".
- Preserve baseline rendering fallback when additive fields are absent or feature flags are off from AGENDA_PLAN sections "Phase 3" and "Scope and non-goals".

## Acceptance Criteria

1. Flag-off UI behavior is visually and functionally equivalent to baseline meeting detail.
2. Flag-on UI renders planned and outcomes sections from additive API fields.
3. Mismatch indicators appear only when mismatch entries include evidence-backed support.
4. UI gracefully falls back to baseline sections when additive fields are missing.
5. Frontend tests cover flag states, fallback states, and mismatch severity rendering.

## Implementation Tasks

- [ ] Add planned/outcomes section components in existing meeting detail surface.
- [ ] Implement mismatch indicator rendering rules and neutral/empty states.
- [ ] Wire feature flags and fallback behavior for additive-field absence.
- [ ] Add component/integration tests for baseline and additive modes.
- [ ] Validate UI performance and accessibility checks for new sections.

## Dependencies

- ST-007
- ST-027

## Definition of Done

- Meeting detail supports additive planned/outcomes rendering with safe fallback.
- Mismatch UI is evidence-backed and non-disruptive.
- Automated tests validate both rollout modes.
