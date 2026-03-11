ALTER TABLE meeting_processing_requests
    ADD COLUMN processing_run_id TEXT REFERENCES processing_runs(id) ON DELETE SET NULL;

ALTER TABLE meeting_processing_requests
    ADD COLUMN processing_stage_outcome_id TEXT REFERENCES processing_stage_outcomes(id) ON DELETE SET NULL;

ALTER TABLE meeting_processing_requests
    ADD COLUMN work_dedupe_key TEXT;

ALTER TABLE meeting_processing_requests
    ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number > 0);

ALTER TABLE meeting_processing_requests
    ADD COLUMN reopened_from_request_id TEXT REFERENCES meeting_processing_requests(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_meeting_processing_requests_requested_by_status_created
    ON meeting_processing_requests (requested_by, status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_meeting_processing_requests_run_status_created
    ON meeting_processing_requests (processing_run_id, status, created_at DESC, id DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_meeting_processing_requests_active_work_dedupe
    ON meeting_processing_requests (work_dedupe_key)
    WHERE work_dedupe_key IS NOT NULL
      AND status IN ('requested', 'accepted', 'processing');