CREATE TABLE IF NOT EXISTS canonical_documents (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    document_kind TEXT NOT NULL CHECK (document_kind IN ('minutes', 'agenda', 'packet')),
    revision_id TEXT NOT NULL CHECK (length(trim(revision_id)) > 0),
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    is_active_revision INTEGER NOT NULL DEFAULT 1 CHECK (is_active_revision IN (0, 1)),
    authority_level TEXT NOT NULL CHECK (authority_level IN ('authoritative', 'supplemental')),
    authority_source TEXT NOT NULL CHECK (length(trim(authority_source)) > 0),
    authority_note TEXT,
    source_document_url TEXT,
    source_checksum TEXT,
    parser_name TEXT NOT NULL CHECK (length(trim(parser_name)) > 0),
    parser_version TEXT NOT NULL CHECK (length(trim(parser_version)) > 0),
    extraction_status TEXT NOT NULL CHECK (extraction_status IN ('pending', 'processed', 'failed', 'limited_confidence')),
    extraction_confidence REAL CHECK (extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)),
    extracted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (meeting_id, document_kind, revision_id),
    UNIQUE (meeting_id, document_kind, revision_number)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_canonical_documents_single_active_revision
    ON canonical_documents (meeting_id, document_kind)
    WHERE is_active_revision = 1;

CREATE INDEX IF NOT EXISTS idx_canonical_documents_meeting_kind_revision
    ON canonical_documents (meeting_id, document_kind, revision_number DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_canonical_documents_authority
    ON canonical_documents (authority_level, authority_source, document_kind);
