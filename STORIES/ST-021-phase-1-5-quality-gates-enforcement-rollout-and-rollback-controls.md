# Phase 1.5: Quality Gates Enforcement, Rollout, and Rollback Controls

**Story ID:** ST-021  
**Phase:** Phase 1.5 (Hardening)  
**Requirement Links:** GAP_PLAN §Phase 4, GAP_PLAN §Gate Matrix (A/B/C), GAP_PLAN §Rollback, NFR-4, NFR-5

## User Story
As a release owner, I want configurable quality gates with shadow-to-enforced rollout and rollback controls so parity can be enforced safely without destabilizing operations.

## Scope
- Add feature flags for topic hardening, specificity retention, and evidence projection behaviors.
- Implement report-only shadow gate mode and enforced gate mode using fixture scorecard outcomes.
- Define promotion/rollback controls and execution order aligned to GAP_PLAN.

## Acceptance Criteria
1. Feature flags exist for topic hardening, specificity retention, and evidence projection, and can be toggled by environment/cohort.
2. Report-only gate mode emits pass/fail diagnostics without blocking publish path.
3. Enforced mode blocks or downgrades publish path per quality policy after promotion criteria are met.
4. Promotion requires two consecutive green fixture runs for Gate A, Gate B, and Gate C prerequisites.
5. Rollback runbook and controls support disabling flags in reverse order (specificity → evidence projection → topic hardening) and returning gates to report-only mode.

## Implementation Tasks
- [ ] Implement/configure quality-hardening feature flags and environment-aware wiring.
- [ ] Implement shadow gate evaluation and diagnostics artifact generation.
- [ ] Implement enforced gate behavior and policy hooks for publish decisioning.
- [ ] Implement promotion checks based on consecutive green fixture runs.
- [ ] Add rollback controls/tests and operational documentation updates for runbook parity.

## Dependencies
- ST-014
- ST-016
- ST-017
- ST-018
- ST-019
- ST-020

## Definition of Done
- Shadow and enforced quality gate modes are operational with measurable promotion criteria.
- Rollout and rollback controls are tested and documented for operators.
- Gate A/B/C enforcement can be enabled safely without breaking existing consumers.
