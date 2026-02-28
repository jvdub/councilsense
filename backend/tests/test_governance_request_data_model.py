from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from councilsense.db import (
    GOVERNANCE_DELETION_REQUEST_STATUS_MODEL,
    GOVERNANCE_EXPORT_REQUEST_STATUS_MODEL,
    apply_migrations,
)


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def seeded_identity(connection: sqlite3.Connection) -> str:
    apply_migrations(connection)
    user_id = "user-001"
    connection.execute(
        "INSERT INTO governance_user_identities (user_id) VALUES (?)",
        (user_id,),
    )
    return user_id


def test_governance_status_models_define_deterministic_lifecycle_transitions() -> None:
    assert GOVERNANCE_EXPORT_REQUEST_STATUS_MODEL.can_transition(current="requested", next_status="accepted")
    assert GOVERNANCE_EXPORT_REQUEST_STATUS_MODEL.can_transition(current="processing", next_status="completed")
    assert not GOVERNANCE_EXPORT_REQUEST_STATUS_MODEL.can_transition(current="requested", next_status="completed")

    assert GOVERNANCE_DELETION_REQUEST_STATUS_MODEL.can_transition(current="requested", next_status="rejected")
    assert GOVERNANCE_DELETION_REQUEST_STATUS_MODEL.can_transition(current="failed", next_status="processing")
    assert not GOVERNANCE_DELETION_REQUEST_STATUS_MODEL.can_transition(current="completed", next_status="processing")


def test_export_request_lifecycle_persists_history_and_audit_events(
    connection: sqlite3.Connection,
    seeded_identity: str,
) -> None:
    user_id = seeded_identity

    connection.execute(
        """
        INSERT INTO governance_export_requests (
            id,
            user_id,
            idempotency_key,
            status,
            requested_by,
            scope_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("exp-001", user_id, "idem-exp-001", "requested", user_id, '{"include_profile":true}'),
    )

    connection.execute(
        "UPDATE governance_export_requests SET status = 'accepted' WHERE id = ?",
        ("exp-001",),
    )
    connection.execute(
        "UPDATE governance_export_requests SET status = 'processing' WHERE id = ?",
        ("exp-001",),
    )
    connection.execute(
        """
        UPDATE governance_export_requests
        SET status = 'completed', completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        ("exp-001",),
    )

    statuses = connection.execute(
        """
        SELECT to_status
        FROM governance_export_request_status_history
        WHERE request_id = ?
        ORDER BY id ASC
        """,
        ("exp-001",),
    ).fetchall()
    assert statuses == [
        ("requested",),
        ("accepted",),
        ("processing",),
        ("completed",),
    ]

    audit_types = connection.execute(
        """
        SELECT event_type
        FROM governance_audit_events
        WHERE entity_type = 'governance_export_request'
          AND entity_id = ?
        ORDER BY id ASC
        """,
        ("exp-001",),
    ).fetchall()
    assert audit_types == [
        ("export_request_created",),
        ("export_request_status_changed",),
        ("export_request_status_changed",),
        ("export_request_status_changed",),
    ]


def test_invalid_transition_and_duplicate_idempotency_are_rejected(
    connection: sqlite3.Connection,
    seeded_identity: str,
) -> None:
    user_id = seeded_identity

    connection.execute(
        """
        INSERT INTO governance_export_requests (
            id,
            user_id,
            idempotency_key,
            status,
            requested_by
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        ("exp-002", user_id, "idem-exp-dup", "requested", user_id),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO governance_export_requests (
                id,
                user_id,
                idempotency_key,
                status,
                requested_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("exp-003", user_id, "idem-exp-dup", "requested", user_id),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE governance_export_requests SET status = 'completed' WHERE id = ?",
            ("exp-002",),
        )


def test_deletion_request_enforces_identity_fk_and_due_at_policy(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO governance_deletion_requests (
                id,
                user_id,
                idempotency_key,
                mode,
                status,
                requested_by
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("del-001", "missing-user", "idem-del-001", "anonymize", "requested", "missing-user"),
        )

    connection.execute(
        "INSERT INTO governance_user_identities (user_id) VALUES (?)",
        ("user-002",),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO governance_deletion_requests (
                id,
                user_id,
                idempotency_key,
                mode,
                status,
                requested_by
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("del-002", "user-002", "idem-del-002", "delete", "accepted", "user-002"),
        )


def test_retention_policies_and_audit_history_are_append_only(
    connection: sqlite3.Connection,
    seeded_identity: str,
) -> None:
    connection.execute(
        """
        INSERT INTO governance_retention_policies (
            id,
            policy_name,
            applies_to,
            retention_days,
            effective_from,
            config_json,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ret-001",
            "default-retention",
            "all",
            730,
            "2026-02-28T00:00:00+00:00",
            '{"config_key":"GOVERNANCE_RETENTION_DAYS"}',
            seeded_identity,
        ),
    )
    connection.execute(
        """
        INSERT INTO governance_retention_policies (
            id,
            policy_name,
            applies_to,
            retention_days,
            effective_from,
            config_json,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "ret-002",
            "default-retention",
            "all",
            365,
            "2028-01-01T00:00:00+00:00",
            '{"config_key":"GOVERNANCE_RETENTION_DAYS","reason":"legal_override"}',
            seeded_identity,
        ),
    )

    policy_count = connection.execute(
        "SELECT COUNT(*) FROM governance_retention_policies WHERE policy_name = 'default-retention'",
    ).fetchone()
    assert policy_count == (2,)

    connection.execute(
        """
        INSERT INTO governance_export_requests (
            id,
            user_id,
            idempotency_key,
            status,
            requested_by
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        ("exp-immut", seeded_identity, "idem-exp-immut", "requested", seeded_identity),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE governance_export_request_status_history SET reason = 'edited' WHERE request_id = ?",
            ("exp-immut",),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "DELETE FROM governance_audit_events WHERE entity_id = ?",
            ("exp-immut",),
        )
