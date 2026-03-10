# Agenda Plan: Reader API Additive Planned/Outcomes and Mismatch Fields

**Story ID:** ST-027  
**Phase:** Phase 3 (API additive delivery)  
**Requirement Links:** AGENDA_PLAN §3 Target architecture (API), AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 3 — API/frontend additive planned/outcomes + mismatches (Weeks 6–7)

## User Story

As a frontend client, I want additive planned/outcomes and mismatch API fields so I can render document-aware meeting detail without breaking existing readers.

## Scope

- Add optional planned/outcomes/mismatch API fields from AGENDA_PLAN section "Target architecture (API)".
- Preserve existing meeting list/detail semantics while adding evidence v2 fields from AGENDA_PLAN section "Data model and contract changes (v1-first)".
- Implement additive field gating from AGENDA_PLAN section "Phase 3 — API/frontend additive planned/outcomes + mismatches".

## Acceptance Criteria

1. Existing meeting detail/list fields and semantics remain unchanged when additive flags are off.
2. Flag-on responses include `planned`, `outcomes`, and `planned_outcome_mismatches` blocks.
3. Evidence v2 fields are present when available and omitted safely when unavailable.
4. Contract tests validate flag-off baseline parity and flag-on additive payloads.
5. API p95 latency remains within agreed budget for meeting detail.

## Implementation Tasks

- [ ] Extend meeting detail serializer with additive planned/outcomes/mismatch blocks.
- [ ] Wire environment/feature-flag controls for additive field exposure.
- [ ] Preserve baseline contract behavior for flag-off responses.
- [ ] Add integration/contract tests for both flag states.
- [ ] Add API performance regression checks for detail endpoint.

## Dependencies

- ST-006
- ST-022
- ST-025
- ST-026

## Definition of Done

- Additive API contract is stable and backwards-safe by default.
- Flag-off behavior matches current baseline semantics.
- Flag-on payload supports frontend split rendering use cases.
