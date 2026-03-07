ALTER TABLE claim_evidence_pointers
    ADD COLUMN document_id TEXT REFERENCES canonical_documents(id) ON DELETE SET NULL;

ALTER TABLE claim_evidence_pointers
    ADD COLUMN span_id TEXT REFERENCES canonical_document_spans(id) ON DELETE SET NULL;

ALTER TABLE claim_evidence_pointers
    ADD COLUMN document_kind TEXT CHECK (document_kind IN ('minutes', 'agenda', 'packet'));

ALTER TABLE claim_evidence_pointers
    ADD COLUMN section_path TEXT;

ALTER TABLE claim_evidence_pointers
    ADD COLUMN precision TEXT CHECK (precision IN ('offset', 'span', 'section', 'file'));

ALTER TABLE claim_evidence_pointers
    ADD COLUMN confidence TEXT CHECK (confidence IN ('high', 'medium', 'low'));

CREATE INDEX IF NOT EXISTS idx_claim_evidence_document_id
    ON claim_evidence_pointers (document_id);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_span_id
    ON claim_evidence_pointers (span_id);
