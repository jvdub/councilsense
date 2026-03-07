# ST-029 Pipeline DLQ Contract

Task: TASK-ST-029-02

This contract defines the persistence shape for terminal pipeline failures captured in `pipeline_dlq_entries`.

## Purpose

- Persist one source-scoped DLQ record when a stage failure becomes terminal.
- Preserve replay-targeting identifiers without implementing replay commands.
- Keep repeated terminal boundary writes idempotent for the same run, meeting, stage, and source.

## Idempotency Key

- `dlq_key = pipeline-dlq:{run_id}:{city_id}:{meeting_id}:{stage_name}:{source_id}`
- Repeated terminal inserts with the same key must reuse the existing record.
- New pipeline runs produce new DLQ entries because `run_id` changes.

## Required Fields

- `contract_version`: additive contract version, currently `st029-pipeline-dlq.v1`
- `run_id`, `city_id`, `meeting_id`, `stage_name`, `source_id`, `source_type`
- `stage_outcome_id`: linkage back to `processing_stage_outcomes`
- `failure_classification`: `transient` or `terminal`
- `terminal_reason`: `retry_exhausted` or `non_retryable`
- `retry_policy_version`, `terminal_attempt_number`, `max_attempts`
- `error_code`, `error_type`, `error_message`
- `payload_references_json`: stage payload artifacts needed for replay targeting
- `triage_metadata_json`: operator-facing context including policy key, failure details, and source snapshot context when available
- `terminal_transitioned_at`

## Status Vocabulary

- `open`: initial terminal failure state written by TASK-ST-029-02
- `triaged`: operator reviewed and classified the incident
- `replay_ready`: operator approved the item for replay
- `replayed`: a later replay task linked a completed replay action
- `dismissed`: terminal item intentionally closed without replay

Allowed transitions:

- `open -> triaged | replay_ready | dismissed`
- `triaged -> replay_ready | dismissed`
- `replay_ready -> replayed | dismissed`
- `replayed` and `dismissed` are terminal

## Payload Reference Mapping

- `ingest`: typically `raw_artifact_uri` when raw capture already exists
- `extract`: `raw_artifact_uri`
- `summarize`: `extracted_text_uri`
- `publish`: any stage-owned publish artifact reference when available

## Replay Consumer Expectations

- Later replay tasks should target DLQ rows by `dlq_key` or `id` and must not derive scope from free-form logs.
- Replay eligibility should use `status`, `failure_classification`, `terminal_reason`, and the source/run/stage identifiers already stored here.
- Replay requests must capture `actor_user_id`, `replay_reason`, and an operator-supplied `idempotency_key`.
- Replay execution must persist `requested`, `queued`, `replayed`, `noop`, and `failed` outcomes in `pipeline_replay_audit_events`.
- Duplicate-replay prevention must preserve the existing publication/artifact state and surface the guard reason in replay audit metadata.

## Ownership And Escalation

- Primary owner: `ops-pipeline-oncall`
- Secondary owner: `backend-oncall`
- Escalate to: `platform-owner`
- Escalate immediately when the same `dlq_key` fails replay twice after mitigation, replay metadata is incomplete, or the replay outcome stays `failed` after a bounded retry window.

## Operator Recovery Workflow

1. Identify the terminal failure in `pipeline_dlq_entries` using `dlq_key`, `run_id`, `meeting_id`, `stage_name`, and `source_id`.
2. Review `triage_metadata_json` and confirm the terminal boundary is understood before replaying.
3. Confirm the incident is source-scoped and record the alert class or incident reference that justified replay.
4. Record the operator identity as `actor_user_id`, the remediation explanation as `replay_reason`, a unique `idempotency_key`, and an `incident_reference` for the recovery attempt.
5. Submit the replay request only when the DLQ row is `open` or `triaged`; the command transitions the row to `replay_ready` and records the audit trail.
6. Execute replay and verify the terminal outcome in `pipeline_replay_audit_events` before closing the incident.

Required operator evidence:

- `actor_user_id`
- `replay_reason`
- `idempotency_key`
- `incident_reference`
- `alert_class`
- `dlq_key`
- terminal replay outcome: `replayed`, `noop`, or `failed`

## Observability Queries

Replay command/execution logs emit structured events named `pipeline_replay_command` and `pipeline_replay_execution` with the standard correlation keys:

- `city_id`
- `meeting_id`
- `run_id`
- `dedupe_key` (the replay request key)
- `stage`
- `outcome`

Additional replay fields required for triage:

- `replay_outcome`
- `actor_user_id`
- `idempotency_key`
- `replay_reason`
- `dlq_key`
- `guard_reason_code`

Suggested SQL for DLQ triage:

```sql
SELECT dlq_key, status, terminal_reason, terminal_attempt_number, max_attempts, error_code, error_message
FROM pipeline_dlq_entries
WHERE status IN ('open', 'triaged', 'replay_ready')
ORDER BY terminal_transitioned_at DESC;
```

Suggested SQL for replay audit verification:

```sql
SELECT replay_request_key, actor_user_id, replay_reason, idempotency_key, event_type, result_metadata_json, created_at
FROM pipeline_replay_audit_events
WHERE dlq_key = ?
ORDER BY created_at ASC, id ASC;
```

No-op recovery expectations:

- `event_type = 'noop'` indicates the recovery attempt was safely short-circuited.
- `guard_reason_code = 'publish_stage_outcome_already_materialized'` confirms publication replay did not duplicate summary artifacts.
- `guard_reason_code = 'stage_already_processed'` confirms the stage had already reached a processed terminal state.