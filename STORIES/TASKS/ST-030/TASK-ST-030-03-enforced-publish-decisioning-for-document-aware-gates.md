# Enforced Publish Decisioning for Document-Aware Gates

**Task ID:** TASK-ST-030-03  
**Story:** ST-030  
**Bucket:** backend  
**Requirement Links:** ST-030 Acceptance Criteria #2, AGENDA_PLAN §5 Phase 4 — Hardening, AGENDA_PLAN §8 Risks and mitigations

## Objective
Integrate document-aware gate outcomes into enforced-mode publish decisioning so threshold violations block or downgrade outputs per policy.

## Scope
- Define enforced-mode decision points in summarize/publish lifecycle.
- Map gate failure classes to policy outcomes (block, limited-confidence downgrade, or equivalent documented action).
- Propagate gate-reason detail into publish decision artifacts for auditability.
- Out of scope: promotion eligibility computation and rollback command/runbook definition.

## Inputs / Dependencies
- TASK-ST-030-01 threshold and reason-code contract.
- TASK-ST-030-02 report-only diagnostics model.
- Existing publish policy controls from ST-021 enforcement hooks.

## Implementation Notes
- Enforcement must be cohort/environment controlled and reversible via flags.
- Preserve baseline behavior when enforcement mode is not enabled.
- Ensure unresolved authority conflicts follow risk mitigation path (downgrade or block with explicit reason).

## Acceptance Criteria
1. Enforced mode can apply document-aware gates to publish outcomes by configured environment/cohort.
2. Threshold violations trigger policy-defined block/downgrade outcomes.
3. Publish decisions include traceable gate reason metadata.
4. Non-enforced cohorts retain current publish behavior.

## Validation
- Execute policy scenario matrix for pass/fail gate combinations in enforced mode.
- Verify correct block/downgrade behavior for authority-alignment and precision/coverage violations.
- Confirm decision artifacts preserve gate reason lineage.

## Deliverables
- Enforced policy mapping for document-aware gate failures.
- Publish decisioning integration notes and sample decision artifacts.
- Cohort/environment enforcement validation report.
