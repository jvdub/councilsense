ALTER TABLE notification_delivery_dlq
    ADD COLUMN replayed_at TEXT;

ALTER TABLE notification_delivery_dlq
    ADD COLUMN replayed_by TEXT;

ALTER TABLE notification_delivery_dlq
    ADD COLUMN replay_idempotency_key TEXT;

ALTER TABLE notification_delivery_dlq
    ADD COLUMN replay_outbox_id TEXT REFERENCES notification_outbox(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX idx_notification_delivery_dlq_replay_idempotency
    ON notification_delivery_dlq (replay_idempotency_key)
    WHERE replay_idempotency_key IS NOT NULL;

CREATE UNIQUE INDEX idx_notification_delivery_dlq_replay_outbox
    ON notification_delivery_dlq (replay_outbox_id)
    WHERE replay_outbox_id IS NOT NULL;

CREATE TABLE notification_dlq_replay_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dlq_id INTEGER NOT NULL REFERENCES notification_delivery_dlq(id) ON DELETE CASCADE,
    source_outbox_id TEXT NOT NULL CHECK (length(trim(source_outbox_id)) > 0),
    replay_outbox_id TEXT REFERENCES notification_outbox(id) ON DELETE SET NULL,
    requeue_correlation_id TEXT NOT NULL UNIQUE CHECK (length(trim(requeue_correlation_id)) > 0),
    replay_idempotency_key TEXT NOT NULL UNIQUE CHECK (length(trim(replay_idempotency_key)) > 0),
    actor_user_id TEXT NOT NULL CHECK (length(trim(actor_user_id)) > 0),
    replay_reason TEXT NOT NULL CHECK (length(trim(replay_reason)) > 0),
    outcome TEXT NOT NULL CHECK (outcome IN ('requeued', 'ineligible', 'duplicate')),
    outcome_detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notification_dlq_replay_audit_dlq_created
    ON notification_dlq_replay_audit (dlq_id, created_at DESC);

CREATE INDEX idx_notification_dlq_replay_audit_source_created
    ON notification_dlq_replay_audit (source_outbox_id, created_at DESC);
