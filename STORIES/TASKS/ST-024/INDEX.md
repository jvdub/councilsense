# ST-024 Task Index — Canonical Documents, Artifacts, and Spans Persistence

- Story: [ST-024 — Canonical Documents, Artifacts, and Spans Persistence](../../ST-024-canonical-documents-artifacts-and-spans-persistence.md)
- Requirement Links: AGENDA_PLAN §3 Target architecture (normalization/storage), AGENDA_PLAN §4 Data model and contract changes (v1-first), AGENDA_PLAN §5 Phase 2 — Canonical document spans + evidence precision (Weeks 4–5)

## Ordered Checklist

- [ ] [TASK-ST-024-01](TASK-ST-024-01-canonical-document-schema-and-authority-metadata.md) — Canonical Document Schema and Authority Metadata
- [ ] [TASK-ST-024-02](TASK-ST-024-02-artifact-lineage-and-checksum-persistence.md) — Artifact Lineage and Checksum Persistence
- [ ] [TASK-ST-024-03](TASK-ST-024-03-span-persistence-and-stable-section-locators.md) — Span Persistence and Stable Section Locators
- [ ] [TASK-ST-024-04](TASK-ST-024-04-pipeline-write-path-and-pilot-backfill-hooks.md) — Pipeline Write Path and Pilot Backfill Hooks
- [ ] [TASK-ST-024-05](TASK-ST-024-05-referential-integrity-integration-tests-and-lineage-validation.md) — Referential Integrity Integration Tests and Lineage Validation

## Dependency Chain

- TASK-ST-024-01 -> TASK-ST-024-02
- TASK-ST-024-01 -> TASK-ST-024-03
- TASK-ST-024-02 -> TASK-ST-024-04
- TASK-ST-024-03 -> TASK-ST-024-04
- TASK-ST-024-04 -> TASK-ST-024-05

## Notes

- Keep migration strategy additive only; no destructive or rewrite migrations.
- Ensure revision and authority metadata are persisted at canonical-document level before artifact/span linking.
- Task 05 is release evidence for AC #5 and DoD lineage integrity expectations.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90`
