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

## Shutdown

```bash
docker compose -f docker-compose.local.yml down --remove-orphans
```
