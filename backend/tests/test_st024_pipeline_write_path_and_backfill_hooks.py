from __future__ import annotations

import sqlite3
from pathlib import Path

from councilsense.app.canonical_persistence import run_pilot_canonical_backfill
from councilsense.app.local_pipeline import LocalPipelineOrchestrator
from councilsense.db import MeetingSummaryRepository, PILOT_CITY_ID, apply_migrations, seed_city_registry


def _create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)
    return connection


def test_st024_pipeline_write_path_persists_document_artifact_and_span_and_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    connection = _create_connection()

    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", str(artifact_root))

    meeting_id = "meeting-st024-write-1"
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, "uid-st024-write-1", "ST024 Pipeline Write Meeting"),
    )

    city_dir = artifact_root / PILOT_CITY_ID
    city_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = city_dir / "st024-write-1-minutes.txt"
    artifact_path.write_text(
        "Council approved the transportation safety plan and directed staff to publish implementation milestones.",
        encoding="utf-8",
    )

    orchestrator = LocalPipelineOrchestrator(connection)

    first = orchestrator.process_latest(
        run_id="run-st024-write-1",
        city_id=PILOT_CITY_ID,
        meeting_id=meeting_id,
        ingest_stage_metadata=None,
        llm_provider="none",
        ollama_endpoint=None,
        ollama_model=None,
        ollama_timeout_seconds=20.0,
    )
    assert first.status == "processed"

    doc_row = connection.execute(
        """
        SELECT id, document_kind
        FROM canonical_documents
        WHERE meeting_id = ?
        """,
        (meeting_id,),
    ).fetchone()
    assert doc_row is not None
    canonical_document_id = str(doc_row[0])
    assert str(doc_row[1]) == "minutes"

    artifact_rows = connection.execute(
        """
        SELECT id, artifact_kind, lineage_parent_artifact_id
        FROM canonical_document_artifacts
        WHERE canonical_document_id = ?
        ORDER BY artifact_kind ASC, id ASC
        """,
        (canonical_document_id,),
    ).fetchall()
    assert len(artifact_rows) == 2

    raw_row = next(item for item in artifact_rows if str(item[1]) == "raw")
    normalized_row = next(item for item in artifact_rows if str(item[1]) == "normalized")
    assert raw_row[2] is None
    assert str(normalized_row[2]) == str(raw_row[0])

    span_rows = connection.execute(
        """
        SELECT artifact_id
        FROM canonical_document_spans
        WHERE canonical_document_id = ?
        """,
        (canonical_document_id,),
    ).fetchall()
    assert len(span_rows) >= 1
    assert all(str(item[0]) == str(normalized_row[0]) for item in span_rows)

    counts_before_rerun = (
        connection.execute("SELECT COUNT(*) FROM canonical_documents WHERE meeting_id = ?", (meeting_id,)).fetchone()[0],
        connection.execute(
            """
            SELECT COUNT(*)
            FROM canonical_document_artifacts a
            INNER JOIN canonical_documents d ON d.id = a.canonical_document_id
            WHERE d.meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()[0],
        connection.execute(
            """
            SELECT COUNT(*)
            FROM canonical_document_spans s
            INNER JOIN canonical_documents d ON d.id = s.canonical_document_id
            WHERE d.meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()[0],
    )

    second = orchestrator.process_latest(
        run_id="run-st024-write-2",
        city_id=PILOT_CITY_ID,
        meeting_id=meeting_id,
        ingest_stage_metadata=None,
        llm_provider="none",
        ollama_endpoint=None,
        ollama_model=None,
        ollama_timeout_seconds=20.0,
    )
    assert second.status == "processed"

    counts_after_rerun = (
        connection.execute("SELECT COUNT(*) FROM canonical_documents WHERE meeting_id = ?", (meeting_id,)).fetchone()[0],
        connection.execute(
            """
            SELECT COUNT(*)
            FROM canonical_document_artifacts a
            INNER JOIN canonical_documents d ON d.id = a.canonical_document_id
            WHERE d.meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()[0],
        connection.execute(
            """
            SELECT COUNT(*)
            FROM canonical_document_spans s
            INNER JOIN canonical_documents d ON d.id = s.canonical_document_id
            WHERE d.meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()[0],
    )

    assert counts_after_rerun == counts_before_rerun


def test_st024_pilot_backfill_hook_supports_dry_run_and_idempotent_rerun() -> None:
    connection = _create_connection()

    meeting_id = "meeting-st024-backfill-1"
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, PILOT_CITY_ID, "uid-st024-backfill-1", "ST024 Backfill Meeting"),
    )

    summary_repository = MeetingSummaryRepository(connection)
    summary_repository.create_publication(
        publication_id="pub-st024-backfill-1",
        meeting_id=meeting_id,
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        summary_text="Council approved the safety plan and asked staff to report quarterly progress.",
        key_decisions_json='["Approved safety plan"]',
        key_actions_json='["Quarterly progress reporting"]',
        notable_topics_json='["Transportation"]',
        published_at="2026-03-04T20:00:00Z",
    )
    summary_repository.add_claim(
        claim_id="claim-st024-backfill-1",
        publication_id="pub-st024-backfill-1",
        claim_order=1,
        claim_text="Council approved the safety plan.",
    )
    summary_repository.add_claim_evidence_pointer(
        pointer_id="ptr-st024-backfill-1",
        claim_id="claim-st024-backfill-1",
        artifact_id="artifact-local:st024-backfill-1.txt",
        section_ref="artifact.html.sentence.1",
        char_start=0,
        char_end=35,
        excerpt="Council approved the safety plan.",
    )

    dry_run = run_pilot_canonical_backfill(
        connection,
        city_id=PILOT_CITY_ID,
        start_date=None,
        end_date=None,
        limit=10,
        dry_run=True,
    )
    assert dry_run.scanned_meetings >= 1
    assert dry_run.meetings_with_publications == 1
    assert dry_run.meetings_written == 0
    assert any(item.status == "would_write" for item in dry_run.audits)

    no_rows = connection.execute(
        "SELECT COUNT(*) FROM canonical_documents WHERE meeting_id = ?",
        (meeting_id,),
    ).fetchone()
    assert no_rows is not None
    assert int(no_rows[0]) == 0

    first = run_pilot_canonical_backfill(
        connection,
        city_id=PILOT_CITY_ID,
        start_date=None,
        end_date=None,
        limit=10,
        dry_run=False,
    )
    assert first.meetings_written == 1
    assert any(item.status == "written" for item in first.audits)

    second = run_pilot_canonical_backfill(
        connection,
        city_id=PILOT_CITY_ID,
        start_date=None,
        end_date=None,
        limit=10,
        dry_run=False,
    )
    assert second.meetings_written == 0
    assert any(item.status == "already_current" for item in second.audits)

    document_count = connection.execute(
        "SELECT COUNT(*) FROM canonical_documents WHERE meeting_id = ?",
        (meeting_id,),
    ).fetchone()
    assert document_count is not None
    assert int(document_count[0]) == 1
