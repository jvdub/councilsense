# Phase 1.5: Rubric Freeze + Fixture Scorecard

**Story ID:** ST-017  
**Phase:** Phase 1.5 (Hardening)  
**Requirement Links:** GAP_PLAN §Parity Targets, GAP_PLAN §Fixture + Scorecard, GAP_PLAN §Phase 0, GAP_PLAN §Gate B

## User Story
As a quality owner, I want a frozen rubric and repeatable fixture scorecard so parity checks are stable and comparable across runs.

## Scope
- Codify parity checks in backend test helpers/constants without changing runtime behavior.
- Add fixture scorecard generation for section completeness, topic semantics, specificity, grounding coverage, and evidence count/precision.
- Capture and persist pre-change baseline scores for Eagle Mountain and two structurally different meetings.

## Acceptance Criteria
1. Fixture set includes 2024-12-03 Eagle Mountain and at least two structurally different meetings, all runnable via existing local pipeline path.
2. Scorecard artifact is produced per run in JSON or markdown and includes all GAP_PLAN parity dimensions.
3. Rubric thresholds are centralized in test constants and reused by unit/integration checks.
4. Two consecutive reruns on unchanged inputs produce stable pass/fail outcomes and bounded score variance.
5. No runtime behavior change is introduced outside tests/scorecard instrumentation.

## Implementation Tasks
- [ ] Add/extend fixture manifest and deterministic loader coverage in backend tests.
- [ ] Implement reusable scorecard schema and writer for fixture runs.
- [ ] Centralize parity threshold constants and helper assertions.
- [ ] Add baseline capture workflow and artifact retention for pre-change comparison.
- [ ] Add rerun-stability tests/checks for rubric repeatability.

## Dependencies
- ST-005
- ST-011
- ST-012

## Definition of Done
- Rubric checks are frozen, measurable, and repeatable on the fixture set.
- Baseline scorecards exist and are available for delta comparison in subsequent hardening stories.
- Test suite includes deterministic checks for parity dimensions without changing production contract.
