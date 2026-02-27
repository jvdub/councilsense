# Story Task Decomposition Pattern

This directory defines how stories (`ST-###`) are broken into small, agent-executable tasks.

Task instances now exist under per-story folders using the conventions below.

Story grouping used for subagent batching is documented in [GROUPS.md](GROUPS.md).

## Goals

- Keep each task small enough for one focused AI-agent run.
- Preserve strict traceability from task -> story -> requirements.
- Allow parallel execution where dependencies permit.
- Make completion state and handoffs explicit.

## Directory Convention

Use one folder per story:

- `STORIES/TASKS/ST-001/`
- `STORIES/TASKS/ST-002/`
- ...
- `STORIES/TASKS/ST-016/`

Inside each story folder, create:

1. `INDEX.md` — ordered task list and dependency graph for that story.
2. `TASK-<story>-<nn>-<slug>.md` — one file per actionable task.

Example:

- `TASK-ST-004-01-scheduler-enqueue.md`
- `TASK-ST-004-02-queue-contracts.md`
- `TASK-ST-004-03-run-lifecycle-persistence.md`

## Task Sizing Rules (AI-agent friendly)

A task should usually:

- Touch one layer when possible (DB, API, worker, frontend, ops/docs/tests).
- Be completable in one PR and one agent session.
- Have clear file-level scope and explicit acceptance checks.
- Avoid mixing feature build + broad refactor.

If a task violates two or more of those, split it.

## Correlation and IDs

Task ID format:

- `TASK-ST-###-NN`

Where:

- `ST-###` maps directly to a story ID.
- `NN` is 2-digit sequence local to that story (`01`, `02`, ...).

Required cross-links in each task:

- Story: `ST-###`
- Requirement refs: `FR-*`, `NFR-*`, or MVP section refs.
- Dependencies: other task IDs (`TASK-ST-###-NN`).

## Suggested Decomposition Buckets per Story

Use these buckets to keep task sets consistent across stories:

1. `data` — schema/migrations/constraints/indexes
2. `backend` — services/routes/workers/policies
3. `frontend` — UI routes/components/state flows
4. `ops` — metrics/logs/dashboards/runbooks
5. `tests` — unit/integration/e2e/contract checks
6. `docs` — deployment notes, ADR updates, acceptance evidence

Not every story needs all buckets.

## Task File Template (for future use)

Use this template when creating task files later:

```md
# <Task title>

**Task ID:** TASK-ST-###-NN  
**Story:** ST-###  
**Bucket:** data | backend | frontend | ops | tests | docs  
**Requirement Links:** <refs>

## Objective

<single clear outcome>

## Scope

- <in>
- <in>
- Out of scope: <explicit>

## Inputs / Dependencies

- <task IDs or stories>

## Implementation Notes

- <target files/modules>
- <constraints>

## Acceptance Criteria

1. <verifiable outcome>
2. <verifiable outcome>

## Validation

- Backend/data/worker tasks: `pytest -q`
- Frontend tasks: `npm --prefix archive/poc-2026-02-26/councilsense_ui run lint`
- Frontend build path (when UI contracts change): `npm --prefix archive/poc-2026-02-26/councilsense_ui run build`

## Deliverables

- <files changed / artifacts expected>
```

## Recommended Execution Pattern

Within each story folder:

- Put dependency-free tasks first (`01`, `02`).
- Put integration and verification tasks last.
- Keep one `INDEX.md` checklist as the source of truth for status.

This pattern keeps tasks easy to assign to AI agents while preserving end-to-end traceability.
