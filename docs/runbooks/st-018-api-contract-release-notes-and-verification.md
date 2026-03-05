# ST-018 API Contract Release Notes and Verification Runbook

- Story: ST-018
- Tasks covered: TASK-ST-018-05
- Release scope: additive `evidence_references` in meeting detail response

## Release notes

- Added top-level `evidence_references: string[]` to `GET /v1/meetings/{meeting_id}`.
- Field is additive and backward compatible; no existing field names, types, or semantics changed.
- For evidence-sparse meetings, `evidence_references` is returned as `[]`.
- Existing `claims[].evidence[]` contract is unchanged.

## Consumer impact

- Existing consumers that ignore unknown fields continue to work without changes.
- Consumers can adopt `evidence_references` incrementally without migration of legacy fields.

## Verification steps (local)

1. Run ST-018 contract and Gate A compatibility tests:

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_meeting_detail_api.py tests/test_st018_evidence_references_contract.py
```

Expected:
- all tests pass
- evidence-present fixture asserts non-empty `evidence_references`
- evidence-sparse fixture asserts explicit `[]`
- additive-delta test permits only `evidence_references` beyond legacy field set

2. Run broader backend safety path:

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q
```

Expected:
- suite remains green with no legacy meeting-detail regressions

3. Run local runtime API path (CI-adjacent behavior check):

```bash
docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90
```

Expected:
- command exits `0`
- generated meeting details include additive `evidence_references` when evidence exists

## CI command path

Use this contract path in CI for Gate A safety:

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q tests/test_meeting_detail_api.py tests/test_st018_evidence_references_contract.py
```

## Rollback and mitigation

If contract regressions are detected:

1. Revert ST-018 additive projection in `backend/src/councilsense/api/routes/meetings.py`.
2. Re-run ST-018 contract tests and meeting detail API tests.
3. Keep Gate A in blocking mode until additive-delta contract is restored.
4. Communicate that `evidence_references` rollout is paused; legacy fields remain source of truth.

## Handoff packet links

- Contract decision: `docs/runbooks/st-018-evidence-references-contract.md`
- Gate A report: `docs/runbooks/st-018-gate-a-contract-report.json`
- Tests: `backend/tests/test_meeting_detail_api.py`, `backend/tests/test_st018_evidence_references_contract.py`
- Fixtures: `backend/tests/fixtures/st018_evidence_references_contract_fixtures.json`
