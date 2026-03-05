from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from councilsense.db import (
    CanonicalDocumentRepository,
    PILOT_CITY_ID,
    apply_migrations,
    seed_city_registry,
)


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _create_meeting(connection: sqlite3.Connection, *, meeting_id: str, uid: str) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, uid, "Council Meeting"),
    )


def test_canonical_document_persists_revision_and_authority_metadata_across_kinds(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-st024-1", uid="uid-st024-1")

    repository = CanonicalDocumentRepository(connection)

    minutes = repository.upsert_document_revision(
        canonical_document_id="canon-minutes-r1",
        meeting_id="meeting-st024-1",
        document_kind="minutes",
        revision_id="minutes-rev-1",
        revision_number=1,
        is_active_revision=True,
        authority_level="authoritative",
        authority_source="minutes_policy_v1",
        authority_note="minutes are authoritative for outcomes",
        source_document_url="https://example.test/minutes-r1.pdf",
        source_checksum="sha256:minutes-r1",
        parser_name="pdf-parser",
        parser_version="2026.03.01",
        extraction_status="processed",
        extraction_confidence=0.97,
        extracted_at="2026-03-04T18:12:00Z",
    )
    agenda = repository.upsert_document_revision(
        canonical_document_id="canon-agenda-r1",
        meeting_id="meeting-st024-1",
        document_kind="agenda",
        revision_id="agenda-rev-1",
        revision_number=1,
        is_active_revision=True,
        authority_level="supplemental",
        authority_source="minutes_policy_v1",
        authority_note="agenda supports planning context",
        source_document_url="https://example.test/agenda-r1.pdf",
        source_checksum="sha256:agenda-r1",
        parser_name="pdf-parser",
        parser_version="2026.03.01",
        extraction_status="processed",
        extraction_confidence=0.91,
        extracted_at="2026-03-04T18:12:00Z",
    )
    packet = repository.upsert_document_revision(
        canonical_document_id="canon-packet-r1",
        meeting_id="meeting-st024-1",
        document_kind="packet",
        revision_id="packet-rev-1",
        revision_number=1,
        is_active_revision=True,
        authority_level="supplemental",
        authority_source="minutes_policy_v1",
        authority_note="packet supports evidence context",
        source_document_url="https://example.test/packet-r1.pdf",
        source_checksum="sha256:packet-r1",
        parser_name="pdf-parser",
        parser_version="2026.03.01",
        extraction_status="limited_confidence",
        extraction_confidence=0.68,
        extracted_at="2026-03-04T18:12:00Z",
    )

    assert minutes.authority_level == "authoritative"
    assert minutes.revision_number == 1
    assert agenda.authority_level == "supplemental"
    assert packet.document_kind == "packet"

    all_rows = repository.list_documents_for_meeting(meeting_id="meeting-st024-1")
    assert len(all_rows) == 3


def test_active_revision_selection_is_deterministic_and_queryable(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-st024-2", uid="uid-st024-2")

    repository = CanonicalDocumentRepository(connection)
    repository.upsert_document_revision(
        canonical_document_id="canon-minutes-r1",
        meeting_id="meeting-st024-2",
        document_kind="minutes",
        revision_id="minutes-rev-1",
        revision_number=1,
        is_active_revision=True,
        authority_level="authoritative",
        authority_source="minutes_policy_v1",
        authority_note=None,
        source_document_url=None,
        source_checksum="sha256:minutes-r1",
        parser_name="html-parser",
        parser_version="2026.03.02",
        extraction_status="processed",
        extraction_confidence=0.82,
        extracted_at="2026-03-04T18:20:00Z",
    )
    repository.upsert_document_revision(
        canonical_document_id="canon-minutes-r2",
        meeting_id="meeting-st024-2",
        document_kind="minutes",
        revision_id="minutes-rev-2",
        revision_number=2,
        is_active_revision=True,
        authority_level="authoritative",
        authority_source="minutes_policy_v1",
        authority_note="revised minutes",
        source_document_url=None,
        source_checksum="sha256:minutes-r2",
        parser_name="html-parser",
        parser_version="2026.03.03",
        extraction_status="processed",
        extraction_confidence=0.89,
        extracted_at="2026-03-04T18:25:00Z",
    )

    active = repository.get_active_document(meeting_id="meeting-st024-2", document_kind="minutes")
    assert active is not None
    assert active.revision_id == "minutes-rev-2"
    assert active.revision_number == 2
    assert active.is_active_revision is True

    rows = connection.execute(
        """
        SELECT revision_id, is_active_revision
        FROM canonical_documents
        WHERE meeting_id = ?
          AND document_kind = 'minutes'
        ORDER BY revision_number ASC
        """,
        ("meeting-st024-2",),
    ).fetchall()
    assert rows == [("minutes-rev-1", 0), ("minutes-rev-2", 1)]


def test_schema_enforces_single_active_revision_per_kind(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-st024-3", uid="uid-st024-3")

    connection.execute(
        """
        INSERT INTO canonical_documents (
            id,
            meeting_id,
            document_kind,
            revision_id,
            revision_number,
            is_active_revision,
            authority_level,
            authority_source,
            parser_name,
            parser_version,
            extraction_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "canon-minutes-r1",
            "meeting-st024-3",
            "minutes",
            "minutes-rev-1",
            1,
            1,
            "authoritative",
            "minutes_policy_v1",
            "pdf-parser",
            "2026.03.01",
            "processed",
        ),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO canonical_documents (
                id,
                meeting_id,
                document_kind,
                revision_id,
                revision_number,
                is_active_revision,
                authority_level,
                authority_source,
                parser_name,
                parser_version,
                extraction_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "canon-minutes-r2",
                "meeting-st024-3",
                "minutes",
                "minutes-rev-2",
                2,
                1,
                "authoritative",
                "minutes_policy_v1",
                "pdf-parser",
                "2026.03.01",
                "processed",
            ),
        )
