CREATE TABLE IF NOT EXISTS reviewer_queue_items (
    id TEXT PRIMARY KEY,
    audit_run_id TEXT NOT NULL REFERENCES ecr_audit_runs(id) ON DELETE CASCADE,
    audit_week_start_utc TEXT NOT NULL,
    publication_id TEXT NOT NULL REFERENCES summary_publications(id) ON DELETE CASCADE,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source_id TEXT,
    processing_run_id TEXT REFERENCES processing_runs(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved')),
    reason_codes_json TEXT NOT NULL CHECK (length(trim(reason_codes_json)) > 0),
    claim_count INTEGER NOT NULL CHECK (claim_count >= 0),
    claims_with_evidence_count INTEGER NOT NULL CHECK (
        claims_with_evidence_count >= 0
        AND claims_with_evidence_count <= claim_count
    ),
    publication_status TEXT NOT NULL CHECK (publication_status IN ('processed', 'limited_confidence')),
    confidence_label TEXT NOT NULL CHECK (confidence_label IN ('high', 'medium', 'low', 'limited_confidence')),
    queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    first_in_progress_at TEXT,
    resolved_at TEXT,
    last_status_changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    outcome_code TEXT,
    recommended_action TEXT,
    outcome_notes TEXT,
    last_reviewed_by TEXT,
    last_reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(audit_run_id, publication_id),
    CHECK (
        outcome_code IS NULL
        OR outcome_code IN ('confirmed_issue', 'false_positive', 'requires_reprocess', 'policy_adjustment_recommended')
    ),
    CHECK (
        recommended_action IS NULL
        OR recommended_action IN ('none', 'rerun_pipeline', 'escalate_calibration', 'open_bug')
    ),
    CHECK (
        (status = 'resolved' AND resolved_at IS NOT NULL)
        OR (status IN ('open', 'in_progress') AND resolved_at IS NULL)
    ),
    CHECK (
        (status = 'resolved' AND outcome_code IS NOT NULL)
        OR (status IN ('open', 'in_progress') AND outcome_code IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_reviewer_queue_items_status_age
    ON reviewer_queue_items (status, queued_at ASC);

CREATE INDEX IF NOT EXISTS idx_reviewer_queue_items_audit_week
    ON reviewer_queue_items (audit_week_start_utc DESC, status ASC);

CREATE TABLE IF NOT EXISTS reviewer_queue_events (
    id TEXT PRIMARY KEY,
    queue_item_id TEXT NOT NULL REFERENCES reviewer_queue_items(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('enqueued', 'status_transition', 'outcome_captured')),
    reason_codes_json TEXT,
    from_status TEXT CHECK (from_status IN ('open', 'in_progress', 'resolved')),
    to_status TEXT CHECK (to_status IN ('open', 'in_progress', 'resolved')),
    outcome_code TEXT CHECK (
        outcome_code IS NULL
        OR outcome_code IN ('confirmed_issue', 'false_positive', 'requires_reprocess', 'policy_adjustment_recommended')
    ),
    recommended_action TEXT CHECK (
        recommended_action IS NULL
        OR recommended_action IN ('none', 'rerun_pipeline', 'escalate_calibration', 'open_bug')
    ),
    actor_user_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reviewer_queue_events_item_created
    ON reviewer_queue_events (queue_item_id, created_at ASC, id ASC);
