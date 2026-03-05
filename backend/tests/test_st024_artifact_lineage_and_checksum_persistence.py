from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from councilsense.db import (
    CanonicalDocumentArtifactRepository,
    CanonicalDocumentRepository,
    DocumentKind,
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


def _create_canonical_document(
    connection: sqlite3.Connection,
    *,
    canonical_document_id: str,
    meeting_id: str,
    document_kind: DocumentKind,
) -> None:
    repository = CanonicalDocumentRepository(connection)
    repository.upsert_document_revision(
        canonical_document_id=canonical_document_id,
        meeting_id=meeting_id,
        document_kind=document_kind,
        revision_id=f"{document_kind}-rev-1",
        revision_number=1,
        is_active_revision=True,
        authority_level="authoritative" if document_kind == "minutes" else "supplemental",
        authority_source="minutes_policy_v1",
        authority_note=None,
        source_document_url=None,
        source_checksum=f"sha256:{document_kind}-r1",
        parser_name="pdf-parser",
        parser_version="2026.03.04",
        extraction_status="processed",
        extraction_confidence=0.9,
        extracted_at="2026-03-04T20:00:00Z",
    )


def test_artifact_rows_link_to_canonical_document_with_fk_enforcement(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO canonical_document_artifacts (
                id,
                canonical_document_id,
                artifact_kind,
                content_checksum,
                lineage_root_checksum,
                lineage_depth
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "artifact-missing-parent",
                "canon-missing",
                "raw",
                "sha256:missing",
                "sha256:missing",
                0,
            ),
        )


def test_artifact_lineage_checksum_and_dedupe_behavior_is_deterministic(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-st024-4", uid="uid-st024-4")
    _create_canonical_document(
        connection,
        canonical_document_id="canon-minutes-r1",
        meeting_id="meeting-st024-4",
        document_kind="minutes",
    )

    repository = CanonicalDocumentArtifactRepository(connection)

    raw = repository.upsert_artifact(
        artifact_id="artifact-raw-r1",
        canonical_document_id="canon-minutes-r1",
        artifact_kind="raw",
        content_checksum="sha256:raw-r1",
        storage_uri="s3://bucket/minutes/raw-r1.pdf",
        lineage_parent_artifact_id=None,
        normalizer_name=None,
        normalizer_version=None,
    )
    duplicate_raw = repository.upsert_artifact(
        artifact_id="artifact-raw-duplicate-id",
        canonical_document_id="canon-minutes-r1",
        artifact_kind="raw",
        content_checksum="sha256:raw-r1",
        storage_uri="s3://bucket/minutes/raw-r1-duplicate.pdf",
        lineage_parent_artifact_id=None,
        normalizer_name=None,
        normalizer_version=None,
    )
    normalized = repository.upsert_artifact(
        artifact_id="artifact-normalized-r1",
        canonical_document_id="canon-minutes-r1",
        artifact_kind="normalized",
        content_checksum="sha256:normalized-r1",
        storage_uri="s3://bucket/minutes/normalized-r1.txt",
        lineage_parent_artifact_id=raw.id,
        normalizer_name="minutes-normalizer",
        normalizer_version="v2026.03.04",
    )

    assert duplicate_raw.id == raw.id
    assert duplicate_raw.storage_uri == "s3://bucket/minutes/raw-r1.pdf"
    assert raw.lineage_root_checksum == "sha256:raw-r1"
    assert raw.lineage_depth == 0

    assert normalized.lineage_parent_artifact_id == raw.id
    assert normalized.lineage_root_checksum == raw.lineage_root_checksum
    assert normalized.lineage_depth == 1

    resolved = repository.get_artifact_by_checksum(
        canonical_document_id="canon-minutes-r1",
        artifact_kind="normalized",
        content_checksum="sha256:normalized-r1",
    )
    assert resolved is not None
    assert resolved.id == normalized.id

    lineage_chain = repository.list_lineage_chain(artifact_id=normalized.id)
    assert [item.id for item in lineage_chain] == [raw.id, normalized.id]


def test_lineage_parent_must_reference_same_canonical_document(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-st024-5", uid="uid-st024-5")

    _create_canonical_document(
        connection,
        canonical_document_id="canon-minutes-r1",
        meeting_id="meeting-st024-5",
        document_kind="minutes",
    )
    _create_canonical_document(
        connection,
        canonical_document_id="canon-agenda-r1",
        meeting_id="meeting-st024-5",
        document_kind="agenda",
    )

    repository = CanonicalDocumentArtifactRepository(connection)
    raw = repository.upsert_artifact(
        artifact_id="artifact-raw-minutes-r1",
        canonical_document_id="canon-minutes-r1",
        artifact_kind="raw",
        content_checksum="sha256:minutes-raw-r1",
        storage_uri="s3://bucket/minutes/raw-r1.pdf",
        lineage_parent_artifact_id=None,
        normalizer_name=None,
        normalizer_version=None,
    )

    with pytest.raises(ValueError, match="same canonical_document_id"):
        repository.upsert_artifact(
            artifact_id="artifact-normalized-agenda-r1",
            canonical_document_id="canon-agenda-r1",
            artifact_kind="normalized",
            content_checksum="sha256:agenda-normalized-r1",
            storage_uri="s3://bucket/agenda/normalized-r1.txt",
            lineage_parent_artifact_id=raw.id,
            normalizer_name="agenda-normalizer",
            normalizer_version="v2026.03.04",
        )
