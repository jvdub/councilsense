# ST-017 Baseline Capture and Gate B Workflow

## Scope

- Story: ST-017
- Tasks covered: TASK-ST-017-04 and TASK-ST-017-05
- Fixture manifest: `backend/tests/fixtures/st017_fixture_manifest.json`

## Retention and Naming Conventions

- Baseline retention artifact: `config/ops/st-017-fixture-baseline-scorecard.json`
- Gate B rerun verification artifact: `docs/runbooks/st-017-gate-b-verification-report.json`
- Rubric version lock: `st-017-rubric-v1`
- Baseline records are immutable snapshots. Later runs should produce additive snapshots with distinct capture timestamps.

## Local Baseline Capture

1. Run ST-017 fixture suite:

   ```bash
   cd backend
   /home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st017_fixture_manifest_and_scorecard.py
   ```

2. Validate baseline artifact metadata:

   ```bash
   /home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st017_baseline_and_gate_b_verification.py::test_st017_baseline_and_gate_b_artifacts_exist_and_are_schema_shaped
   ```

## CI Baseline Verification Path

- CI should run both ST-017 test modules:

  ```bash
  cd backend
  /home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st017_fixture_manifest_and_scorecard.py tests/test_st017_baseline_and_gate_b_verification.py
  ```

- Gate B verification is considered passing when:
  - `gate_b_passed` is `true`
  - Every fixture row status is `ok`
  - No dimension has `pass_fail_flip=true`
  - Every dimension delta is `<= allowed_delta`

## Retrieval and Dry-Run Comparison

- Baseline retrieval: `config/ops/st-017-fixture-baseline-scorecard.json`
- Gate B retrieval: `docs/runbooks/st-017-gate-b-verification-report.json`
- Dry-run comparison command:

  ```bash
  cd backend
  /home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st017_baseline_and_gate_b_verification.py::test_st017_baseline_capture_and_gate_b_stability_verification
  ```

## Operator Audit Metadata

- Baseline capture includes:
  - `captured_by`
  - `captured_from`
  - `captured_at_utc`
  - `manifest_path`
  - `rubric_version`
