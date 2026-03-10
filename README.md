# CouncilSense

CouncilSense helps residents stay informed about local government by ingesting city meeting data, producing evidence-grounded summaries, and powering notifications and a reader experience.

This repository contains the MVP + Phase 1.5 implementation backlog (`ST-001` through `ST-016`) with:

- Backend API + worker logic (FastAPI + Python)
- Frontend web app (Next.js)
- Local runtime parity tooling (Docker Compose)
- Ops/runbook artifacts for reliability, quality, and governance hardening

## Tech stack

- Backend: Python 3.12, FastAPI, SQLite for local runtime
- Frontend: Next.js 15 + React 19
- Local orchestration: Docker Compose
- Tests: `pytest` (backend), `vitest` (frontend)

## Repository layout

- `backend/` — API, worker/runtime commands, DB logic, backend tests
- `frontend/` — web UI and frontend tests
- `config/` — operational configuration artifacts
- `docs/runbooks/` — operational and compliance runbooks
- `scripts/` — local smoke and deployment helper scripts
- `STORIES/` — delivery backlog and task decomposition
- `archive/` — historical reference material (read-only)

## Prerequisites

- Python 3.12+
- Node.js 20+
- npm
- Docker + Docker Compose plugin (optional, for containerized local runtime)

## Quick start (recommended): Docker local runtime

From repository root:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

If your environment does not support `docker compose`, try:

```bash
docker-compose -f docker-compose.local.yml up -d --build
```

If both commands fail in WSL (for example, `docker: unknown command: docker compose` or
`docker-compose could not be found in this WSL 2 distro`), enable your distro under:
Docker Desktop → Settings → Resources → WSL Integration, then restart the shell.

Services:

- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`
- Postgres: `localhost:5432`
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`

Stop everything:

```bash
docker compose -f docker-compose.local.yml down --remove-orphans
```

Fallback:

```bash
docker-compose -f docker-compose.local.yml down --remove-orphans
```

Run the built-in smoke check:

```bash
bash scripts/local_runtime_smoke.sh
```

## Local runtime LLM providers

The local runtime supports deterministic summarization plus pluggable LLM-backed summarization.

- `--llm-provider none` uses the built-in deterministic path.
- `--llm-provider ollama` uses a local Ollama instance.
- `--llm-provider openai` uses an OpenAI-compatible hosted `chat/completions` endpoint.

Examples:

```bash
docker compose -f docker-compose.local.yml exec -T api \
	python -m councilsense.app.local_runtime run-latest \
	--city-id city-eagle-mountain-ut \
	--llm-provider ollama \
	--ollama-endpoint http://host.docker.internal:11434 \
	--ollama-model gemma3:12b \
	--ollama-timeout-seconds 90
```

```bash
export OPENAI_API_KEY=your-api-key

docker compose -f docker-compose.local.yml exec -T api \
	python -m councilsense.app.local_runtime run-latest \
	--city-id city-eagle-mountain-ut \
	--llm-provider openai \
	--llm-model gpt-4.1-mini \
	--llm-timeout-seconds 45
```

For hosted providers, the generic flags are:

- `--llm-endpoint`
- `--llm-model`
- `--llm-api-key`
- `--llm-timeout-seconds`

Env var fallbacks:

- `OPENAI_API_KEY`
- `COUNCILSENSE_OPENAI_API_KEY`
- `COUNCILSENSE_LLM_API_KEY`
- `COUNCILSENSE_OPENAI_ENDPOINT`
- `COUNCILSENSE_LLM_ENDPOINT`
- `COUNCILSENSE_OPENAI_MODEL`
- `COUNCILSENSE_LLM_MODEL`
- `COUNCILSENSE_LLM_TIMEOUT_SECONDS`

If a hosted or Ollama request fails, the runtime falls back to deterministic summarization and records a warning in the command envelope.

## Quick start: run backend + frontend directly

### 1) Backend setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./backend
```

### 2) Frontend setup

```bash
npm --prefix frontend install
```

### 3) Start backend

```bash
export COUNCILSENSE_RUNTIME_ENV=local
export COUNCILSENSE_SECRET_SOURCE=env
export AUTH_SESSION_SECRET=local-runtime-secret
export COUNCILSENSE_DISABLE_AUTH_GUARD=true
export COUNCILSENSE_LOCAL_DEV_AUTH_USER_ID=local-dev-user
export COUNCILSENSE_SQLITE_PATH="$PWD/.data/councilsense-local.db"
export SUPPORTED_CITY_IDS=city-eagle-mountain-ut

python -m uvicorn councilsense.app.main:app --app-dir backend/src --host 0.0.0.0 --port 8000
```

### 4) Start frontend (new terminal)

```bash
npm --prefix frontend run dev
```

Frontend defaults to `http://localhost:8000` for API. You can override with:

```bash
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
export NEXT_PUBLIC_DISABLE_AUTH_GUARD=true
export NEXT_PUBLIC_LOCAL_DEV_AUTH_TOKEN=local-dev-bypass-token
```

## Authentication note (local)

By default in this repo's local docker profile, auth guard is disabled for faster testing.

- Backend bypass flag: `COUNCILSENSE_DISABLE_AUTH_GUARD=true`
- Frontend bypass flag: `NEXT_PUBLIC_DISABLE_AUTH_GUARD=true`

If you re-enable auth guard, the backend expects a Bearer token signed with `AUTH_SESSION_SECRET`.
The smoke script (`scripts/local_runtime_smoke.sh`) generates a valid local token automatically.

## Running tests

### Backend

```bash
cd backend
/home/jtvanwage/councilsense/.venv/bin/python -m pytest -q
```

### Frontend

```bash
npm --prefix frontend run test
```

## Product and implementation references

- Requirements: `REQUIREMENTS.md`
- Architecture baseline: `ARCHITECTURE.md`
- Backend plan: `BACKEND.md`
- Frontend plan: `FRONTEND.md`
- Story backlog: `STORIES/README.md`
- Task orchestration status: `STORIES/TASKS/ORCHESTRATION_STATUS.md`
