# ST-012 Task Index — Local-First + AWS Portable Runtime

- Story: [ST-012 — Local-First + AWS Portable Runtime](../../ST-012-local-first-and-aws-portable-runtime.md)
- Requirement Links: NFR-5, NFR-6, MVP §4.1-§4.5 (parity enabler)

## Ordered Checklist

- [x] [TASK-ST-012-01](TASK-ST-012-01-parity-architecture-contract.md) — Parity Architecture Contract
- [x] [TASK-ST-012-02](TASK-ST-012-02-environment-contract-and-startup-validation.md) — Environment Contract and Startup Validation
- [x] [TASK-ST-012-03](TASK-ST-012-03-local-runtime-compose-and-smoke-flow.md) — Local Runtime Compose and Smoke Flow
- [ ] [TASK-ST-012-04](TASK-ST-012-04-aws-baseline-wiring.md) — AWS Baseline Wiring
- [ ] [TASK-ST-012-05](TASK-ST-012-05-parity-checklist-ci-and-deployment-docs.md) — Parity Checklist, CI, and Deployment Docs

## Dependency Chain

- TASK-ST-012-01 -> TASK-ST-012-02
- TASK-ST-012-02 -> TASK-ST-012-03
- TASK-ST-012-02 -> TASK-ST-012-04
- TASK-ST-012-03 -> TASK-ST-012-05
- TASK-ST-012-04 -> TASK-ST-012-05

## Notes

- Keep one codebase, config-driven environment differences only.
- Preserve reliability behavior parity for queue, retries, and idempotency semantics.
- Ensure observability hooks are available in both local and cloud paths.

## Validation Commands

- `pytest -q`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run lint`
- `npm --prefix archive/poc-2026-02-26/councilsense_ui run build`
