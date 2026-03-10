# Agenda Plan: Document-Aware Quality Gates and Authority Alignment Enforcement

**Story ID:** ST-030  
**Phase:** Phase 4 (Quality hardening and rollout enforcement)  
**Requirement Links:** AGENDA_PLAN §5 Phase 4 — Hardening: quality gates, retries, DLQ/replay, alerts (Weeks 8–10), AGENDA_PLAN §7 Observability, operations, and runbook updates, AGENDA_PLAN §8 Risks and mitigations, AGENDA_PLAN §10 Decision log and open questions

## User Story

As a release owner, I want document-aware gate dimensions and authority-alignment checks so rollout can move from report-only to enforced mode with safe rollback.

## Scope

- Implement gate dimensions for authority alignment, document coverage balance, and citation precision from AGENDA_PLAN sections "Phase 4 — Hardening" and "Observability, operations, and runbook updates".
- Extend existing rollout controls to support report-only to enforced promotions and reversible rollback from AGENDA_PLAN section "Decision log and open questions".
- Integrate source-conflict mitigation policies from AGENDA_PLAN section "Risks and mitigations".

## Acceptance Criteria

1. Report-only mode emits gate diagnostics for authority alignment, coverage balance, and precision ratios.
2. Enforced mode blocks/downgrades publish outputs when gate thresholds are violated.
3. Promotion requires two consecutive green report-only runs per configured environment.
4. Rollback to report-only and flag disable sequence is executable without schema rollback.
5. Runbook drills validate promotion and rollback controls end-to-end.

## Implementation Tasks

- [ ] Define and implement document-aware gate evaluators and threshold configuration.
- [ ] Integrate gate outcomes into publish decisioning for report-only and enforced modes.
- [ ] Implement promotion controller checks for consecutive green prerequisites.
- [ ] Implement reversible rollback controls and operator commands.
- [ ] Add operational test plan/drill scripts for promotion and rollback exercises.

## Dependencies

- ST-016
- ST-021
- ST-026
- ST-029

## Definition of Done

- Document-aware quality gates run in report-only and enforced modes.
- Promotion and rollback controls are validated in operational drills.
- Authority-alignment policy is enforced consistently during publish decisioning.
