CREATE TABLE IF NOT EXISTS meeting_processing_requests (
    id TEXT PRIMARY KEY,
    discovered_meeting_id TEXT NOT NULL REFERENCES discovered_meetings(id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    meeting_id TEXT REFERENCES meetings(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('requested', 'accepted', 'processing', 'completed', 'failed', 'cancelled')),
    requested_by TEXT NOT NULL CHECK (length(trim(requested_by)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_meeting_processing_requests_city_status_created
    ON meeting_processing_requests (city_id, status, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_meeting_processing_requests_discovered_created
    ON meeting_processing_requests (discovered_meeting_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_meeting_processing_requests_meeting_status_created
    ON meeting_processing_requests (meeting_id, status, created_at DESC, id DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_meeting_processing_requests_active_discovered
    ON meeting_processing_requests (discovered_meeting_id)
    WHERE status IN ('requested', 'accepted', 'processing');