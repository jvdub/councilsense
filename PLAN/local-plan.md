# Local execution plan (synthesized): Eagle Mountain latest ingestion + optional Ollama parse/summarize

## 1) Purpose and scope

Implement a **minimal, local-first** operator workflow to:

1. fetch the latest Eagle Mountain council source content, and
2. process parse → summarize → publish locally,
3. with optional Ollama summarization that never blocks deterministic validation.

### In scope (MVP-local)

- Extend existing backend local runtime CLI (`python -m councilsense.app.local_runtime`).
- Add latest-fetch + latest-process orchestration for `city-eagle-mountain-ut`.
- Reuse existing run/stage lifecycle persistence and summarization publish path.
- Add focused tests + runbook updates.

### Out of scope (this increment)

- No async worker/scheduler redesign.
- No multi-city expansion beyond extension points.
- No changes under `archive/`.
- No production API expansion required for MVP (CLI-first).
- No DB migration unless strictly required (prefer stage metadata).

---

## 2) Guiding principles (merged strengths)

### A. Minimal/surgical implementation

- Prefer small new modules adjacent to existing patterns.
- Keep existing commands (`process-fixture`, `worker-once`, `smoke-state`) unchanged.
- Avoid introducing new infrastructure or broad abstractions.

### B. Operator UX and command clarity

- Add explicit, scriptable commands: `fetch-latest`, `process-latest`, `run-latest`.
- Return machine-readable JSON envelopes with run IDs and stage outcomes.
- Include actionable error summaries and next checks in failures.

### C. Reliability, idempotency, and failure handling

- Deterministic meeting identity + upsert semantics for retry safety.
- Ordered stage outcomes (`ingest`, `extract`, `summarize`, `publish`) with terminal run status.
- Ollama is optional and bounded; fallback to deterministic summarization on failure.

---

## 3) Implementation design (repo-aligned)

## 3.1 CLI contract (source of truth)

Extend `backend/src/councilsense/app/local_runtime.py` with:

1. `fetch-latest`
   - Args: `--city-id` (default `city-eagle-mountain-ut`), optional `--source-id`, optional timeout.
   - Behavior: discover and persist latest source artifact + upsert meeting.

2. `process-latest`
   - Args: `--city-id`, optional `--meeting-id`, `--llm-provider none|ollama`, `--ollama-endpoint`, `--ollama-model`, `--ollama-timeout-seconds`.
   - Behavior: extract + summarize + publish for selected/latest meeting.

3. `run-latest`
   - Wrapper command that runs fetch + process and emits one consolidated JSON result.

### JSON output envelope (all new commands)

Return compact JSON with:

- `command`, `run_id`, `city_id`, `source_id`, `meeting_id`
- `status` (`processed` | `limited_confidence` | `failed`)
- `stage_outcomes` (ordered)
- `warnings` (including fallback reasons)
- `error_summary` (with failed stage + operator hint)

## 3.2 Local latest ingestion path

Add a focused fetch module (name flexible; e.g., `local_latest_fetch.py`) to:

- Resolve source URL from seeded city/source registry.
- Fetch Eagle Mountain agenda page with strict timeout and one transient retry.
- Parse latest candidate (title/date/link) using robust-minimal selectors.
- Build deterministic identity:
  - normalized fingerprint from `city_id + source_url + meeting_date + title (+ optional content hash)`
  - deterministic `meeting_uid` from fingerprint.
- Upsert meeting by `meeting_uid` (no duplicate logical meetings on rerun).
- Persist raw source snapshot under local data volume and include artifact URI/path in ingest metadata.

## 3.3 Local process path (extract/summarize/publish)

Add a focused orchestrator module (name flexible; e.g., `local_pipeline.py`) to:

- Create processing run before side effects.
- Execute ordered stages: `ingest -> extract -> summarize -> publish`.
- Persist stage outcomes + durations + metadata for each stage.
- Reuse existing summarization publish primitives (`publish_summarization_output`, existing repositories/services).

### Summarizer provider policy

- Default provider: deterministic local summarizer.
- Optional provider: Ollama via endpoint/model/timeout.
- On Ollama failure (unreachable/model missing/timeout/invalid response):
  - fallback to deterministic summarizer,
  - record `provider_used=deterministic_fallback` and `fallback_reason`,
  - terminal status usually `limited_confidence` unless quality gate deems fully acceptable.

### Terminal status rules

- `processed`: successful publish without reliability warnings.
- `limited_confidence`: fallback path, weak extraction, or confidence warning.
- `failed`: no publishable output due to ingest/extract/summarize hard failure.

---

## 4) Phased milestones (execution-ready)

## Phase 0 — Contract and scaffolding (0.5 day)

### Deliverables

- Final CLI arg definitions for `fetch-latest`, `process-latest`, `run-latest`.
- Shared JSON envelope helper for consistent command outputs.
- Event/log field contract aligned to current observability keys (`run_id`, `city_id`, `meeting_id`, `stage`, `outcome`, `dedupe_key`).

### Acceptance criteria

- New commands parse and return well-formed JSON even in dry/error paths.
- Existing local runtime commands remain unaffected.

## Phase 1 — Latest fetch + idempotent upsert (1 day)

### Deliverables

- Latest-source fetcher for Eagle Mountain.
- Deterministic fingerprint/meeting UID generation and meeting upsert.
- Ingest stage outcome persistence with artifact pointer.

### Acceptance criteria

- Running `fetch-latest` twice against unchanged source does not create duplicate logical meetings.
- `ingest` stage includes artifact URI/path and source metadata.
- Failures include explicit `error_summary` and `operator_hint`.

## Phase 2 — Deterministic process + publish (1 day)

### Deliverables

- Process orchestration for `extract`, `summarize`, `publish` stages.
- Integration with existing publication + evidence persistence path.
- `run-latest` wrapper command.

### Acceptance criteria

- Deterministic mode (`--llm-provider none`) completes end-to-end locally.
- Reader endpoints show latest meeting/publication after run.
- Run reaches deterministic terminal state with ordered stage outcomes.

## Phase 3 — Optional Ollama + fallback hardening (0.5–1 day)

### Deliverables

- Ollama provider integration with bounded timeout.
- Deterministic fallback behavior + warning metadata.
- Focused tests for unavailable endpoint/model/timeout scenarios.

### Acceptance criteria

- Ollama success path records `provider_used=ollama`.
- Ollama failure does not crash command; fallback publishes deterministic output.
- Fallback run status and warning metadata are explicit and operator-readable.

## Phase 4 — Docs, smoke validation, handoff (0.5 day)

### Deliverables

- Update `docs/runbooks/st-012-local-runtime-quickstart.md` with latest-flow commands.
- Add dedicated runbook for latest ingestion + optional Ollama local test workflow.
- Execute and record local validation matrix outcomes.

### Acceptance criteria

- Operator can run end-to-end flow from runbook only.
- `process-fixture` and existing local smoke workflow remain functional.

---

## 5) Test and validation plan

## 5.1 Automated tests (focused)

Add/extend backend tests for:

- Latest parser discovery from representative Eagle Mountain HTML fixtures.
- Idempotent meeting upsert/fingerprint behavior.
- `run-latest` JSON envelope and stage ordering.
- Ollama fallback behavior for endpoint/model/timeout/invalid response.
- Terminal run-state safety on mid-pipeline exceptions.

Suggested test files:

- `backend/tests/test_local_latest_parser.py`
- `backend/tests/test_local_latest_idempotency.py`
- `backend/tests/test_local_run_latest_contract.py`
- `backend/tests/test_local_ollama_fallback.py`
- `backend/tests/test_local_pipeline_terminal_state.py`

## 5.2 Manual local validation commands

1. Start stack:
   - `docker compose -f docker-compose.local.yml up -d --build`
2. Init DB:
   - `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime init-db`
3. Deterministic full flow:
   - `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider none`
4. Optional Ollama flow:
   - `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model llama3.2:3b --ollama-timeout-seconds 20`
5. Verify reader API:
   - `curl -s http://localhost:8000/v1/cities/city-eagle-mountain-ut/meetings | python -m json.tool`

## 5.3 Validation matrix

- Deterministic happy path: run succeeds and meeting/publication visible.
- Retry same source: no duplicate logical meeting/publication artifacts.
- Fetch timeout/DNS/5xx: ingest failure recorded with retryable metadata and hint.
- Parser drift: extract failure or limited-confidence path with retained artifact pointer.
- Ollama unavailable: deterministic fallback with warnings, not hard crash.

---

## 6) Reliability controls and rollback

### Reliability controls

- One processing run per command invocation before side effects.
- Always persist stage outcomes and terminal status.
- Strict bounded timeouts for network and Ollama calls.
- Explicit failure metadata keys: `error_code`, `error_class`, `retryable`, `operator_hint`.

### Rollback/fallback

1. Operational fallback: use deterministic mode (`--llm-provider none`).
2. Functional fallback: use existing `process-fixture` flow if latest parsing drifts.
3. Code rollback: revert only latest-flow modules/CLI additions; no broad impact expected.

---

## 7) Done definition (overall)

This plan is complete when all are true:

1. `run-latest` is retry-safe and does not create duplicate logical meetings on unchanged source.
2. Deterministic mode passes end-to-end on local stack without external dependencies.
3. Optional Ollama mode works when available and degrades gracefully when unavailable.
4. Stage-level diagnostics are operator-readable and sufficient for first-line triage.
5. Changes remain surgical, aligned to existing repo patterns, and do not touch `archive/`.
