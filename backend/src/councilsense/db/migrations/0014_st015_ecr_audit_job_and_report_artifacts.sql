CREATE TABLE IF NOT EXISTS ecr_audit_runs (
    id TEXT PRIMARY KEY,
    audit_week_start_utc TEXT NOT NULL,
    audit_week_end_utc TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed_retryable')),
    owner_role TEXT NOT NULL CHECK (length(trim(owner_role)) > 0),
    scheduler_triggered_at_utc TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,
    formula_version TEXT NOT NULL CHECK (length(trim(formula_version)) > 0),
    report_version TEXT NOT NULL CHECK (length(trim(report_version)) > 0),
    seed TEXT,
    sample_size_requested INTEGER NOT NULL DEFAULT 0 CHECK (sample_size_requested >= 0),
    sample_size_actual INTEGER NOT NULL DEFAULT 0 CHECK (sample_size_actual >= 0),
    eligible_frame_count INTEGER NOT NULL DEFAULT 0 CHECK (eligible_frame_count >= 0),
    malformed_exclusion_count INTEGER NOT NULL DEFAULT 0 CHECK (malformed_exclusion_count >= 0),
    report_artifact_uri TEXT,
    error_code TEXT,
    error_message TEXT,
    runtime_metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (length(trim(runtime_metadata_json)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ecr_audit_runs_week_status
    ON ecr_audit_runs (audit_week_start_utc, status, created_at DESC);

CREATE TABLE IF NOT EXISTS ecr_audit_report_artifacts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES ecr_audit_runs(id) ON DELETE CASCADE,
    audit_week_start_utc TEXT NOT NULL UNIQUE,
    audit_week_end_utc TEXT NOT NULL,
    artifact_uri TEXT NOT NULL UNIQUE CHECK (length(trim(artifact_uri)) > 0),
    report_version TEXT NOT NULL CHECK (length(trim(report_version)) > 0),
    formula_version TEXT NOT NULL CHECK (length(trim(formula_version)) > 0),
    generated_at_utc TEXT NOT NULL,
    ecr REAL NOT NULL CHECK (ecr >= 0.0 AND ecr <= 1.0),
    claim_count INTEGER NOT NULL CHECK (claim_count >= 0),
    claims_with_evidence_count INTEGER NOT NULL CHECK (
        claims_with_evidence_count >= 0
        AND claims_with_evidence_count <= claim_count
    ),
    content_json TEXT NOT NULL CHECK (length(trim(content_json)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ecr_audit_report_artifacts_week
    ON ecr_audit_report_artifacts (audit_week_start_utc DESC);
