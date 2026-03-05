CREATE TABLE IF NOT EXISTS canonical_document_spans (
    id TEXT PRIMARY KEY,
    canonical_document_id TEXT NOT NULL REFERENCES canonical_documents(id) ON DELETE CASCADE,
    artifact_id TEXT,
    artifact_scope TEXT NOT NULL DEFAULT '',
    stable_section_path TEXT NOT NULL CHECK (length(trim(stable_section_path)) > 0),
    page_number INTEGER CHECK (page_number IS NULL OR page_number > 0),
    line_index INTEGER CHECK (line_index IS NULL OR line_index >= 0),
    start_char_offset INTEGER CHECK (start_char_offset IS NULL OR start_char_offset >= 0),
    end_char_offset INTEGER CHECK (
        end_char_offset IS NULL
        OR (
            end_char_offset >= 0
            AND (start_char_offset IS NULL OR end_char_offset >= start_char_offset)
        )
    ),
    locator_fingerprint TEXT NOT NULL CHECK (length(trim(locator_fingerprint)) > 0),
    parser_name TEXT NOT NULL CHECK (length(trim(parser_name)) > 0),
    parser_version TEXT NOT NULL CHECK (length(trim(parser_version)) > 0),
    source_chunk_id TEXT,
    span_text TEXT,
    span_text_checksum TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (canonical_document_id, artifact_scope, locator_fingerprint, parser_name, parser_version)
);

CREATE INDEX IF NOT EXISTS idx_canonical_document_spans_document_ordering
    ON canonical_document_spans (
        canonical_document_id,
        artifact_scope,
        stable_section_path,
        page_number,
        line_index,
        start_char_offset,
        end_char_offset,
        locator_fingerprint,
        id
    );

CREATE INDEX IF NOT EXISTS idx_canonical_document_spans_document_artifact
    ON canonical_document_spans (canonical_document_id, artifact_scope, parser_name, parser_version);
