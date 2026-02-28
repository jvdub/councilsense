PRAGMA foreign_keys = OFF;

CREATE TABLE notification_outbox_new (
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
            'dlq',
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

INSERT INTO notification_outbox_new (
    id,
    user_id,
    meeting_id,
    city_id,
    notification_type,
    dedupe_key,
    payload_json,
    status,
    attempt_count,
    max_attempts,
    next_retry_at,
    last_attempt_at,
    error_code,
    provider_response_summary,
    subscription_id,
    sent_at,
    created_at,
    updated_at
)
SELECT
    id,
    user_id,
    meeting_id,
    city_id,
    notification_type,
    dedupe_key,
    payload_json,
    status,
    attempt_count,
    max_attempts,
    next_retry_at,
    last_attempt_at,
    error_code,
    provider_response_summary,
    subscription_id,
    sent_at,
    created_at,
    updated_at
FROM notification_outbox;

DROP TABLE notification_outbox;
ALTER TABLE notification_outbox_new RENAME TO notification_outbox;

CREATE INDEX idx_notification_outbox_status_next_retry
    ON notification_outbox (status, next_retry_at);

CREATE INDEX idx_notification_outbox_city_meeting
    ON notification_outbox (city_id, meeting_id);

CREATE INDEX idx_notification_outbox_user_created
    ON notification_outbox (user_id, created_at DESC);

CREATE TABLE notification_delivery_dlq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outbox_id TEXT NOT NULL UNIQUE REFERENCES notification_outbox(id) ON DELETE CASCADE,
    notification_id TEXT NOT NULL CHECK (length(trim(notification_id)) > 0),
    message_id TEXT NOT NULL CHECK (length(trim(message_id)) > 0),
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    source_id TEXT,
    run_id TEXT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL CHECK (length(trim(user_id)) > 0),
    notification_type TEXT NOT NULL CHECK (length(trim(notification_type)) > 0),
    failure_classification TEXT NOT NULL CHECK (
        failure_classification IN ('transient', 'permanent', 'unknown')
    ),
    failure_reason_code TEXT,
    failure_reason_summary TEXT,
    terminal_attempt_number INTEGER NOT NULL CHECK (terminal_attempt_number > 0),
    terminal_attempted_at TEXT NOT NULL,
    terminal_transitioned_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notification_delivery_dlq_city
    ON notification_delivery_dlq (city_id, terminal_transitioned_at DESC);

CREATE INDEX idx_notification_delivery_dlq_source
    ON notification_delivery_dlq (source_id, terminal_transitioned_at DESC);

CREATE INDEX idx_notification_delivery_dlq_run
    ON notification_delivery_dlq (run_id, terminal_transitioned_at DESC);

CREATE INDEX idx_notification_delivery_dlq_message
    ON notification_delivery_dlq (message_id, terminal_transitioned_at DESC);

PRAGMA foreign_keys = ON;
