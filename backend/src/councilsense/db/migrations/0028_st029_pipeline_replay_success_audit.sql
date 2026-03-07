CREATE TABLE pipeline_replay_audit_events_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    replay_request_key TEXT NOT NULL CHECK (length(trim(replay_request_key)) > 0),
    idempotency_key TEXT NOT NULL CHECK (length(trim(idempotency_key)) > 0),
    dlq_entry_id INTEGER NOT NULL REFERENCES pipeline_dlq_entries(id) ON DELETE CASCADE,
    dlq_key TEXT NOT NULL CHECK (length(trim(dlq_key)) > 0),
    run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    meeting_id TEXT NOT NULL CHECK (length(trim(meeting_id)) > 0),
    stage_name TEXT NOT NULL CHECK (stage_name IN ('ingest', 'extract', 'summarize', 'publish')),
    source_id TEXT NOT NULL CHECK (length(trim(source_id)) > 0),
    stage_outcome_id TEXT NOT NULL REFERENCES processing_stage_outcomes(id) ON DELETE CASCADE,
    actor_user_id TEXT NOT NULL CHECK (length(trim(actor_user_id)) > 0),
    replay_reason TEXT NOT NULL CHECK (length(trim(replay_reason)) > 0),
    event_type TEXT NOT NULL CHECK (event_type IN ('requested', 'queued', 'replayed', 'noop', 'failed')),
    result_metadata_json TEXT NOT NULL CHECK (length(trim(result_metadata_json)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (replay_request_key, event_type)
);

INSERT INTO pipeline_replay_audit_events_v2 (
    id,
    replay_request_key,
    idempotency_key,
    dlq_entry_id,
    dlq_key,
    run_id,
    city_id,
    meeting_id,
    stage_name,
    source_id,
    stage_outcome_id,
    actor_user_id,
    replay_reason,
    event_type,
    result_metadata_json,
    created_at
)
SELECT
    id,
    replay_request_key,
    idempotency_key,
    dlq_entry_id,
    dlq_key,
    run_id,
    city_id,
    meeting_id,
    stage_name,
    source_id,
    stage_outcome_id,
    actor_user_id,
    replay_reason,
    event_type,
    result_metadata_json,
    created_at
FROM pipeline_replay_audit_events;

DROP TABLE pipeline_replay_audit_events;

ALTER TABLE pipeline_replay_audit_events_v2 RENAME TO pipeline_replay_audit_events;

CREATE INDEX idx_pipeline_replay_audit_dlq_created
    ON pipeline_replay_audit_events (dlq_entry_id, created_at DESC);

CREATE INDEX idx_pipeline_replay_audit_city_created
    ON pipeline_replay_audit_events (city_id, created_at DESC);

CREATE INDEX idx_pipeline_replay_audit_run_created
    ON pipeline_replay_audit_events (run_id, created_at DESC);

CREATE INDEX idx_pipeline_replay_audit_meeting_created
    ON pipeline_replay_audit_events (meeting_id, created_at DESC);

CREATE INDEX idx_pipeline_replay_audit_stage_source_created
    ON pipeline_replay_audit_events (stage_name, source_id, created_at DESC);

CREATE INDEX idx_pipeline_replay_audit_actor_created
    ON pipeline_replay_audit_events (actor_user_id, created_at DESC);