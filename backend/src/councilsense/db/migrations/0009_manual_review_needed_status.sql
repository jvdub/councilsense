PRAGMA foreign_keys = OFF;

CREATE TABLE processing_runs_new (
    id TEXT PRIMARY KEY,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    cycle_id TEXT NOT NULL CHECK (length(trim(cycle_id)) > 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'processed', 'failed', 'limited_confidence', 'manual_review_needed')),
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    parser_version TEXT NOT NULL DEFAULT 'unknown',
    source_version TEXT NOT NULL DEFAULT 'unknown'
);

INSERT INTO processing_runs_new (
    id,
    city_id,
    cycle_id,
    status,
    started_at,
    finished_at,
    created_at,
    updated_at,
    parser_version,
    source_version
)
SELECT
    id,
    city_id,
    cycle_id,
    status,
    started_at,
    finished_at,
    created_at,
    updated_at,
    parser_version,
    source_version
FROM processing_runs;

DROP TABLE processing_runs;
ALTER TABLE processing_runs_new RENAME TO processing_runs;

CREATE INDEX idx_processing_runs_city_status
    ON processing_runs (city_id, status);

CREATE INDEX idx_processing_runs_cycle_city
    ON processing_runs (cycle_id, city_id);

CREATE TABLE processing_stage_outcomes_new (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    meeting_id TEXT NOT NULL CHECK (length(trim(meeting_id)) > 0),
    stage_name TEXT NOT NULL CHECK (stage_name IN ('ingest', 'extract', 'summarize', 'publish')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'processed', 'failed', 'limited_confidence', 'manual_review_needed')),
    metadata_json TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, city_id, meeting_id, stage_name)
);

INSERT INTO processing_stage_outcomes_new (
    id,
    run_id,
    city_id,
    meeting_id,
    stage_name,
    status,
    metadata_json,
    started_at,
    finished_at,
    created_at,
    updated_at
)
SELECT
    id,
    run_id,
    city_id,
    meeting_id,
    stage_name,
    status,
    metadata_json,
    started_at,
    finished_at,
    created_at,
    updated_at
FROM processing_stage_outcomes;

DROP TABLE processing_stage_outcomes;
ALTER TABLE processing_stage_outcomes_new RENAME TO processing_stage_outcomes;

CREATE INDEX idx_processing_stage_outcomes_run_city
    ON processing_stage_outcomes (run_id, city_id);

PRAGMA foreign_keys = ON;
