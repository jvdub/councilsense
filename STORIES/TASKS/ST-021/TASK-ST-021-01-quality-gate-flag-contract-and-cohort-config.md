# Quality Gate Feature Flag Contract and Cohort Configuration

**Task ID:** TASK-ST-021-01  
**Story:** ST-021  
**Bucket:** backend  
**Requirement Links:** ST-021 Acceptance Criteria #1, GAP_PLAN §Phase 4, GAP_PLAN §Gate Matrix (A/B/C)

## Objective
Define and wire the feature flag contract that controls topic hardening, specificity retention, and evidence projection behaviors by environment and rollout cohort.

## Scope
- Define canonical flag names, allowed values, default states, and precedence rules.
- Define environment/cohort targeting rules used by rollout controls.
- Add validation rules for unsupported combinations and missing configuration.
- Out of scope: gate score evaluation logic, publish-path enforcement behavior, and promotion automation.

## Inputs / Dependencies
- ST-019 and ST-020 behavior definitions for topic/specificity hardening.
- ST-018 additive evidence projection contract expectations.
- Existing runtime configuration loading pattern.

## Implementation Notes
- Treat flag schema as a contract consumed by downstream gate tasks.
- Record explicit mapping from each flag to behavior toggles.
- Include fail-safe defaults that preserve current non-enforced behavior when configuration is absent.

## Acceptance Criteria
1. A documented flag contract exists for topic hardening, specificity retention, and evidence projection controls.
2. Environment and cohort targeting rules are documented with deterministic precedence.
3. Invalid flag combinations and missing required settings are detected with explicit diagnostics.
4. Default behavior with all flags disabled is documented and preserves current publish path.

## Validation
- Execute configuration validation against representative env/cohort matrices.
- Verify deterministic resolution for conflicting cohort and environment settings.
- Perform peer review of the flag contract with release ownership.

## Deliverables
- Feature flag contract specification.
- Cohort/environment mapping table.
- Configuration validation checklist and example diagnostics.
