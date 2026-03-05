# ST-020 Specificity + Evidence Locator Precision Gate-B Readiness

## Scope

- Story: ST-020
- Tasks covered: TASK-ST-020-01 through TASK-ST-020-05
- Fixture manifest: `backend/tests/fixtures/st017_fixture_manifest.json`

## Artifacts

- Baseline specificity/locator matrix: `config/ops/st-020-specificity-locator-baseline-matrix.json`
- Gate-B verification report: `docs/runbooks/st-020-specificity-evidence-gate-b-verification-report.json`
- Rubric scorecard source: `config/ops/st-017-fixture-baseline-scorecard.json`

## Verification Summary

- Quantitative and entity-like anchors are harvested deterministically from fixture source text.
- Carry-through enforcement ensures at least one harvested anchor appears in `summary` or `key_decisions`/`key_actions` when anchors exist.
- Evidence projection deduplicates equivalent references and deterministically ranks precise locators ahead of file-level references.
- Grounding coverage for key decisions/actions remains complete across fixture reruns.
- Gate-B verification status is `gate_b_passed: true` for the ST-020 fixture rerun comparison.

## Reproducible Commands

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st020_specificity_and_evidence_precision_hardening.py
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st018_evidence_references_contract.py tests/test_st017_fixture_manifest_and_scorecard.py tests/test_st017_baseline_and_gate_b_verification.py tests/test_st019_topic_semantic_hardening.py
```

## Contract Safety Notes

- ST-018 additive `evidence_references` contract remains unchanged at the schema level.
- Evidence reference projection hardening is deterministic and additive (dedupe/ranking only).
- No ST-021 rollout/enforcement flag behavior is introduced in this scope.

## Residual Risk and Rollback Trigger

- Risk: parser source variance can reduce locator precision where sentence segmentation is sparse.
- Trigger: fixture reruns show non-majority precise locators or any grounding coverage regression.
- Rollback path: disable ST-020 carry-through/precision helpers in local pipeline and API projection while preserving existing ST-018 payload fields.
