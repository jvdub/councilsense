# ST-012 Local Latest Ingestion + Optional Ollama Workflow

Practical operator flow for the local `fetch-latest`, `process-latest`, and `run-latest` commands.

## Prerequisites

- Local stack running:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

- Use the `api` container command path:

```bash
python -m councilsense.app.local_runtime
```

- Pilot city is seeded by local runtime DB init (`city-eagle-mountain-ut`).

## Step-by-step commands

### A) Fetch latest source candidate

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime fetch-latest \
  --city-id city-eagle-mountain-ut
```

Expected terminal output: one JSON envelope with `command` = `fetch-latest`.

### B) Process latest deterministically

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime process-latest \
  --city-id city-eagle-mountain-ut \
  --llm-provider none
```

Expected stage order in `stage_outcomes`: `extract`, `summarize`, `publish`.

### C) Process latest with optional Ollama

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime process-latest \
  --city-id city-eagle-mountain-ut \
  --llm-provider ollama \
  --ollama-endpoint http://host.docker.internal:11434 \
  --ollama-model llama3.2:3b \
  --ollama-timeout-seconds 20
```

If Ollama succeeds, summarize stage uses provider `ollama`.
If Ollama is unavailable, the command falls back to deterministic summarize and still returns JSON output.

### D) One-command ingest + process (`run-latest`)

Deterministic:

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime run-latest \
  --city-id city-eagle-mountain-ut \
  --llm-provider none
```

Optional Ollama:

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime run-latest \
  --city-id city-eagle-mountain-ut \
  --llm-provider ollama \
  --ollama-endpoint http://host.docker.internal:11434 \
  --ollama-model llama3.2:3b \
  --ollama-timeout-seconds 20
```

Expected stage order in `stage_outcomes`: `ingest`, `extract`, `summarize`, `publish`.

## JSON envelope fields

All three commands emit a top-level JSON envelope with:

- `command`
- `run_id`
- `city_id`
- `source_id`
- `meeting_id`
- `status`
- `stage_outcomes` (array of `{stage, status, metadata}`)
- `warnings` (array)
- `error_summary` (`null` on success/limited-confidence, object on failures)

Common status values:

- `processed`: command completed without fallback/failure.
- `limited_confidence`: command completed with fallback or limited-confidence stage outcome.
- `failed`: terminal failure with `error_summary` populated.

## Troubleshooting

### Source fetch fails

Symptoms:

- `fetch-latest` or `run-latest` returns `status: failed`.
- `error_summary.stage` is `ingest`.

Actions:

- Verify `--city-id` and optional `--source-id` are valid for seeded/configured local sources.
- Verify source URL reachability from inside the `api` container.
- Re-run with explicit timeout if needed: `--timeout-seconds 20`.

### Ollama unreachable (automatic fallback)

Symptoms:

- `process-latest`/`run-latest` returns `status: limited_confidence`.
- `warnings` includes `ollama_fallback_to_deterministic`.
- Summarize stage metadata includes `provider_used: deterministic_fallback` and `fallback_reason`.

Actions:

- Validate Ollama endpoint/model (`--ollama-endpoint`, `--ollama-model`).
- If Ollama is intentionally unavailable, use deterministic mode explicitly with `--llm-provider none`.

### `limited_confidence` status

Interpretation:

- Pipeline completed, but confidence is reduced due to fallback behavior (for example Ollama fallback or limited-confidence stage outcome).

Actions:

- Review `stage_outcomes[*].status` and `metadata` for the stage that produced limited confidence.
- Review `warnings` for fallback markers before deciding whether to accept or rerun.
