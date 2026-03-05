# Contract Fixtures and Rerun Stability Snapshot Verification

**Task ID:** TASK-ST-026-04  
**Story:** ST-026  
**Bucket:** tests  
**Requirement Links:** ST-026 Acceptance Criteria #2, #4, AGENDA_PLAN §6 Testing and validation plan

## Objective

Create contract fixtures and snapshot tests that validate stable additive `evidence_references_v2` payload shape and deterministic ordering across reruns.

## Scope

- Add fixture coverage for mixed precision levels and multi-document evidence references.
- Add snapshot/contract checks for v2 payload shape invariants.
- Add rerun consistency assertions for deterministic ordering output.
- Out of scope: operational scorecard and alerting thresholds.

## Inputs / Dependencies

- TASK-ST-026-02 deterministic ordering implementation.
- TASK-ST-026-03 v2 projection and compatibility gating behavior.
- Existing contract testing baseline for reader/publication payloads.

## Implementation Notes

- Keep fixtures representative of minutes + agenda/packet mixed source inputs.
- Ensure snapshots are stable and resistant to non-functional metadata drift.
- Validate both compatibility enabled and disabled states where applicable.

## Acceptance Criteria

1. Contract fixtures validate stable `evidence_references_v2` shape.
2. Snapshot tests confirm deterministic evidence ordering for identical reruns.
3. Test suite distinguishes additive v2 fields from baseline legacy payload expectations.
4. Regression checks fail on breaking shape/order changes.

## Validation

- Run targeted contract/snapshot tests for publication and reader payloads.
- Execute repeated fixture runs and compare outputs for order parity.
- Validate tests in both compatibility-mapping enabled and disabled modes.

## Deliverables

- New/updated fixture set for evidence v2 payload scenarios.
- Snapshot/contract test assertions for shape and deterministic ordering.
- Test evidence showing rerun output stability.
