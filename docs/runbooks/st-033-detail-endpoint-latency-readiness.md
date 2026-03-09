# ST-033 Detail Endpoint Latency Readiness

## Scope

- Story: ST-033
- Task covered: TASK-ST-033-05
- Endpoint: `GET /v1/meetings/{meeting_id}`
- Goal: prove additive resident-relevance fields stay backward-compatible and within the local detail-endpoint regression budget before frontend rollout.

## Evidence Artifacts

- Release evidence report: `config/ops/st-033-detail-endpoint-latency-report.json`
- Contract and compatibility coverage: `backend/tests/test_st033_resident_relevance_additive_contract.py`
- Detail endpoint parity coverage: `backend/tests/test_meeting_detail_api.py`
- Artifact validation: `backend/tests/test_st033_detail_endpoint_latency_regression.py`

## Measurement Procedure

1. Use the ST-033 full structured-relevance contract fixture as the representative relevance-enabled payload.
2. Keep ST-027 additive planned/outcomes blocks enabled for both paths so the only variable is resident-relevance projection.
3. Measure the same seeded meeting three times per scenario after 15 warmup requests and 75 measured requests.
4. Treat `ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED=false` as the flag-off baseline and `true` as the additive comparison path.
5. Compute p95 with the nearest-rank method from `time.perf_counter_ns` durations captured around the FastAPI test client request.

## Reproducible Commands

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q \
  tests/test_st033_resident_relevance_additive_contract.py \
  tests/test_meeting_detail_api.py \
  tests/test_st033_detail_endpoint_latency_regression.py -k 'st033'

cd backend
PYTHONPATH=src /home/jtvanwage/councilsense/.venv/bin/python - <<'PY'
import importlib.util
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.app.st027_detail_latency import (
    DetailEndpointLatencyThresholds,
    _issue_token,
    _temporary_environment,
    build_detail_endpoint_latency_report,
)
from councilsense.db import PILOT_CITY_ID

repo_root = Path('/home/jtvanwage/councilsense')
module_path = repo_root / 'backend' / 'tests' / 'test_meeting_detail_api.py'
spec = importlib.util.spec_from_file_location('st033_detail_test_helpers', module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

fixture_id = 'st033-flag-on-full-structured-relevance'
scenario = module._load_st033_contract_scenario(fixture_id)
payload = scenario['payload']
meeting_id = payload['id']

def measure_runs(*, resident_relevance_enabled: bool, repeat_count: int, sample_count: int, warmup_count: int) -> list[list[float]]:
    runs: list[list[float]] = []
    auth_secret = 'st033-latency-secret'
    env_updates = {
        'AUTH_SESSION_SECRET': auth_secret,
        'SUPPORTED_CITY_IDS': PILOT_CITY_ID,
        'ST022_API_ADDITIVE_V1_FIELDS_ENABLED': 'true',
        'ST022_API_ADDITIVE_V1_BLOCKS': 'planned,outcomes,planned_outcome_mismatches',
        'ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED': 'true' if resident_relevance_enabled else 'false',
    }
    for repeat_index in range(repeat_count):
        with _temporary_environment(env_updates):
            with TestClient(create_app()) as client:
                token = _issue_token(
                    user_id=f"st033-benchmark-{'on' if resident_relevance_enabled else 'off'}-{repeat_index}",
                    secret=auth_secret,
                    expires_in_seconds=300,
                )
                headers = {'Authorization': f'Bearer {token}'}
                module._set_home_city(client, headers=headers)
                module._seed_st033_contract_scenario(
                    client,
                    scenario=scenario,
                    scramble_projection_ordering=True,
                )
                for _ in range(warmup_count):
                    response = client.get(f'/v1/meetings/{meeting_id}', headers=headers)
                    if response.status_code != 200:
                        raise RuntimeError(f'warmup failed: {response.status_code}')
                samples: list[float] = []
                for _ in range(sample_count):
                    started_at = time.perf_counter_ns()
                    response = client.get(f'/v1/meetings/{meeting_id}', headers=headers)
                    finished_at = time.perf_counter_ns()
                    if response.status_code != 200:
                        raise RuntimeError(f'measured request failed: {response.status_code}')
                    samples.append(round((finished_at - started_at) / 1_000_000.0, 3))
                runs.append(samples)
    return runs

repeat_count = 3
sample_count = 75
warmup_count = 15
report = build_detail_endpoint_latency_report(
    flag_off_runs_ms=measure_runs(
        resident_relevance_enabled=False,
        repeat_count=repeat_count,
        sample_count=sample_count,
        warmup_count=warmup_count,
    ),
    flag_on_runs_ms=measure_runs(
        resident_relevance_enabled=True,
        repeat_count=repeat_count,
        sample_count=sample_count,
        warmup_count=warmup_count,
    ),
    repeat_count=repeat_count,
    sample_count=sample_count,
    warmup_count=warmup_count,
    thresholds=DetailEndpointLatencyThresholds(
        flag_off_p95_max_ms=35.0,
        flag_on_p95_max_ms=40.0,
        flag_on_p95_delta_max_ms=8.0,
        flag_on_p95_ratio_max=1.25,
        repeat_run_p95_spread_max_ms=8.0,
    ),
    fixture_profile={
        'fixture_id': fixture_id,
        'city_id': payload['city_id'],
        'meeting_id': meeting_id,
        'payload_shape': 'st033 full structured relevance with additive planned and outcomes blocks',
        'top_level_impact_tag_count': len(payload['structured_relevance']['impact_tags']),
        'planned_item_count': len(payload['planned']['items']),
        'outcome_item_count': len(payload['outcomes']['items']),
        'planned_item_relevance_field_count': len({'subject', 'location', 'action', 'scale', 'impact_tags'} & set(payload['planned']['items'][0].keys())),
        'outcome_item_relevance_field_count': len({'subject', 'location', 'action', 'scale', 'impact_tags'} & set(payload['outcomes']['items'][0].keys())),
    },
    captured_by='local-release-check',
    environment='local-dev',
    generated_at_utc=datetime.now(UTC),
)
report['task_id'] = 'TASK-ST-033-05'
report['story_id'] = 'ST-033'
report['scenarios'][1]['scenario_id'] = 'flag_on_resident_relevance_additive'
print(json.dumps(report, indent=2, sort_keys=True))
PY
```

## Acceptance Thresholds

- Flag-off baseline: p95 must be `<= 35 ms`.
- Flag-on resident-relevance path: p95 must be `<= 40 ms`.
- Resident-relevance regression delta: flag-on p95 minus flag-off p95 must be `<= 8 ms`.
- Resident-relevance regression ratio: flag-on p95 divided by flag-off p95 must be `<= 1.25x`.
- Repeat stability: p95 spread across repeated runs for each scenario must be `<= 8 ms`.

These thresholds are local rollout checks for additive resident-relevance projection. They are not a production SLA.

## Release Decision Rules

- Ship when the report records `within_budget=true` and the compatibility/parity tests pass with the flag on and off.
- Hold rollout when any latency threshold fails or when flag-on and flag-off parity diverge after resident-relevance fields are ignored.
- Re-run once after a failure to rule out transient local contention before changing flags.

## Mitigation and Rollback

If the resident-relevance path exceeds budget or breaks parity after a confirmatory rerun:

1. Stop promotion of resident-relevance rendering for the affected environment.
2. Disable resident-relevance API exposure with `ST033_API_RESIDENT_RELEVANCE_FIELDS_ENABLED=false`.
3. Keep ST-027 additive blocks enabled only if their independent rollout remains healthy.
4. Capture the failing report, the confirmatory rerun report, and the flag snapshot together in the release log.
5. Open follow-up work before advancing to frontend rollout so ST-034 starts from a stable API baseline.

## Notes

- The representative benchmark payload is the ST-033 full structured-relevance fixture introduced by TASK-ST-033-04.
- The measured local evidence for this run stayed within budget: flag-off p95 `2.507 ms`, flag-on p95 `3.129 ms`, delta `0.622 ms`, ratio `1.248x`.