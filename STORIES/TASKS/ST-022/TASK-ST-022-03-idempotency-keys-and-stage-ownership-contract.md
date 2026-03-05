# Idempotency Key Naming and Stage Ownership Contract

**Task ID:** TASK-ST-022-03  
**Story:** ST-022  
**Bucket:** backend  
**Requirement Links:** ST-022 Implementation Tasks (idempotency naming and stage ownership), AGENDA_PLAN §5 Phase 0 deliverables

## Objective
Define deterministic idempotency key naming rules and a stage ownership table that implementation teams will use in multi-source ingestion and publish stages.

## Scope
- Define key components and canonical string formats per stage (ingest, extract, summarize, publish).
- Define ownership boundaries and handoff contracts between stages.
- Define collision and replay expectations for same city/meeting/source inputs.
- Out of scope: runtime dedupe code changes and queue retry policy implementation.

## Inputs / Dependencies
- TASK-ST-022-01 contract entities and identifiers.
- TASK-ST-022-02 schema identifiers and constraints.
- Existing run/stage model in pipeline architecture.

## Implementation Notes
- Ensure naming includes city, meeting, source type, revision/checksum where required.
- Align ownership table to observability and replay diagnostics fields.
- Include examples for normal run, rerun, and duplicate payload scenarios.

## Acceptance Criteria
1. Idempotency key formats are specified per stage with deterministic field ordering. (ST-022 Implementation Tasks)
2. Stage ownership table identifies producer/consumer responsibilities and persisted handoff state. (ST-022 Implementation Tasks)
3. Replay/duplicate scenarios are covered with expected no-duplicate outcomes. (supports ST-023 dependency)

## Validation
- Walk through sample inputs and verify deterministic key generation outcomes.
- Confirm ownership mapping has no ambiguous stage boundaries.
- Review contract with pipeline and operations owners.

## Deliverables
- Idempotency key specification with examples.
- Stage ownership and handoff contract table.
- Replay/duplicate behavior matrix.
