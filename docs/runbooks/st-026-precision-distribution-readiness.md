# ST-026 Precision Distribution Readiness

## Scope

- Story: ST-026
- Task covered: TASK-ST-026-05
- Scorecard source: `config/ops/st-017-fixture-baseline-scorecard.json`

## Artifacts

- Precision distribution report: `config/ops/st-026-precision-distribution-report.json`

## Verification Summary

- Precision distribution reporting breaks projected evidence into `offset`, `span`, `section`, and `file` classes.
- Run-level reporting keeps an explicit `precision_metadata_availability` state so reruns without precision metadata do not silently read as file-level regressions.
- Majority finer-than-file review is only applicable when at least one grounded reference projects into `evidence_references_v2`.
- City and source summaries roll up the same ratios for parser-drift and city-level triage.

## Reproducible Commands

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st026_precision_distribution_diagnostics_and_scorecard_reporting.py
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st020_specificity_and_evidence_precision_hardening.py tests/test_st017_fixture_manifest_and_scorecard.py tests/test_st017_baseline_and_gate_b_verification.py
```

## Release Readiness Checks

- Confirm `runs_meeting_majority_finer_than_file` is non-zero for cohorts where precision metadata is expected.
- Review any `runs_without_precision_metadata` separately from true file-level precision runs.
- Use `city_source_summaries` to isolate whether weak precision clusters by city, source type, or both.

## Contract Safety Notes

- No reader API shape changed in this task.
- Reporting is derived from the existing scorecard evidence dimension and mirrors the final v2 projection eligibility rules.
- No new rollout or enforcement behavior is introduced.