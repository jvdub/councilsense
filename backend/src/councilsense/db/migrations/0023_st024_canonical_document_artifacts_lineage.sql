CREATE TABLE IF NOT EXISTS canonical_document_artifacts (
    id TEXT PRIMARY KEY,
    canonical_document_id TEXT NOT NULL REFERENCES canonical_documents(id) ON DELETE CASCADE,
    artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('raw', 'normalized')),
    storage_uri TEXT,
    content_checksum TEXT NOT NULL CHECK (length(trim(content_checksum)) > 0),
    lineage_parent_artifact_id TEXT REFERENCES canonical_document_artifacts(id) ON DELETE SET NULL,
    lineage_root_checksum TEXT NOT NULL CHECK (length(trim(lineage_root_checksum)) > 0),
    lineage_depth INTEGER NOT NULL DEFAULT 0 CHECK (lineage_depth >= 0),
    normalizer_name TEXT,
    normalizer_version TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (canonical_document_id, artifact_kind, content_checksum),
    CHECK (lineage_parent_artifact_id IS NULL OR lineage_parent_artifact_id <> id)
);

CREATE INDEX IF NOT EXISTS idx_canonical_document_artifacts_document_checksum
    ON canonical_document_artifacts (canonical_document_id, content_checksum, artifact_kind, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_canonical_document_artifacts_root_checksum
    ON canonical_document_artifacts (lineage_root_checksum, lineage_depth ASC, created_at ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_canonical_document_artifacts_lineage_parent
    ON canonical_document_artifacts (lineage_parent_artifact_id);
