# Document-Aware Gate Dimensions and Threshold Contract

**Task ID:** TASK-ST-030-01  
**Story:** ST-030  
**Bucket:** backend  
**Requirement Links:** ST-030 Acceptance Criteria #1, AGENDA_PLAN §5 Phase 4 — Hardening, AGENDA_PLAN §8 Risks and mitigations

## Objective

Define the gate-dimension contract and threshold model for authority alignment, document coverage balance, and citation precision.

## Scope

- Define metric dimensions, score semantics, and pass/fail threshold policy for each document-aware gate.
- Define environment-scoped threshold configuration and validation rules.
- Define reason-code taxonomy for authority conflict, low coverage balance, and low citation precision outcomes.
- Out of scope: publish-path enforcement behavior and promotion-state tracking.

## Inputs / Dependencies

- ST-016 parser-drift and alert-threshold conventions.
- ST-021 gate rollout control patterns and flag contract behavior.
- ST-026 and ST-029 quality/authority model assumptions from prior hardening work.

## Implementation Notes

- Use minutes authority policy from AGENDA_PLAN decision log: minutes authoritative when available.
- Keep threshold contract deterministic and auditable across reruns and environments.
- Treat missing gate input dimensions as explicit gate-evaluation failures with diagnostics.

## Acceptance Criteria

1. Gate dimensions for authority alignment, document coverage balance, and citation precision are documented and implemented as a shared contract.
2. Threshold configuration supports environment-specific values with deterministic precedence.
3. Failed checks emit explicit reason codes aligned to source-conflict risk handling.
4. Contract defaults preserve report-only behavior when enforcement flags are disabled.

## Validation

- Execute configuration validation over representative environment matrices.
- Verify deterministic gate results for identical fixture inputs across reruns.
- Review threshold contract and reason codes with release owners.

## Deliverables

- Document-aware gate contract specification.
- Threshold configuration schema and validation rules.
- Reason-code catalog with representative examples.
