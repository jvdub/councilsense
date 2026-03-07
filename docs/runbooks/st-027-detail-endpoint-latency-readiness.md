# ST-027 Detail Endpoint Latency Readiness

## Scope

- Story: ST-027
- Task covered: TASK-ST-027-05
- Endpoint: `GET /v1/meetings/{meeting_id}`
- Goal: prove additive planned/outcomes/mismatch blocks stay within the local release p95 budget before promotion.

## Evidence Artifacts

- Release evidence report: `config/ops/st-027-detail-endpoint-latency-report.json`
- Benchmark helper: `backend/src/councilsense/app/st027_detail_latency.py`
- Validation test: `backend/tests/test_st027_detail_endpoint_latency_regression.py`

## Measurement Procedure

1. Run the benchmark helper from the backend workspace root so the API boots with the same in-memory route stack used by the contract tests.
2. Keep the seeded meeting payload identical for both paths. The fixture includes the same claims, claim evidence, and hidden additive publish metadata in both scenarios; only the additive API flag changes.
3. Collect three repeated runs per scenario after warmup. Each run uses 15 warmup requests and 75 measured requests.
4. Compute p95 with the nearest-rank method from the measured request durations recorded with `time.perf_counter_ns`.
5. Treat the report as release evidence only when all thresholds below pass and the repeated-run p95 spread remains within the stability budget.

## Reproducible Commands

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_st027_detail_endpoint_latency_regression.py tests/test_meeting_detail_api.py
PYTHONPATH=src /home/jtvanwage/councilsense/.venv/bin/python -m councilsense.app.st027_detail_latency \
  --captured-by local-release-check \
  --environment local-dev \
  --output ../config/ops/st-027-detail-endpoint-latency-report.json
```

## Acceptance Thresholds

- Flag-off baseline: p95 must be `<= 35 ms`.
- Flag-on additive path: p95 must be `<= 50 ms`.
- Additive regression delta: flag-on p95 minus flag-off p95 must be `<= 15 ms`.
- Additive regression ratio: flag-on p95 divided by flag-off p95 must be `<= 1.50x`.
- Repeat stability: p95 spread across repeated runs for each scenario must be `<= 8 ms`.

These thresholds are intentionally scoped to the local release benchmark path for ST-027. They are not a production SLA and should not be reused as a broad infrastructure target.

## Release Decision Rules

- Ship when the release evidence report records `within_budget=true` and both scenarios remain stable across repeated runs.
- Hold rollout when any threshold fails or when repeated-run spread exceeds the stability budget.
- Re-run once after a failure to rule out transient local contention before changing flags.

## Mitigation and Rollback

If the additive path exceeds budget after a confirmatory rerun:

1. Stop any promotion of additive meeting-detail exposure for the affected environment.
2. Keep downstream UI and notification rollout gates unchanged until API latency is back inside budget.
3. Disable additive API exposure with `ST022_API_ADDITIVE_V1_FIELDS_ENABLED=false`.
4. Clear additive block selection with `ST022_API_ADDITIVE_V1_BLOCKS=`.
5. If any downstream rollout already occurred, follow the reverse-order flag sequence in `docs/runbooks/st-022-rollout-flag-matrix-and-rollback.md`.
6. Capture the failing report, the confirmatory rerun report, and the flag snapshot together in the release log so regression size and rollback timing are auditable.

## Notes

- No frontend behavior changes are required for this task.
- The benchmark fixture intentionally mirrors the additive serializer path introduced in TASK-ST-027-03 and the flag-state expectations validated in TASK-ST-027-04.
