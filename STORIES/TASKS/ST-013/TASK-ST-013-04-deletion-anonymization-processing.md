# Deletion and Anonymization Processing Workflow

**Task ID:** TASK-ST-013-04  
**Story:** ST-013  
**Bucket:** backend  
**Requirement Links:** NFR-3, NFR-7, ST-013 Acceptance Criteria #3 and #4

## Objective
Implement deletion/anonymization processing that removes or anonymizes personal data within SLA while preserving immutable published provenance.

## Scope
- Build deletion request processing worker and status handling.
- Implement per-entity delete/anonymize policy application.
- Preserve append-only published provenance records per governance policy.
- Out of scope: UI controls and policy/legal discovery work.

## Inputs / Dependencies
- TASK-ST-013-01 policy matrix.
- TASK-ST-013-02 request lifecycle schema.

## Implementation Notes
- Separate irreversible actions behind explicit terminal states.
- Record before/after governance audit events for each processing phase.
- Track SLA timers from request acceptance to completion.

## Acceptance Criteria
1. Personal profile data is removed or anonymized according to policy.
2. Published provenance records remain immutable and queryable.
3. Deletion workflow enforces and records SLA compliance timing.
4. Reprocessing same deletion request is idempotent and safe.

## Validation
- Integration tests for delete/anonymize outcomes across data domains.
- SLA timing test using controlled clock or deterministic timestamps.
- Idempotency test for repeated worker execution.

## Deliverables
- Deletion/anonymization worker and policy application logic.
- Governance audit events for processing lifecycle.
- Automated tests for immutability, SLA, and idempotency.
