CREATE TABLE IF NOT EXISTS processing_run_sources (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (length(trim(source_type)) > 0),
    source_url TEXT NOT NULL CHECK (length(trim(source_url)) > 0),
    parser_name TEXT NOT NULL CHECK (length(trim(parser_name)) > 0),
    parser_version TEXT NOT NULL CHECK (length(trim(parser_version)) > 0),
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_processing_run_sources_city_source_recorded
    ON processing_run_sources (city_id, source_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_processing_run_sources_run_source
    ON processing_run_sources (run_id, source_id);

CREATE TABLE IF NOT EXISTS parser_drift_events (
    id TEXT PRIMARY KEY,
    event_schema_version TEXT NOT NULL CHECK (length(trim(event_schema_version)) > 0),
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (length(trim(source_type)) > 0),
    source_url TEXT NOT NULL CHECK (length(trim(source_url)) > 0),
    parser_name TEXT NOT NULL CHECK (length(trim(parser_name)) > 0),
    baseline_parser_name TEXT NOT NULL CHECK (length(trim(baseline_parser_name)) > 0),
    baseline_parser_version TEXT NOT NULL CHECK (length(trim(baseline_parser_version)) > 0),
    current_parser_name TEXT NOT NULL CHECK (length(trim(current_parser_name)) > 0),
    current_parser_version TEXT NOT NULL CHECK (length(trim(current_parser_version)) > 0),
    baseline_run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    baseline_source_version TEXT NOT NULL CHECK (length(trim(baseline_source_version)) > 0),
    current_source_version TEXT NOT NULL CHECK (length(trim(current_source_version)) > 0),
    delta_context_json TEXT NOT NULL CHECK (length(trim(delta_context_json)) > 0),
    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_parser_drift_events_city_detected
    ON parser_drift_events (city_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_parser_drift_events_source_detected
    ON parser_drift_events (source_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_parser_drift_events_current_version_detected
    ON parser_drift_events (current_parser_version, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_parser_drift_events_baseline_version_detected
    ON parser_drift_events (baseline_parser_version, detected_at DESC);
