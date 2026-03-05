from __future__ import annotations

import sqlite3

from councilsense.app.multi_document_compose import assemble_summarize_compose_input
from councilsense.db import (
    CanonicalDocumentRepository,
    DocumentKind,
    PILOT_CITY_ID,
    apply_migrations,
    seed_city_registry,
)


def _create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)
    return connection


def _create_meeting(connection: sqlite3.Connection, *, meeting_id: str) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, f"uid-{meeting_id}", "ST025 Compose Meeting"),
    )


def _insert_document_with_spans(
    connection: sqlite3.Connection,
    *,
    meeting_id: str,
    document_id: str,
    document_kind: DocumentKind,
    revision_id: str,
    revision_number: int,
    is_active_revision: bool,
    extracted_at: str,
    span_texts: tuple[tuple[str, str], ...],
) -> None:
    repository = CanonicalDocumentRepository(connection)
    document = repository.upsert_document_revision(
        canonical_document_id=document_id,
        meeting_id=meeting_id,
        document_kind=document_kind,
        revision_id=revision_id,
        revision_number=revision_number,
        is_active_revision=is_active_revision,
        authority_level=("authoritative" if document_kind == "minutes" else "supplemental"),
        authority_source="minutes_policy_v1",
        authority_note=("minutes are authoritative" if document_kind == "minutes" else "supplemental source"),
        source_document_url=f"https://example.org/{document_kind}/{revision_id}",
        source_checksum=f"sha256:{document_kind}-{revision_id}",
        parser_name="fixture-parser",
        parser_version="st025-v1",
        extraction_status="processed",
        extraction_confidence=0.9,
        extracted_at=extracted_at,
    )
    for index, (stable_section_path, text) in enumerate(span_texts, start=1):
        repository.upsert_document_span(
            canonical_document_span_id=f"span-{document.id}-{index}",
            canonical_document_id=document.id,
            artifact_id=f"artifact-normalized-{document.id}",
            stable_section_path=stable_section_path,
            page_number=None,
            line_index=index,
            start_char_offset=0,
            end_char_offset=len(text),
            parser_name="fixture-parser",
            parser_version="st025-v1",
            source_chunk_id=f"chunk-{index}",
            span_text=text,
            span_text_checksum=f"sha256:{document.id}:{index}",
        )


def test_st025_compose_assembles_canonical_documents_in_deterministic_source_order() -> None:
    connection = _create_connection()
    meeting_id = "meeting-st025-compose-1"
    _create_meeting(connection, meeting_id=meeting_id)

    _insert_document_with_spans(
        connection,
        meeting_id=meeting_id,
        document_id="canon-agenda-r2",
        document_kind="agenda",
        revision_id="agenda-rev-2",
        revision_number=2,
        is_active_revision=True,
        extracted_at="2026-03-04T19:00:00Z",
        span_texts=(
            ("agenda/section/2", "Agenda item B."),
            ("agenda/section/1", "Agenda item A."),
        ),
    )
    _insert_document_with_spans(
        connection,
        meeting_id=meeting_id,
        document_id="canon-minutes-r1",
        document_kind="minutes",
        revision_id="minutes-rev-1",
        revision_number=1,
        is_active_revision=False,
        extracted_at="2026-03-04T18:00:00Z",
        span_texts=(("minutes/section/1", "Old minutes text."),),
    )
    _insert_document_with_spans(
        connection,
        meeting_id=meeting_id,
        document_id="canon-minutes-r2",
        document_kind="minutes",
        revision_id="minutes-rev-2",
        revision_number=2,
        is_active_revision=True,
        extracted_at="2026-03-04T20:00:00Z",
        span_texts=(
            ("minutes/section/2", "Council adopted ordinance 2026-12."),
            ("minutes/section/1", "Public hearing was closed."),
        ),
    )

    first = assemble_summarize_compose_input(
        connection=connection,
        meeting_id=meeting_id,
        fallback_source_type="minutes",
        fallback_text="fallback text should not be used when canonical exists",
    )
    second = assemble_summarize_compose_input(
        connection=connection,
        meeting_id=meeting_id,
        fallback_source_type="minutes",
        fallback_text="fallback text should not be used when canonical exists",
    )

    assert first.source_order == ("minutes", "agenda", "packet")
    assert tuple(source.source_type for source in first.sources) == ("minutes", "agenda", "packet")

    minutes, agenda, packet = first.sources
    assert minutes.source_origin == "canonical"
    assert minutes.revision_id == "minutes-rev-2"
    assert minutes.coverage_status == "present"

    assert agenda.source_origin == "canonical"
    assert agenda.revision_id == "agenda-rev-2"
    assert agenda.coverage_status == "present"

    assert packet.source_origin == "missing"
    assert packet.coverage_status == "missing"

    assert first.source_coverage.statuses == {
        "minutes": "present",
        "agenda": "present",
        "packet": "missing",
    }
    assert first.source_coverage.missing_source_types == ("packet",)
    assert first.source_coverage.available_source_types == ("minutes", "agenda")

    assert first.composed_text.startswith("[minutes]")
    assert "\n\n[agenda]" in first.composed_text

    assert first.composed_text == second.composed_text
    assert first.source_coverage.coverage_checksum == second.source_coverage.coverage_checksum


def test_st025_compose_allows_partial_source_with_fallback_text_when_canonical_missing() -> None:
    connection = _create_connection()
    meeting_id = "meeting-st025-compose-2"
    _create_meeting(connection, meeting_id=meeting_id)

    composed = assemble_summarize_compose_input(
        connection=connection,
        meeting_id=meeting_id,
        fallback_source_type="agenda",
        fallback_text="Planning session includes zoning map review.",
    )

    minutes, agenda, packet = composed.sources
    assert minutes.coverage_status == "missing"
    assert agenda.source_origin == "fallback_extract"
    assert agenda.coverage_status == "partial"
    assert packet.coverage_status == "missing"

    assert composed.composed_text.startswith("[agenda]")
    assert "zoning map review" in composed.composed_text
    assert composed.source_coverage.partial_source_types == ("agenda",)
    assert composed.source_coverage.missing_source_types == ("minutes", "packet")
