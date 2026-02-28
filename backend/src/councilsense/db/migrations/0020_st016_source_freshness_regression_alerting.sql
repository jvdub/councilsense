CREATE TABLE IF NOT EXISTS source_freshness_breach_events (
    id TEXT PRIMARY KEY,
    event_schema_version TEXT NOT NULL CHECK (length(trim(event_schema_version)) > 0),
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (length(trim(source_type)) > 0),
    source_url TEXT NOT NULL CHECK (length(trim(source_url)) > 0),
    run_id TEXT NOT NULL REFERENCES processing_runs(id) ON DELETE CASCADE,
    parser_drift_event_id TEXT REFERENCES parser_drift_events(id) ON DELETE SET NULL,
    severity TEXT NOT NULL CHECK (severity IN ('warning', 'critical')),
    threshold_age_hours REAL NOT NULL CHECK (threshold_age_hours > 0),
    last_success_age_hours REAL NOT NULL CHECK (last_success_age_hours >= 0),
    last_success_at TEXT,
    evaluated_at TEXT NOT NULL,
    suppressed INTEGER NOT NULL DEFAULT 0 CHECK (suppressed IN (0, 1)),
    suppression_reason TEXT,
    maintenance_window_name TEXT,
    maintenance_window_starts_at TEXT,
    maintenance_window_ends_at TEXT,
    triage_payload_json TEXT NOT NULL CHECK (length(trim(triage_payload_json)) > 0),
    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, source_id)
);

CREATE INDEX IF NOT EXISTS idx_source_freshness_breach_events_city_detected
    ON source_freshness_breach_events (city_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_source_freshness_breach_events_source_detected
    ON source_freshness_breach_events (source_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_source_freshness_breach_events_severity_detected
    ON source_freshness_breach_events (severity, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_source_freshness_breach_events_suppressed_detected
    ON source_freshness_breach_events (suppressed, detected_at DESC);
