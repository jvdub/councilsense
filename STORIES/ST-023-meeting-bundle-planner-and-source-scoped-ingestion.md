# Agenda Plan: Meeting Bundle Planner and Source-Scoped Ingestion

**Story ID:** ST-023  
**Phase:** Phase 1 (MVP multi-source ingestion)  
**Requirement Links:** AGENDA_PLAN §3 Target architecture (ingestion, normalization/storage, summarization, API, frontend), AGENDA_PLAN §5 Phase 1 — MVP multi-source ingestion and publish continuity (Weeks 2–3), AGENDA_PLAN §6 Testing and validation plan

## User Story

As a pipeline operator, I want deterministic meeting bundle planning and source-scoped ingestion so agenda, packet, and minutes artifacts are processed once per run without duplicate artifacts or publications.

## Scope

- Implement meeting bundle planning from AGENDA_PLAN section "Target architecture" to resolve expected source types per city/meeting.
- Implement source-scoped ingestion/extraction with checksum dedupe and idempotency keys from AGENDA_PLAN section "Phase 1 — MVP multi-source ingestion and publish continuity".
- Ensure deterministic reruns for the same city/meeting/source set.

## Acceptance Criteria

1. Pipeline creates a deterministic meeting bundle for each eligible meeting candidate.
2. Ingestion of duplicate source payloads is deduplicated by checksum/idempotency key.
3. Rerunning the same ingest window does not create duplicate documents/artifacts.
4. At least minutes + one supplemental artifact can be ingested for pilot city flows.
5. Unit/integration tests cover bundle planning and source-scoped dedupe behavior.

## Implementation Tasks

- [ ] Implement bundle planner that resolves minutes/agenda/packet expectations per meeting.
- [ ] Implement source-scoped idempotency key and dedupe key generation.
- [ ] Wire source ingest/extract outcomes to bundle-level state tracking.
- [ ] Add deterministic rerun tests for duplicate prevention.
- [ ] Add pilot-city smoke fixture with minutes + supplemental source ingestion.

## Dependencies

- ST-003
- ST-004
- ST-022

## Definition of Done

- Multi-source ingestion is deterministic and idempotent at source granularity.
- Pilot city ingest supports minutes plus supplemental artifacts.
- Test coverage validates duplicate prevention across reruns.
