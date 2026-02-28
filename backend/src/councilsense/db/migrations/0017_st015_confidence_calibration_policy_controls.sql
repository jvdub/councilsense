ALTER TABLE summary_publications
    ADD COLUMN calibration_policy_version TEXT NOT NULL DEFAULT 'st015-calibration-policy-v1-default';

CREATE TABLE IF NOT EXISTS confidence_calibration_policies (
    version TEXT PRIMARY KEY,
    min_claim_count INTEGER NOT NULL CHECK (min_claim_count >= 0),
    min_total_evidence_pointers INTEGER NOT NULL CHECK (min_total_evidence_pointers >= 0),
    min_evidence_coverage_rate REAL NOT NULL CHECK (
        min_evidence_coverage_rate >= 0.0
        AND min_evidence_coverage_rate <= 1.0
    ),
    max_evidence_gap_claims INTEGER NOT NULL CHECK (max_evidence_gap_claims >= 0),
    min_confidence_score REAL CHECK (
        min_confidence_score IS NULL
        OR (
            min_confidence_score >= 0.0
            AND min_confidence_score <= 1.0
        )
    ),
    source_audit_run_id TEXT REFERENCES ecr_audit_runs(id) ON DELETE SET NULL,
    created_from_reviewer_outcomes_json TEXT,
    notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    activated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (is_active = 1 AND activated_at IS NOT NULL)
        OR (is_active = 0)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_confidence_calibration_single_active
    ON confidence_calibration_policies (is_active)
    WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_confidence_calibration_created_at
    ON confidence_calibration_policies (created_at DESC, version DESC);

INSERT INTO confidence_calibration_policies (
    version,
    min_claim_count,
    min_total_evidence_pointers,
    min_evidence_coverage_rate,
    max_evidence_gap_claims,
    min_confidence_score,
    source_audit_run_id,
    created_from_reviewer_outcomes_json,
    notes,
    is_active,
    activated_at
)
SELECT
    'st015-calibration-policy-v1-default',
    1,
    1,
    0.75,
    0,
    NULL,
    NULL,
    json('{"seed":"default"}'),
    'Default ST-015 calibration policy; preserves MVP behavior until changed.',
    1,
    CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1
    FROM confidence_calibration_policies
    WHERE version = 'st015-calibration-policy-v1-default'
);

UPDATE summary_publications
SET calibration_policy_version = COALESCE(
    NULLIF(trim(calibration_policy_version), ''),
    'st015-calibration-policy-v1-default'
)
WHERE calibration_policy_version IS NULL
   OR trim(calibration_policy_version) = '';
