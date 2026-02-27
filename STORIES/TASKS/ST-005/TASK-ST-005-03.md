# Claim Evidence Attachment

**Task ID:** TASK-ST-005-03  
**Story:** ST-005  
**Bucket:** backend  
**Requirement Links:** MVP §4.3(2-4), FR-4, NFR-7

## Objective
Attach at least one evidence citation/snippet to each key claim when source evidence is available, and persist it in the required schema.

## Scope (+ Out of scope)
- Implement claim-to-evidence linking logic.
- Persist evidence pointers with artifact_id, section/offset, and excerpt.
- Handle no-evidence cases by marking claim evidence gap for quality-gate consumption.
- Out of scope: final publish-state decisioning.

## Inputs / Dependencies
- TASK-ST-005-01, TASK-ST-005-02.
- Artifact text/section metadata from ingestion pipeline.

## Implementation Notes
- Enforce strict field validation before write.
- Prefer minimal but sufficient excerpt spans.
- Keep linkability from claim record to source artifact stable for reader API.

## Acceptance Criteria
1. Claims with available evidence include at least one valid evidence pointer.
2. Evidence records reject missing artifact_id/offset/excerpt fields.
3. Claims with weak/absent evidence are explicitly marked for gating.

## Validation
- Run unit tests for evidence mapper/validator.
- Run integration test verifying evidence retrieval for processed meeting.

## Deliverables
- Evidence attachment logic and validators.
- Tests for valid and missing-evidence paths.
