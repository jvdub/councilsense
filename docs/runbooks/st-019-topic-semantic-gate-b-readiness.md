# ST-019 Topic Semantic Gate-B Readiness

## Scope

- Story: ST-019
- Tasks covered: TASK-ST-019-01 through TASK-ST-019-05
- Fixture manifest: `backend/tests/fixtures/st017_fixture_manifest.json`

## Artifacts

- Baseline topic semantic gap matrix: `config/ops/st-019-topic-semantic-baseline-matrix.json`
- Gate-B verification report: `docs/runbooks/st-019-topic-semantic-gate-b-verification-report.json`
- Rubric and scorecard source: `config/ops/st-017-fixture-baseline-scorecard.json`

## Verification Summary

- Topic semantic category totals are zero across baseline fixtures for:
  - `generic_token`
  - `weak_concept_phrase`
  - `missing_topic_evidence_mapping`
- Gate-B verification report status is `gate_b_passed: true`.
- Fixture statuses are all `ok` with stable topic semantic dimension results.

## Reproducible Commands

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st019_topic_semantic_hardening.py
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st017_fixture_manifest_and_scorecard.py tests/test_st017_baseline_and_gate_b_verification.py
```

## Contract Safety Notes

- Summary payload contract remains unchanged (`summary`, `key_decisions`, `key_actions`, `notable_topics`, `claims`).
- ST-018 additive `evidence_references` behavior remains intact.
- Topic hardening is additive and deterministic; no ST-020/ST-021 behavior is included in this scope.

## Residual Risk and Rollback Trigger

- Risk: future fixture text drift may reintroduce weak phrase labels if decision/action phrasing changes materially.
- Trigger: any non-zero topic semantic failure category count or Gate-B failure in fixture reruns.
- Rollback path: remove ST-019 token configuration overrides and revert to baseline fallback topic labels while retaining artifact capture.
