CREATE TABLE IF NOT EXISTS quality_ops_weekly_reports (
    id TEXT PRIMARY KEY,
    audit_week_start_utc TEXT NOT NULL UNIQUE REFERENCES ecr_audit_report_artifacts(audit_week_start_utc) ON DELETE CASCADE,
    audit_week_end_utc TEXT NOT NULL,
    generated_at_utc TEXT NOT NULL,
    source_report_artifact_uri TEXT NOT NULL CHECK (length(trim(source_report_artifact_uri)) > 0),
    ecr REAL NOT NULL CHECK (ecr >= 0.0 AND ecr <= 1.0),
    ecr_target REAL NOT NULL CHECK (ecr_target >= 0.0 AND ecr_target <= 1.0),
    target_attained INTEGER NOT NULL CHECK (target_attained IN (0, 1)),
    target_status TEXT NOT NULL CHECK (target_status IN ('met', 'below_target')),
    low_confidence_labeling_rate REAL NOT NULL CHECK (
        low_confidence_labeling_rate >= 0.0
        AND low_confidence_labeling_rate <= 1.0
    ),
    reviewer_queue_item_count INTEGER NOT NULL CHECK (reviewer_queue_item_count >= 0),
    reviewer_queue_resolved_count INTEGER NOT NULL CHECK (
        reviewer_queue_resolved_count >= 0
        AND reviewer_queue_resolved_count <= reviewer_queue_item_count
    ),
    reviewer_queue_closure_rate REAL NOT NULL CHECK (
        reviewer_queue_closure_rate >= 0.0
        AND reviewer_queue_closure_rate <= 1.0
    ),
    reviewer_backlog_open_count INTEGER NOT NULL CHECK (reviewer_backlog_open_count >= 0),
    reviewer_backlog_in_progress_count INTEGER NOT NULL CHECK (reviewer_backlog_in_progress_count >= 0),
    reviewer_outcome_counts_json TEXT NOT NULL CHECK (length(trim(reviewer_outcome_counts_json)) > 0),
    calibration_policy_version TEXT,
    escalation_owner_role TEXT,
    escalation_triggered_at_utc TEXT,
    summary_json TEXT NOT NULL CHECK (length(trim(summary_json)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (target_attained = 1 AND escalation_triggered_at_utc IS NULL AND escalation_owner_role IS NULL)
        OR (target_attained = 0 AND escalation_triggered_at_utc IS NOT NULL AND escalation_owner_role IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_quality_ops_weekly_reports_week
    ON quality_ops_weekly_reports (audit_week_start_utc DESC);

CREATE INDEX IF NOT EXISTS idx_quality_ops_weekly_reports_target_status
    ON quality_ops_weekly_reports (target_status, audit_week_start_utc DESC);