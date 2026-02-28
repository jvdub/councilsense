ALTER TABLE governance_export_requests
ADD COLUMN processing_attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (processing_attempt_count >= 0);

ALTER TABLE governance_export_requests
ADD COLUMN max_processing_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_processing_attempts > 0);

CREATE TABLE IF NOT EXISTS governance_export_artifacts (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE REFERENCES governance_export_requests(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES governance_user_identities(user_id) ON DELETE RESTRICT,
    schema_version TEXT NOT NULL CHECK (length(trim(schema_version)) > 0),
    generated_at TEXT NOT NULL,
    content_json TEXT NOT NULL CHECK (length(trim(content_json)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governance_export_artifacts_user_created
    ON governance_export_artifacts (user_id, created_at DESC);
