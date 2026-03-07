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
- Actor, reason, replay audit history, and duplicate-replay prevention remain out of scope for this task.