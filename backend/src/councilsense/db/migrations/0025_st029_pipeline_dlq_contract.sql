CREATE TABLE pipeline_dlq_entries (
    id INTEGER PRIMARY KEY,
    dlq_key TEXT NOT NULL UNIQUE CHECK (length(trim(dlq_key)) > 0),
    contract_version TEXT NOT NULL CHECK (length(trim(contract_version)) > 0),
    run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    meeting_id TEXT NOT NULL CHECK (length(trim(meeting_id)) > 0),
    stage_name TEXT NOT NULL CHECK (stage_name IN ('ingest', 'extract', 'summarize', 'publish')),
    source_id TEXT NOT NULL CHECK (length(trim(source_id)) > 0),
    source_type TEXT NOT NULL CHECK (length(trim(source_type)) > 0),
    stage_outcome_id TEXT NOT NULL REFERENCES processing_stage_outcomes(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('open', 'triaged', 'replay_ready', 'replayed', 'dismissed')),
    failure_classification TEXT NOT NULL CHECK (failure_classification IN ('transient', 'terminal')),
    terminal_reason TEXT NOT NULL CHECK (terminal_reason IN ('retry_exhausted', 'non_retryable')),
    retry_policy_version TEXT NOT NULL CHECK (length(trim(retry_policy_version)) > 0),
    terminal_attempt_number INTEGER NOT NULL CHECK (terminal_attempt_number > 0),
    max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
    error_code TEXT NOT NULL CHECK (length(trim(error_code)) > 0),
    error_type TEXT,
    error_message TEXT,
    payload_references_json TEXT NOT NULL CHECK (length(trim(payload_references_json)) > 0),
    triage_metadata_json TEXT NOT NULL CHECK (length(trim(triage_metadata_json)) > 0),
    terminal_transitioned_at TEXT NOT NULL,
    triaged_at TEXT,
    replay_ready_at TEXT,
    replayed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pipeline_dlq_entries_city_status
    ON pipeline_dlq_entries (city_id, status, terminal_transitioned_at DESC);

CREATE INDEX idx_pipeline_dlq_entries_run
    ON pipeline_dlq_entries (run_id, terminal_transitioned_at DESC);

CREATE INDEX idx_pipeline_dlq_entries_source
    ON pipeline_dlq_entries (source_id, terminal_transitioned_at DESC);

CREATE INDEX idx_pipeline_dlq_entries_meeting
    ON pipeline_dlq_entries (meeting_id, terminal_transitioned_at DESC);

CREATE INDEX idx_pipeline_dlq_entries_stage_status
    ON pipeline_dlq_entries (stage_name, status, terminal_transitioned_at DESC);