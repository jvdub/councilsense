# Pipeline Write Path and Pilot Backfill Hooks

**Task ID:** TASK-ST-024-04  
**Story:** ST-024  
**Bucket:** backend  
**Requirement Links:** ST-024 Acceptance Criteria #1, #2, #3, and #4, AGENDA_PLAN §3 Target architecture (normalization/storage), AGENDA_PLAN §5 Phase 2

## Objective
Wire ingestion/extraction pipeline stages to write canonical documents, artifacts, and spans in the required lifecycle order, with pilot-city backfill hooks.

## Scope
- Integrate canonical persistence writes into source-scoped ingest/extract workflow.
- Ensure write order and transaction boundaries enforce document -> artifact -> span lineage integrity.
- Add pilot backfill hooks/commands for initial city document sets without destructive operations.
- Out of scope: confidence policy changes and reader API projection changes.

## Inputs / Dependencies
- TASK-ST-024-02 artifact linkage behavior.
- TASK-ST-024-03 span persistence contracts.
- ST-023 bundle planner/source-scoped orchestration outputs.

## Implementation Notes
- Idempotent reruns must no-op on unchanged checksums while preserving lineage retrieval.
- Backfill hooks should support bounded city/date targeting and audit logging.
- Capture failure modes that preserve partial-state safety and replay capability.

## Acceptance Criteria
1. Pipeline stages persist canonical document/artifact/span records in correct lineage order.
2. Idempotent reruns do not create duplicate lineage rows for unchanged artifacts.
3. Pilot-city backfill hooks exist and can initialize canonical persistence from existing artifacts.
4. Persistence remains additive and replay-safe.

## Validation
- Run end-to-end local pipeline for pilot city meetings with minutes + supplemental sources.
- Replay same run inputs and verify duplicate suppression and stable lineage references.
- Execute bounded backfill dry-run and one real run with audit output.

## Deliverables
- Pipeline write-path integration updates.
- Backfill hook specification and operator command pattern.
- Replay/idempotency verification notes for canonical persistence lifecycle.
