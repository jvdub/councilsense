# ST-012 Local Runtime Quickstart

Launch the full local runtime stack for MVP journey smoke checks.

## Prerequisites

- Docker with Compose plugin.
- `curl` and `python3` available on host.

## Startup

```bash
docker compose -f docker-compose.local.yml up -d --build
```

Services started by the local runtime:

- `web` (Next.js) on `http://localhost:3000`
- `api` (FastAPI) on `http://localhost:8000`
- `worker` (notification delivery loop)
- `db` (Postgres baseline)
- `storage` (MinIO baseline)
- `queue` (Redis queue-adapter baseline)

## Seed deterministic processing fixture

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime process-fixture
```

## Run smoke flow

```bash
./scripts/local_runtime_smoke.sh
```

Smoke flow validates:

1. Signup/authenticated profile access path.
2. Home-city onboarding patch path.
3. Processing fixture publication visibility in reader endpoints.
4. Notification delivery status reaches `sent`.
5. Re-running fixture preserves idempotent behavior (`sent` count remains stable).

## Local latest ingestion commands

Run from the `api` container to use the seeded city/source registry and local DB wiring.

### 1) Fetch latest meeting source (`fetch-latest`)

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime fetch-latest \
  --city-id city-eagle-mountain-ut
```

Fetches/parses the latest candidate from the enabled city source and persists a local HTML artifact + meeting row.

### 2) Process latest meeting (`process-latest`)

Deterministic (default):

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime process-latest \
  --city-id city-eagle-mountain-ut \
  --llm-provider none
```

Optional Ollama provider:

```bash
docker compose -f docker-compose.local.yml exec -T api \
  python -m councilsense.app.local_runtime process-latest \
  --city-id city-eagle-mountain-ut \
  --llm-provider ollama \
  --ollama-endpoint http://host.docker.internal:11434 \
  --ollama-model llama3.2:3b \
  --ollama-timeout-seconds 20
```

Processes the latest (or specified) meeting through extract → summarize → publish, emitting a JSON envelope.

### 3) Fetch + process in one command (`run-latest`)

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

Runs ingest + processing stages in sequence and returns a single JSON envelope.

## Shutdown

```bash
docker compose -f docker-compose.local.yml down --remove-orphans
```
