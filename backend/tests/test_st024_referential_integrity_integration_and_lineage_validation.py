from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from councilsense.app.canonical_persistence import EvidenceSpanInput, persist_pipeline_canonical_records
from councilsense.db import (
    CanonicalDocumentArtifactRepository,
    CanonicalDocumentRepository,
    MeetingSummaryRepository,
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


def _sha256_prefixed(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _insert_source(
    connection: sqlite3.Connection,
    *,
    source_id: str,
    source_type: str,
    source_url: str,
) -> None:
    connection.execute(
        """
        INSERT INTO city_sources (
            id,
            city_id,
            source_type,
            source_url,
            parser_name,
            parser_version
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source_id, PILOT_CITY_ID, source_type, source_url, "integration-parser", "2026.03.04"),
    )


def _insert_meeting(connection: sqlite3.Connection, *, meeting_id: str, meeting_uid: str, title: str) -> None:
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, meeting_uid, title),
    )


def test_st024_referential_integrity_and_checksum_lineage_join_consistency(tmp_path: Path) -> None:
    connection = _create_connection()
    meeting_id = "meeting-st024-ri-1"
    _insert_meeting(
        connection,
        meeting_id=meeting_id,
        meeting_uid="uid-st024-ri-1",
        title="ST024 Referential Integrity Integration",
    )

    source_specs = (
        ("src-st024-minutes", "minutes", "https://example.test/st024/minutes.pdf", "Minutes draft   with extra whitespace\n", "Council approved the budget and directed staff to report monthly.", "minutes"),
        ("src-st024-agenda", "agenda", "https://example.test/st024/agenda.pdf", "Agenda packet draft\n", "Agenda item includes traffic signal modernization discussion.", "agenda"),
        ("src-st024-packet", "packet", "https://example.test/st024/packet.pdf", "Packet appendix raw bytes\n", "Packet appendix details project phases and cost assumptions.", "packet"),
    )

    for source_id, source_type, source_url, *_ in source_specs:
        _insert_source(
            connection,
            source_id=source_id,
            source_type=source_type,
            source_url=source_url,
        )

    doc_repository = CanonicalDocumentRepository(connection)
    artifact_repository = CanonicalDocumentArtifactRepository(connection)

    for source_id, _source_type, _source_url, raw_payload, extracted_text, expected_kind in source_specs:
        artifact_path = tmp_path / f"{source_id}.txt"
        artifact_path.write_text(raw_payload, encoding="utf-8")

        expected_raw_checksum = _sha256_prefixed(raw_payload.encode("utf-8"))
        normalized_text = " ".join(extracted_text.split())
        expected_normalized_checksum = _sha256_prefixed(normalized_text.encode("utf-8"))

        result = persist_pipeline_canonical_records(
            connection,
            meeting_id=meeting_id,
            source_id=source_id,
            source_url=None,
            extracted_text=extracted_text,
            extraction_status="processed",
            extraction_confidence=0.94,
            artifact_storage_uri=str(artifact_path),
            evidence_spans=(
                EvidenceSpanInput(
                    stable_section_path=f"{expected_kind}/section/1",
                    line_index=3,
                    start_char_offset=0,
                    end_char_offset=42,
                    source_chunk_id=f"{source_id}-chunk-1",
                    span_text=f"{expected_kind} evidence one",
                ),
                EvidenceSpanInput(
                    stable_section_path=f"{expected_kind}/section/2",
                    line_index=7,
                    start_char_offset=43,
                    end_char_offset=88,
                    source_chunk_id=f"{source_id}-chunk-2",
                    span_text=f"{expected_kind} evidence two",
                ),
            ),
        )

        active_document = doc_repository.get_active_document(meeting_id=meeting_id, document_kind=expected_kind)
        assert active_document is not None
        assert active_document.id == result.canonical_document_id
        assert active_document.source_checksum == expected_raw_checksum

        raw_artifact = artifact_repository.get_artifact_by_checksum(
            canonical_document_id=result.canonical_document_id,
            artifact_kind="raw",
            content_checksum=expected_raw_checksum,
        )
        normalized_artifact = artifact_repository.get_artifact_by_checksum(
            canonical_document_id=result.canonical_document_id,
            artifact_kind="normalized",
            content_checksum=expected_normalized_checksum,
        )
        assert raw_artifact is not None
        assert normalized_artifact is not None
        assert raw_artifact.id == result.raw_artifact_id
        assert normalized_artifact.id == result.normalized_artifact_id

        assert raw_artifact.lineage_parent_artifact_id is None
        assert raw_artifact.lineage_root_checksum == expected_raw_checksum
        assert raw_artifact.lineage_depth == 0

        assert normalized_artifact.lineage_parent_artifact_id == raw_artifact.id
        assert normalized_artifact.lineage_root_checksum == expected_raw_checksum
        assert normalized_artifact.lineage_depth == 1

        lineage_chain = artifact_repository.list_lineage_chain(artifact_id=normalized_artifact.id)
        assert [item.id for item in lineage_chain] == [raw_artifact.id, normalized_artifact.id]
        assert [item.content_checksum for item in lineage_chain] == [expected_raw_checksum, expected_normalized_checksum]

        spans = doc_repository.list_document_spans(
            canonical_document_id=result.canonical_document_id,
            artifact_id=normalized_artifact.id,
        )
        assert len(spans) == 2
        assert all(span.artifact_id == normalized_artifact.id for span in spans)

        second_read_ids = [item.id for item in doc_repository.list_document_spans(
            canonical_document_id=result.canonical_document_id,
            artifact_id=normalized_artifact.id,
        )]
        assert second_read_ids == [item.id for item in spans]

    orphan_artifacts = connection.execute(
        """
        SELECT COUNT(*)
        FROM canonical_document_artifacts a
        LEFT JOIN canonical_documents d ON d.id = a.canonical_document_id
        WHERE d.id IS NULL
        """
    ).fetchone()
    assert orphan_artifacts is not None
    assert int(orphan_artifacts[0]) == 0

    orphan_spans_by_document = connection.execute(
        """
        SELECT COUNT(*)
        FROM canonical_document_spans s
        LEFT JOIN canonical_documents d ON d.id = s.canonical_document_id
        WHERE d.id IS NULL
        """
    ).fetchone()
    assert orphan_spans_by_document is not None
    assert int(orphan_spans_by_document[0]) == 0

    orphan_spans_by_artifact = connection.execute(
        """
        SELECT COUNT(*)
        FROM canonical_document_spans s
        LEFT JOIN canonical_document_artifacts a ON a.id = s.artifact_id
        WHERE s.artifact_id IS NOT NULL
          AND a.id IS NULL
        """
    ).fetchone()
    assert orphan_spans_by_artifact is not None
    assert int(orphan_spans_by_artifact[0]) == 0


def test_st024_rerun_idempotency_and_legacy_record_compatibility_lineage() -> None:
    connection = _create_connection()
    meeting_id = "meeting-st024-ri-2"
    _insert_meeting(
        connection,
        meeting_id=meeting_id,
        meeting_uid="uid-st024-ri-2",
        title="ST024 Legacy Compatibility Meeting",
    )

    summary_repository = MeetingSummaryRepository(connection)
    summary_repository.create_publication(
        publication_id="pub-st024-ri-legacy-1",
        meeting_id=meeting_id,
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        summary_text="Legacy publication row exists before canonical persistence.",
        key_decisions_json='["Adopted implementation schedule"]',
        key_actions_json='["Publish monthly updates"]',
        notable_topics_json='["Transportation"]',
        published_at="2026-03-04T20:00:00Z",
    )

    _insert_source(
        connection,
        source_id="src-st024-ri-minutes",
        source_type="minutes",
        source_url="https://example.test/st024/ri-minutes.pdf",
    )

    extracted_text = "Council adopted implementation schedule and requested monthly updates."
    spans = (
        EvidenceSpanInput(
            stable_section_path="minutes/section/1",
            line_index=1,
            start_char_offset=0,
            end_char_offset=36,
            source_chunk_id="legacy-chunk-1",
            span_text="Council adopted implementation schedule.",
        ),
    )

    first = persist_pipeline_canonical_records(
        connection,
        meeting_id=meeting_id,
        source_id="src-st024-ri-minutes",
        source_url=None,
        extracted_text=extracted_text,
        extraction_status="processed",
        extraction_confidence=0.9,
        artifact_storage_uri=None,
        evidence_spans=spans,
    )
    second = persist_pipeline_canonical_records(
        connection,
        meeting_id=meeting_id,
        source_id="src-st024-ri-minutes",
        source_url=None,
        extracted_text=extracted_text,
        extraction_status="processed",
        extraction_confidence=0.9,
        artifact_storage_uri=None,
        evidence_spans=spans,
    )

    assert second.canonical_document_id == first.canonical_document_id
    assert second.revision_id == first.revision_id
    assert second.revision_number == first.revision_number
    assert second.raw_artifact_id == first.raw_artifact_id
    assert second.normalized_artifact_id == first.normalized_artifact_id

    counts = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM canonical_documents WHERE meeting_id = ?) AS documents_count,
            (
                SELECT COUNT(*)
                FROM canonical_document_artifacts a
                INNER JOIN canonical_documents d ON d.id = a.canonical_document_id
                WHERE d.meeting_id = ?
            ) AS artifacts_count,
            (
                SELECT COUNT(*)
                FROM canonical_document_spans s
                INNER JOIN canonical_documents d ON d.id = s.canonical_document_id
                WHERE d.meeting_id = ?
            ) AS spans_count
        """,
        (meeting_id, meeting_id, meeting_id),
    ).fetchone()
    assert counts is not None
    assert (int(counts[0]), int(counts[1]), int(counts[2])) == (1, 2, 1)

    publication_rows = connection.execute(
        """
        SELECT id, publication_status
        FROM summary_publications
        WHERE meeting_id = ?
        ORDER BY version_no ASC
        """,
        (meeting_id,),
    ).fetchall()
    assert publication_rows == [("pub-st024-ri-legacy-1", "processed")]

    joined = connection.execute(
        """
        SELECT
            d.id,
            d.document_kind,
            a.artifact_kind,
            a.lineage_depth,
            s.id,
            s.source_chunk_id
        FROM canonical_documents d
        INNER JOIN canonical_document_artifacts a ON a.canonical_document_id = d.id
        LEFT JOIN canonical_document_spans s ON s.canonical_document_id = d.id AND s.artifact_id = a.id
        WHERE d.meeting_id = ?
        ORDER BY a.lineage_depth ASC, a.artifact_kind ASC
        """,
        (meeting_id,),
    ).fetchall()

    assert len(joined) == 2
    assert joined[0][2] == "raw"
    assert joined[0][4] is None
    assert joined[1][2] == "normalized"
    assert joined[1][4] is not None
