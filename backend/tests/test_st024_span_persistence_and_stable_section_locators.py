from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from councilsense.db import (
    AuthorityLevel,
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


def _upsert_document(
    repository: CanonicalDocumentRepository,
    *,
    canonical_document_id: str,
    meeting_id: str,
    document_kind: DocumentKind,
    authority_level: AuthorityLevel,
) -> None:
    repository.upsert_document_revision(
        canonical_document_id=canonical_document_id,
        meeting_id=meeting_id,
        document_kind=document_kind,
        revision_id=f"{document_kind}-rev-1",
        revision_number=1,
        is_active_revision=True,
        authority_level=authority_level,
        authority_source="minutes_policy_v1",
        authority_note=None,
        source_document_url=None,
        source_checksum=f"sha256:{canonical_document_id}",
        parser_name="parser-core",
        parser_version="2026.03.04",
        extraction_status="processed",
        extraction_confidence=0.92,
        extracted_at="2026-03-04T20:00:00Z",
    )


def test_st024_span_persistence_keeps_stable_path_and_optional_precision_fields(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-st024-span-1", uid="uid-st024-span-1")

    repository = CanonicalDocumentRepository(connection)
    _upsert_document(
        repository,
        canonical_document_id="canon-minutes-r1",
        meeting_id="meeting-st024-span-1",
        document_kind="minutes",
        authority_level="authoritative",
    )
    _upsert_document(
        repository,
        canonical_document_id="canon-agenda-r1",
        meeting_id="meeting-st024-span-1",
        document_kind="agenda",
        authority_level="supplemental",
    )
    _upsert_document(
        repository,
        canonical_document_id="canon-packet-r1",
        meeting_id="meeting-st024-span-1",
        document_kind="packet",
        authority_level="supplemental",
    )

    minutes_span = repository.upsert_document_span(
        canonical_document_span_id="span-minutes-1",
        canonical_document_id="canon-minutes-r1",
        artifact_id="artifact-minutes-r1-normalized",
        stable_section_path="minutes/section-3/decision-1",
        page_number=4,
        line_index=12,
        start_char_offset=181,
        end_char_offset=247,
        parser_name="parser-core",
        parser_version="2026.03.04",
        source_chunk_id="chunk-minutes-3-1",
        span_text="Council voted 6-1 to approve the safety plan.",
        span_text_checksum="sha256:minutes-span-1",
    )
    agenda_span = repository.upsert_document_span(
        canonical_document_span_id="span-agenda-1",
        canonical_document_id="canon-agenda-r1",
        artifact_id="artifact-agenda-r1-normalized",
        stable_section_path="agenda/section-2/item-b",
        page_number=None,
        line_index=None,
        start_char_offset=None,
        end_char_offset=None,
        parser_name="parser-core",
        parser_version="2026.03.04",
        source_chunk_id="chunk-agenda-2-2",
        span_text="Transportation safety plan discussion.",
        span_text_checksum="sha256:agenda-span-1",
    )
    packet_span = repository.upsert_document_span(
        canonical_document_span_id="span-packet-1",
        canonical_document_id="canon-packet-r1",
        artifact_id="artifact-packet-r1-normalized",
        stable_section_path="packet/appendix-a/table-2",
        page_number=21,
        line_index=None,
        start_char_offset=None,
        end_char_offset=None,
        parser_name="parser-core",
        parser_version="2026.03.04",
        source_chunk_id="chunk-packet-a-2",
        span_text="Safety budget table and projected costs.",
        span_text_checksum="sha256:packet-span-1",
    )

    assert minutes_span.canonical_document_id == "canon-minutes-r1"
    assert minutes_span.artifact_id == "artifact-minutes-r1-normalized"
    assert minutes_span.page_number == 4
    assert minutes_span.start_char_offset == 181

    assert agenda_span.canonical_document_id == "canon-agenda-r1"
    assert agenda_span.artifact_id == "artifact-agenda-r1-normalized"
    assert agenda_span.page_number is None
    assert agenda_span.start_char_offset is None

    assert packet_span.canonical_document_id == "canon-packet-r1"
    assert packet_span.artifact_id == "artifact-packet-r1-normalized"
    assert packet_span.page_number == 21
    assert packet_span.start_char_offset is None


def test_st024_span_locator_persistence_is_stable_across_reruns(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-st024-span-2", uid="uid-st024-span-2")

    repository = CanonicalDocumentRepository(connection)
    _upsert_document(
        repository,
        canonical_document_id="canon-minutes-r1",
        meeting_id="meeting-st024-span-2",
        document_kind="minutes",
        authority_level="authoritative",
    )

    first = repository.upsert_document_span(
        canonical_document_span_id="span-minutes-original",
        canonical_document_id="canon-minutes-r1",
        artifact_id="artifact-minutes-r1-normalized",
        stable_section_path="  minutes / section-3 // decision-a  ",
        page_number=3,
        line_index=8,
        start_char_offset=140,
        end_char_offset=196,
        parser_name="parser-core",
        parser_version="2026.03.04",
        source_chunk_id="chunk-old",
        span_text="Original extracted sentence.",
        span_text_checksum="sha256:span-original",
    )
    second = repository.upsert_document_span(
        canonical_document_span_id="span-minutes-rerun-new-id",
        canonical_document_id="canon-minutes-r1",
        artifact_id="artifact-minutes-r1-normalized",
        stable_section_path="minutes/section-3/decision-a",
        page_number=3,
        line_index=8,
        start_char_offset=140,
        end_char_offset=196,
        parser_name="parser-core",
        parser_version="2026.03.04",
        source_chunk_id="chunk-new",
        span_text="Rerun extracted sentence.",
        span_text_checksum="sha256:span-rerun",
    )

    spans = repository.list_document_spans(
        canonical_document_id="canon-minutes-r1",
        artifact_id="artifact-minutes-r1-normalized",
    )

    assert len(spans) == 1
    assert first.id == second.id == "span-minutes-original"
    assert spans[0].stable_section_path == "minutes/section-3/decision-a"
    assert spans[0].source_chunk_id == "chunk-new"
    assert spans[0].span_text_checksum == "sha256:span-rerun"


def test_st024_span_retrieval_order_is_deterministic_for_same_document_and_artifact(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-st024-span-3", uid="uid-st024-span-3")

    repository = CanonicalDocumentRepository(connection)
    _upsert_document(
        repository,
        canonical_document_id="canon-packet-r1",
        meeting_id="meeting-st024-span-3",
        document_kind="packet",
        authority_level="supplemental",
    )

    repository.upsert_document_span(
        canonical_document_span_id="span-zeta",
        canonical_document_id="canon-packet-r1",
        artifact_id="artifact-packet-r1-normalized",
        stable_section_path="packet/appendix-z",
        page_number=None,
        line_index=None,
        start_char_offset=None,
        end_char_offset=None,
        parser_name="parser-core",
        parser_version="2026.03.04",
        source_chunk_id=None,
        span_text=None,
        span_text_checksum=None,
    )
    repository.upsert_document_span(
        canonical_document_span_id="span-alpha-later-page",
        canonical_document_id="canon-packet-r1",
        artifact_id="artifact-packet-r1-normalized",
        stable_section_path="packet/appendix-a",
        page_number=9,
        line_index=0,
        start_char_offset=10,
        end_char_offset=30,
        parser_name="parser-core",
        parser_version="2026.03.04",
        source_chunk_id=None,
        span_text=None,
        span_text_checksum=None,
    )
    repository.upsert_document_span(
        canonical_document_span_id="span-alpha-earlier-page",
        canonical_document_id="canon-packet-r1",
        artifact_id="artifact-packet-r1-normalized",
        stable_section_path="packet/appendix-a",
        page_number=2,
        line_index=2,
        start_char_offset=5,
        end_char_offset=15,
        parser_name="parser-core",
        parser_version="2026.03.04",
        source_chunk_id=None,
        span_text=None,
        span_text_checksum=None,
    )

    first = repository.list_document_spans(
        canonical_document_id="canon-packet-r1",
        artifact_id="artifact-packet-r1-normalized",
    )
    second = repository.list_document_spans(
        canonical_document_id="canon-packet-r1",
        artifact_id="artifact-packet-r1-normalized",
    )

    first_ids = [item.id for item in first]
    second_ids = [item.id for item in second]

    assert first_ids == second_ids
    assert first_ids == ["span-alpha-earlier-page", "span-alpha-later-page", "span-zeta"]
