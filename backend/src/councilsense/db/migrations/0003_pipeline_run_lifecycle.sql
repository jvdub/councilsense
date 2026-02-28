CREATE TABLE IF NOT EXISTS processing_runs (
    id TEXT PRIMARY KEY,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    cycle_id TEXT NOT NULL CHECK (length(trim(cycle_id)) > 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'processed', 'failed', 'limited_confidence')),
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processing_runs_city_status
    ON processing_runs (city_id, status);

CREATE INDEX IF NOT EXISTS idx_processing_runs_cycle_city
    ON processing_runs (cycle_id, city_id);

CREATE TABLE IF NOT EXISTS processing_stage_outcomes (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    meeting_id TEXT NOT NULL CHECK (length(trim(meeting_id)) > 0),
    stage_name TEXT NOT NULL CHECK (stage_name IN ('ingest', 'extract', 'summarize', 'publish')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'processed', 'failed', 'limited_confidence')),
    metadata_json TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, city_id, meeting_id, stage_name)
);

CREATE INDEX IF NOT EXISTS idx_processing_stage_outcomes_run_city
    ON processing_stage_outcomes (run_id, city_id);
