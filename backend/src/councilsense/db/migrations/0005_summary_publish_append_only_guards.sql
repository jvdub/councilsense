CREATE TRIGGER IF NOT EXISTS trg_summary_publications_append_only_update
BEFORE UPDATE ON summary_publications
BEGIN
    SELECT RAISE(ABORT, 'summary_publications is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_summary_publications_append_only_delete
BEFORE DELETE ON summary_publications
BEGIN
    SELECT RAISE(ABORT, 'summary_publications is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_publication_claims_append_only_update
BEFORE UPDATE ON publication_claims
BEGIN
    SELECT RAISE(ABORT, 'publication_claims is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_publication_claims_append_only_delete
BEFORE DELETE ON publication_claims
BEGIN
    SELECT RAISE(ABORT, 'publication_claims is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_claim_evidence_pointers_append_only_update
BEFORE UPDATE ON claim_evidence_pointers
BEGIN
    SELECT RAISE(ABORT, 'claim_evidence_pointers is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_claim_evidence_pointers_append_only_delete
BEFORE DELETE ON claim_evidence_pointers
BEGIN
    SELECT RAISE(ABORT, 'claim_evidence_pointers is append-only');
END;
