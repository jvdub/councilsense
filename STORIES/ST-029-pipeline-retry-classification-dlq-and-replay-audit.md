# Agenda Plan: Pipeline Retry Classification, DLQ, and Replay Audit

**Story ID:** ST-029  
**Phase:** Phase 4 (Operational hardening)  
**Requirement Links:** AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 4 — Hardening: quality gates, retries, DLQ/replay, alerts (Weeks 8–10), AGENDA_PLAN §7 Observability, operations, and runbook updates

## User Story

As an operator, I want source-aware retry classification and audited replay tooling so terminal failures can be recovered safely without duplicate side effects.

## Scope

- Implement source-aware retry classification with bounded attempts from AGENDA_PLAN section "Phase 4 — Hardening".
- Implement pipeline DLQ entities and replay workflows with actor/reason/idempotency auditing from AGENDA_PLAN sections "Data model and contract changes (v1-first)" and "Observability, operations, and runbook updates".
- Ensure replay is idempotent and non-destructive for publication state.

## Acceptance Criteria

1. Retry classification distinguishes transient vs terminal failure classes per stage/source type.
2. Terminal failures route to pipeline DLQ with full context fields for triage.
3. Replay actions require actor and reason metadata and are persisted in audit history.
4. Replayed work is idempotent and does not create duplicate publications/artifacts.
5. Integration tests validate retry caps, DLQ routing, and replay no-op safety.

## Implementation Tasks

- [ ] Implement retry policy matrix and bounded retry counters by stage/source.
- [ ] Implement pipeline DLQ persistence and triage metadata capture.
- [ ] Implement replay command path with actor/reason/idempotency audit fields.
- [ ] Add idempotent replay guards in stage execution layer.
- [ ] Add integration tests for failure classification, DLQ routing, and replay behavior.

## Dependencies

- ST-014
- ST-023
- ST-025

## Definition of Done

- Pipeline failures are classified, queued, and replayable with full auditability.
- Replay behavior is deterministic and idempotent.
- Operators have tested recovery workflows for terminal failures.
