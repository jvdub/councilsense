CREATE TABLE IF NOT EXISTS summary_publications (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    processing_run_id TEXT REFERENCES processing_runs(id) ON DELETE SET NULL,
    publish_stage_outcome_id TEXT REFERENCES processing_stage_outcomes(id) ON DELETE SET NULL,
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    publication_status TEXT NOT NULL CHECK (publication_status IN ('processed', 'limited_confidence')),
    confidence_label TEXT NOT NULL CHECK (confidence_label IN ('high', 'medium', 'low', 'limited_confidence')),
    summary_text TEXT NOT NULL CHECK (length(trim(summary_text)) > 0),
    key_decisions_json TEXT NOT NULL DEFAULT '[]',
    key_actions_json TEXT NOT NULL DEFAULT '[]',
    notable_topics_json TEXT NOT NULL DEFAULT '[]',
    published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (meeting_id, version_no)
);

CREATE INDEX IF NOT EXISTS idx_summary_publications_meeting_published
    ON summary_publications (meeting_id, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_summary_publications_status
    ON summary_publications (publication_status, confidence_label);

CREATE TABLE IF NOT EXISTS publication_claims (
    id TEXT PRIMARY KEY,
    publication_id TEXT NOT NULL REFERENCES summary_publications(id) ON DELETE CASCADE,
    claim_order INTEGER NOT NULL CHECK (claim_order > 0),
    claim_text TEXT NOT NULL CHECK (length(trim(claim_text)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (publication_id, claim_order)
);

CREATE INDEX IF NOT EXISTS idx_publication_claims_publication_order
    ON publication_claims (publication_id, claim_order);

CREATE TABLE IF NOT EXISTS claim_evidence_pointers (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES publication_claims(id) ON DELETE CASCADE,
    artifact_id TEXT NOT NULL CHECK (length(trim(artifact_id)) > 0),
    section_ref TEXT,
    char_start INTEGER,
    char_end INTEGER,
    excerpt TEXT NOT NULL CHECK (length(trim(excerpt)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (char_start IS NULL AND char_end IS NULL)
        OR (char_start IS NOT NULL AND char_end IS NOT NULL AND char_start >= 0 AND char_end > char_start)
    )
);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim_id
    ON claim_evidence_pointers (claim_id);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_artifact
    ON claim_evidence_pointers (artifact_id);