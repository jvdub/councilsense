# ST-030 Report-Only Gate Diagnostics

This runbook describes the machine-readable diagnostics emitted by the publish stage when document-aware gates are evaluated in report-only mode.

## Artifact path

Configure `COUNCILSENSE_QG_DIAGNOSTICS_ARTIFACT_PATH` or set `diagnostics_artifact_path` in `COUNCILSENSE_QG_CONFIG_JSON`.

Each publish writes one JSON line to the configured artifact path.

## Correlation fields

Every record includes:

- `run_id`
- `city_id`
- `meeting_id`
- `source_id`
- `source_type`
- `environment`
- `cohort`
- `promotion_scope_key`
- `generated_at_utc`

These fields allow filtering by rollout cohort and reconstructing promotion-readiness windows across consecutive runs.

## Document-aware report shape

The top-level rollout diagnostics payload now includes `document_aware_report` with:

- `schema_version`: `st-030-report-only-gate-diagnostics-v1`
- `contract_version`: document-aware gate contract version
- `evaluation_mode`: `report_only`
- `decision_impact`: `non_blocking`
- `diagnostics_complete`: boolean completeness check
- `all_gates_green`: overall pass/fail for document-aware gates
- `thresholds`: resolved threshold payload used for the run
- `gates`: one row for each of `authority_alignment`, `document_coverage_balance`, and `citation_precision`

Each gate row includes:

- `gate_id`
- `status`
- `score`
- `threshold`
- `passed`
- `reason_codes`
- `details`

## Publish behavior

Document-aware diagnostics are observational in this task. They do not block publish and they do not downgrade publish outcomes on their own, regardless of whether the broader ST-021 rollout mode is `report_only` or `enforced`.

## Validation

Focused backend coverage for this task:

- `backend/tests/test_st030_report_only_gate_diagnostics.py`
- `backend/tests/test_st021_quality_gate_rollout_controls.py`

Sample output: `docs/runbooks/st-030-report-only-gate-diagnostics.sample.json`