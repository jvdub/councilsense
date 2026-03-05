# ST-025 Task Index — Authority-Aware Multi-Document Compose and Limited-Confidence Policy

- Story: [ST-025 — Authority-Aware Multi-Document Compose and Limited-Confidence Policy](../../ST-025-authority-aware-multi-document-compose-and-limited-confidence.md)
- Requirement Links: AGENDA_PLAN §3 Target architecture (summarization), AGENDA_PLAN §5 Phase 1 — MVP multi-source ingestion and publish continuity (Weeks 2–3), AGENDA_PLAN §8 Risks and mitigations

## Ordered Checklist

- [x] [TASK-ST-025-01](TASK-ST-025-01-deterministic-multi-document-compose-assembly.md) — Deterministic Multi-Document Compose Assembly
- [ ] [TASK-ST-025-02](TASK-ST-025-02-authority-aware-outcomes-decision-policy.md) — Authority-Aware Outcomes Decision Policy
- [ ] [TASK-ST-025-03](TASK-ST-025-03-limited-confidence-reason-codes-and-publish-wiring.md) — Limited-Confidence Reason Codes and Publish Wiring
- [ ] [TASK-ST-025-04](TASK-ST-025-04-source-conflict-and-partial-coverage-fixtures.md) — Source Conflict and Partial-Coverage Fixtures
- [ ] [TASK-ST-025-05](TASK-ST-025-05-deterministic-compose-and-confidence-transition-tests.md) — Deterministic Compose and Confidence Transition Tests

## Dependency Chain

- TASK-ST-025-01 -> TASK-ST-025-02
- TASK-ST-025-01 -> TASK-ST-025-03
- TASK-ST-025-02 -> TASK-ST-025-03
- TASK-ST-025-01 -> TASK-ST-025-04
- TASK-ST-025-03 -> TASK-ST-025-05
- TASK-ST-025-04 -> TASK-ST-025-05

## Notes

- Preserve publish continuity: partial-source meetings must still publish under `limited_confidence` when policy conditions require it.
- Keep authority policy explicit: minutes are authoritative for final decisions/actions when available; agenda/packet are supporting inputs.
- Task 05 is release evidence for deterministic compose order and confidence downgrade behavior.

## Validation Commands

- `pytest -q`
- `docker compose -f docker-compose.local.yml exec -T api python -m councilsense.app.local_runtime run-latest --city-id city-eagle-mountain-ut --llm-provider ollama --ollama-endpoint http://host.docker.internal:11434 --ollama-model qwen3:latest --ollama-timeout-seconds 90`
