CREATE TABLE IF NOT EXISTS governance_user_identities (
    user_id TEXT PRIMARY KEY CHECK (length(trim(user_id)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS governance_retention_policies (
    id TEXT PRIMARY KEY,
    policy_name TEXT NOT NULL CHECK (length(trim(policy_name)) > 0),
    applies_to TEXT NOT NULL CHECK (
        applies_to IN (
            'raw_artifacts',
            'generated_outputs',
            'notification_history',
            'export_artifacts',
            'all'
        )
    ),
    retention_days INTEGER NOT NULL CHECK (retention_days > 0),
    effective_from TEXT NOT NULL,
    effective_until TEXT,
    config_json TEXT NOT NULL DEFAULT '{}' CHECK (length(trim(config_json)) > 0),
    created_by TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (effective_until IS NULL OR effective_until > effective_from),
    UNIQUE (policy_name, applies_to, effective_from)
);

CREATE INDEX IF NOT EXISTS idx_governance_retention_policies_effective
    ON governance_retention_policies (applies_to, effective_from DESC);

CREATE TABLE IF NOT EXISTS governance_export_requests (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES governance_user_identities(user_id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL UNIQUE CHECK (length(trim(idempotency_key)) > 0),
    status TEXT NOT NULL CHECK (status IN ('requested', 'accepted', 'processing', 'completed', 'failed', 'cancelled')),
    requested_by TEXT NOT NULL CHECK (length(trim(requested_by)) > 0),
    scope_json TEXT NOT NULL DEFAULT '{}' CHECK (length(trim(scope_json)) > 0),
    artifact_uri TEXT,
    error_code TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((status = 'completed' AND completed_at IS NOT NULL) OR (status != 'completed'))
);

CREATE INDEX IF NOT EXISTS idx_governance_export_requests_user_status
    ON governance_export_requests (user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS governance_export_request_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES governance_export_requests(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL CHECK (to_status IN ('requested', 'accepted', 'processing', 'completed', 'failed', 'cancelled')),
    changed_by TEXT NOT NULL CHECK (length(trim(changed_by)) > 0),
    reason TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (length(trim(metadata_json)) > 0),
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governance_export_status_history_request_changed
    ON governance_export_request_status_history (request_id, changed_at ASC, id ASC);

CREATE TABLE IF NOT EXISTS governance_deletion_requests (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES governance_user_identities(user_id) ON DELETE RESTRICT,
    idempotency_key TEXT NOT NULL UNIQUE CHECK (length(trim(idempotency_key)) > 0),
    mode TEXT NOT NULL CHECK (mode IN ('delete', 'anonymize')),
    status TEXT NOT NULL CHECK (status IN ('requested', 'accepted', 'processing', 'completed', 'failed', 'rejected', 'cancelled')),
    requested_by TEXT NOT NULL CHECK (length(trim(requested_by)) > 0),
    reason_code TEXT,
    due_at TEXT,
    completed_at TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (status IN ('accepted', 'processing', 'completed', 'failed') AND due_at IS NOT NULL)
        OR (status IN ('requested', 'rejected', 'cancelled'))
    ),
    CHECK ((status = 'completed' AND completed_at IS NOT NULL) OR (status != 'completed'))
);

CREATE INDEX IF NOT EXISTS idx_governance_deletion_requests_user_status
    ON governance_deletion_requests (user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS governance_deletion_request_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES governance_deletion_requests(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL CHECK (to_status IN ('requested', 'accepted', 'processing', 'completed', 'failed', 'rejected', 'cancelled')),
    changed_by TEXT NOT NULL CHECK (length(trim(changed_by)) > 0),
    reason TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (length(trim(metadata_json)) > 0),
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governance_deletion_status_history_request_changed
    ON governance_deletion_request_status_history (request_id, changed_at ASC, id ASC);

CREATE TABLE IF NOT EXISTS governance_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'export_request_created',
            'export_request_status_changed',
            'deletion_request_created',
            'deletion_request_status_changed',
            'retention_policy_created'
        )
    ),
    entity_type TEXT NOT NULL CHECK (
        entity_type IN (
            'governance_export_request',
            'governance_deletion_request',
            'governance_retention_policy'
        )
    ),
    entity_id TEXT NOT NULL CHECK (length(trim(entity_id)) > 0),
    actor_user_id TEXT NOT NULL CHECK (length(trim(actor_user_id)) > 0),
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (length(trim(metadata_json)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_governance_audit_events_entity
    ON governance_audit_events (entity_type, entity_id, created_at ASC, id ASC);

CREATE TRIGGER IF NOT EXISTS trg_governance_export_request_insert_history
AFTER INSERT ON governance_export_requests
BEGIN
    INSERT INTO governance_export_request_status_history (
        request_id,
        from_status,
        to_status,
        changed_by,
        reason,
        metadata_json
    )
    VALUES (
        NEW.id,
        NULL,
        NEW.status,
        NEW.requested_by,
        'request_created',
        '{}'
    );

    INSERT INTO governance_audit_events (
        event_type,
        entity_type,
        entity_id,
        actor_user_id,
        metadata_json
    )
    VALUES (
        'export_request_created',
        'governance_export_request',
        NEW.id,
        NEW.requested_by,
        '{}'
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_export_request_validate_transition
BEFORE UPDATE OF status ON governance_export_requests
FOR EACH ROW
WHEN NOT (
    NEW.status = OLD.status
    OR (OLD.status = 'requested' AND NEW.status IN ('accepted', 'cancelled'))
    OR (OLD.status = 'accepted' AND NEW.status IN ('processing', 'cancelled'))
    OR (OLD.status = 'processing' AND NEW.status IN ('completed', 'failed', 'cancelled'))
    OR (OLD.status = 'failed' AND NEW.status IN ('processing', 'cancelled'))
    OR (OLD.status = 'completed' AND NEW.status = 'completed')
    OR (OLD.status = 'cancelled' AND NEW.status = 'cancelled')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid governance export request status transition');
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_export_request_status_history
AFTER UPDATE OF status ON governance_export_requests
FOR EACH ROW
WHEN NEW.status != OLD.status
BEGIN
    INSERT INTO governance_export_request_status_history (
        request_id,
        from_status,
        to_status,
        changed_by,
        reason,
        metadata_json
    )
    VALUES (
        NEW.id,
        OLD.status,
        NEW.status,
        NEW.requested_by,
        'status_transition',
        '{}'
    );

    INSERT INTO governance_audit_events (
        event_type,
        entity_type,
        entity_id,
        actor_user_id,
        metadata_json
    )
    VALUES (
        'export_request_status_changed',
        'governance_export_request',
        NEW.id,
        NEW.requested_by,
        '{}'
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_deletion_request_insert_history
AFTER INSERT ON governance_deletion_requests
BEGIN
    INSERT INTO governance_deletion_request_status_history (
        request_id,
        from_status,
        to_status,
        changed_by,
        reason,
        metadata_json
    )
    VALUES (
        NEW.id,
        NULL,
        NEW.status,
        NEW.requested_by,
        'request_created',
        '{}'
    );

    INSERT INTO governance_audit_events (
        event_type,
        entity_type,
        entity_id,
        actor_user_id,
        metadata_json
    )
    VALUES (
        'deletion_request_created',
        'governance_deletion_request',
        NEW.id,
        NEW.requested_by,
        '{}'
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_deletion_request_validate_transition
BEFORE UPDATE OF status ON governance_deletion_requests
FOR EACH ROW
WHEN NOT (
    NEW.status = OLD.status
    OR (OLD.status = 'requested' AND NEW.status IN ('accepted', 'rejected', 'cancelled'))
    OR (OLD.status = 'accepted' AND NEW.status IN ('processing', 'cancelled'))
    OR (OLD.status = 'processing' AND NEW.status IN ('completed', 'failed', 'cancelled'))
    OR (OLD.status = 'failed' AND NEW.status IN ('processing', 'cancelled'))
    OR (OLD.status = 'completed' AND NEW.status = 'completed')
    OR (OLD.status = 'rejected' AND NEW.status = 'rejected')
    OR (OLD.status = 'cancelled' AND NEW.status = 'cancelled')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid governance deletion request status transition');
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_deletion_request_status_history
AFTER UPDATE OF status ON governance_deletion_requests
FOR EACH ROW
WHEN NEW.status != OLD.status
BEGIN
    INSERT INTO governance_deletion_request_status_history (
        request_id,
        from_status,
        to_status,
        changed_by,
        reason,
        metadata_json
    )
    VALUES (
        NEW.id,
        OLD.status,
        NEW.status,
        NEW.requested_by,
        'status_transition',
        '{}'
    );

    INSERT INTO governance_audit_events (
        event_type,
        entity_type,
        entity_id,
        actor_user_id,
        metadata_json
    )
    VALUES (
        'deletion_request_status_changed',
        'governance_deletion_request',
        NEW.id,
        NEW.requested_by,
        '{}'
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_retention_policy_audit
AFTER INSERT ON governance_retention_policies
BEGIN
    INSERT INTO governance_audit_events (
        event_type,
        entity_type,
        entity_id,
        actor_user_id,
        metadata_json
    )
    VALUES (
        'retention_policy_created',
        'governance_retention_policy',
        NEW.id,
        NEW.created_by,
        '{}'
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_export_status_history_immutable_update
BEFORE UPDATE ON governance_export_request_status_history
BEGIN
    SELECT RAISE(ABORT, 'governance export status history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_export_status_history_immutable_delete
BEFORE DELETE ON governance_export_request_status_history
BEGIN
    SELECT RAISE(ABORT, 'governance export status history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_deletion_status_history_immutable_update
BEFORE UPDATE ON governance_deletion_request_status_history
BEGIN
    SELECT RAISE(ABORT, 'governance deletion status history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_deletion_status_history_immutable_delete
BEFORE DELETE ON governance_deletion_request_status_history
BEGIN
    SELECT RAISE(ABORT, 'governance deletion status history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_audit_events_immutable_update
BEFORE UPDATE ON governance_audit_events
BEGIN
    SELECT RAISE(ABORT, 'governance audit events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_governance_audit_events_immutable_delete
BEFORE DELETE ON governance_audit_events
BEGIN
    SELECT RAISE(ABORT, 'governance audit events are immutable');
END;
