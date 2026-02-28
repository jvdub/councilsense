CREATE TABLE IF NOT EXISTS notification_outbox (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL CHECK (length(trim(user_id)) > 0),
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    notification_type TEXT NOT NULL CHECK (notification_type IN ('meeting_published')),
    dedupe_key TEXT NOT NULL UNIQUE CHECK (length(trim(dedupe_key)) > 0),
    payload_json TEXT NOT NULL CHECK (length(trim(payload_json)) > 0),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (
        status IN (
            'queued',
            'sending',
            'sent',
            'failed',
            'suppressed',
            'invalid_subscription',
            'expired_subscription'
        )
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 6 CHECK (max_attempts > 0),
    next_retry_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_attempt_at TEXT,
    error_code TEXT,
    provider_response_summary TEXT,
    subscription_id TEXT,
    sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_status_next_retry
    ON notification_outbox (status, next_retry_at);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_city_meeting
    ON notification_outbox (city_id, meeting_id);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_user_created
    ON notification_outbox (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notification_delivery_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outbox_id TEXT NOT NULL REFERENCES notification_outbox(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    outcome TEXT NOT NULL CHECK (
        outcome IN (
            'success',
            'retryable_failure',
            'permanent_failure',
            'suppressed',
            'invalid_subscription',
            'expired_subscription'
        )
    ),
    error_code TEXT,
    provider_response_summary TEXT,
    next_retry_at TEXT,
    attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (outbox_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_notification_delivery_attempts_outbox_attempted
    ON notification_delivery_attempts (outbox_id, attempted_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_delivery_attempts_outcome_attempted
    ON notification_delivery_attempts (outcome, attempted_at DESC);
