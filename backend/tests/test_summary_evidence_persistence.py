from __future__ import annotations

import sqlite3

import pytest

from councilsense.db import (
    CanonicalDocumentRepository,
    MeetingSummaryRepository,
    PILOT_CITY_ID,
    ProcessingRunRepository,
    apply_migrations,
    seed_city_registry,
)


@pytest.fixture
def connection() -> sqlite3.Connection:
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


def _create_canonical_document_with_span(
    connection: sqlite3.Connection,
    *,
    meeting_id: str,
    document_id: str,
    span_id: str,
    artifact_id: str,
    document_kind: str,
    stable_section_path: str,
    line_index: int | None,
    start_char_offset: int | None,
    end_char_offset: int | None,
    span_text: str,
) -> None:
    repository = CanonicalDocumentRepository(connection)
    repository.upsert_document_revision(
        canonical_document_id=document_id,
        meeting_id=meeting_id,
        document_kind=document_kind,
        revision_id=f"{document_kind}-rev-1",
        revision_number=1,
        is_active_revision=True,
        authority_level=("authoritative" if document_kind == "minutes" else "supplemental"),
        authority_source="minutes_policy_v1",
        authority_note=None,
        source_document_url=f"https://example.org/{document_kind}/1",
        source_checksum=f"sha256:{document_id}",
        parser_name="test-parser",
        parser_version="st026-test",
        extraction_status="processed",
        extraction_confidence=0.9,
        extracted_at="2026-03-07T07:00:00Z",
    )
    repository.upsert_document_span(
        canonical_document_span_id=span_id,
        canonical_document_id=document_id,
        artifact_id=artifact_id,
        stable_section_path=stable_section_path,
        page_number=None,
        line_index=line_index,
        start_char_offset=start_char_offset,
        end_char_offset=end_char_offset,
        parser_name="test-parser",
        parser_version="st026-test",
        source_chunk_id=f"chunk-{span_id}",
        span_text=span_text,
        span_text_checksum=f"sha256:{span_id}",
    )


def test_summary_publication_persists_required_sections_and_confidence_state(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-1", uid="meeting-uid-1")

    run_repository = ProcessingRunRepository(connection)
    run = run_repository.create_pending_run(
        run_id="run-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T06:00:00Z",
    )
    stage_outcome = run_repository.upsert_stage_outcome(
        outcome_id="outcome-publish-1",
        run_id=run.id,
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-1",
        stage_name="publish",
        status="limited_confidence",
        metadata_json='{"reason":"low evidence"}',
        started_at="2026-02-27T06:00:10Z",
        finished_at="2026-02-27T06:00:20Z",
    )

    repository = MeetingSummaryRepository(connection)
    publication = repository.create_publication(
        publication_id="pub-1",
        meeting_id="meeting-1",
        processing_run_id=run.id,
        publish_stage_outcome_id=stage_outcome.id,
        version_no=1,
        publication_status="limited_confidence",
        confidence_label="limited_confidence",
        summary_text="Summary body",
        key_decisions_json='["Approve contract"]',
        key_actions_json='["Staff to publish final draft"]',
        notable_topics_json='["Budget impacts"]',
        published_at="2026-02-27T06:00:30Z",
    )

    assert publication.publication_status == "limited_confidence"
    assert publication.confidence_label == "limited_confidence"
    assert publication.key_decisions_json == '["Approve contract"]'
    assert publication.key_actions_json == '["Staff to publish final draft"]'
    assert publication.notable_topics_json == '["Budget impacts"]'
    assert publication.processing_run_id == run.id
    assert publication.publish_stage_outcome_id == stage_outcome.id


def test_claim_evidence_pointers_store_artifact_section_offsets_and_excerpt(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-2", uid="meeting-uid-2")
    _create_canonical_document_with_span(
        connection,
        meeting_id="meeting-2",
        document_id="canon-minutes-77",
        span_id="span-minutes-77",
        artifact_id="artifact-minutes-77",
        document_kind="minutes",
        stable_section_path="minutes/section/4",
        line_index=4,
        start_char_offset=412,
        end_char_offset=503,
        span_text="Motion carried unanimously for Resolution 77.",
    )

    repository = MeetingSummaryRepository(connection)
    publication = repository.create_publication(
        publication_id="pub-2",
        meeting_id="meeting-2",
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        summary_text="Processed summary",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-02-27T07:00:30Z",
    )
    claim = repository.add_claim(
        claim_id="claim-2",
        publication_id=publication.id,
        claim_order=1,
        claim_text="The council approved the resolution.",
    )
    pointer = repository.add_claim_evidence_pointer(
        pointer_id="ptr-2",
        claim_id=claim.id,
        artifact_id="artifact-minutes-77",
        section_ref="minutes.section.4",
        char_start=412,
        char_end=503,
        excerpt="Motion carried unanimously for Resolution 77.",
        document_id="canon-minutes-77",
        span_id="span-minutes-77",
        document_kind="minutes",
        section_path="minutes/section/4",
        precision="offset",
        confidence="high",
    )

    assert pointer.artifact_id == "artifact-minutes-77"
    assert pointer.section_ref == "minutes.section.4"
    assert pointer.char_start == 412
    assert pointer.char_end == 503
    assert pointer.excerpt == "Motion carried unanimously for Resolution 77."
    assert pointer.document_id == "canon-minutes-77"
    assert pointer.span_id == "span-minutes-77"
    assert pointer.document_kind == "minutes"
    assert pointer.section_path == "minutes/section/4"
    assert pointer.precision == "offset"
    assert pointer.confidence == "high"

    listed = repository.list_evidence_for_claim(claim_id=claim.id)
    assert listed == (pointer,)


def test_claim_evidence_pointers_allow_additive_file_level_degradation_when_span_precision_is_missing(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-2b", uid="meeting-uid-2b")
    _create_canonical_document_with_span(
        connection,
        meeting_id="meeting-2b",
        document_id="canon-minutes-weak",
        span_id="span-minutes-weak",
        artifact_id="artifact-minutes-weak",
        document_kind="minutes",
        stable_section_path="minutes/page/unknown",
        line_index=None,
        start_char_offset=None,
        end_char_offset=None,
        span_text="The council discussed the permit.",
    )

    repository = MeetingSummaryRepository(connection)
    publication = repository.create_publication(
        publication_id="pub-2b",
        meeting_id="meeting-2b",
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        publication_status="limited_confidence",
        confidence_label="limited_confidence",
        summary_text="Processed summary",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-03-07T07:00:30Z",
    )
    claim = repository.add_claim(
        claim_id="claim-2b",
        publication_id=publication.id,
        claim_order=1,
        claim_text="The council discussed the permit.",
    )

    pointer = repository.add_claim_evidence_pointer(
        pointer_id="ptr-2b",
        claim_id=claim.id,
        artifact_id="artifact-minutes-weak",
        section_ref="minutes.page.unknown",
        char_start=None,
        char_end=None,
        excerpt="The council discussed the permit.",
        document_id="canon-minutes-weak",
        span_id="span-minutes-weak",
        document_kind="minutes",
        section_path="minutes/page/unknown",
        precision="file",
        confidence="low",
    )

    assert pointer.document_id == "canon-minutes-weak"
    assert pointer.span_id == "span-minutes-weak"
    assert pointer.section_path == "minutes/page/unknown"
    assert pointer.precision == "file"
    assert pointer.confidence == "low"


def test_existing_runs_and_stage_outcomes_remain_queryable_after_migration(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    run_repository = ProcessingRunRepository(connection)
    run = run_repository.create_pending_run(
        run_id="run-compat",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T08:00:00Z",
    )
    run_repository.upsert_stage_outcome(
        outcome_id="outcome-compat",
        run_id=run.id,
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-compat",
        stage_name="summarize",
        status="processed",
        metadata_json='{"score":0.88}',
        started_at="2026-02-27T08:00:10Z",
        finished_at="2026-02-27T08:00:20Z",
    )

    outcomes = run_repository.list_stage_outcomes_for_run_city(run_id=run.id, city_id=PILOT_CITY_ID)
    assert len(outcomes) == 1
    assert outcomes[0].status == "processed"
    assert outcomes[0].stage_name == "summarize"


def test_published_provenance_records_are_append_only(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-append-only", uid="meeting-uid-append-only")

    repository = MeetingSummaryRepository(connection)
    publication = repository.create_publication(
        publication_id="pub-append-only",
        meeting_id="meeting-append-only",
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        summary_text="Original summary",
        key_decisions_json='["Approve resolution"]',
        key_actions_json='["Staff to publish memo"]',
        notable_topics_json='["Housing"]',
        published_at="2026-02-27T16:00:30Z",
    )
    claim = repository.add_claim(
        claim_id="claim-append-only",
        publication_id=publication.id,
        claim_order=1,
        claim_text="Council approved the housing resolution.",
    )
    pointer = repository.add_claim_evidence_pointer(
        pointer_id="ptr-append-only",
        claim_id=claim.id,
        artifact_id="artifact-housing-1",
        section_ref="minutes.section.6",
        char_start=100,
        char_end=160,
        excerpt="Council voted 6-1 in favor of the housing resolution.",
    )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            "UPDATE summary_publications SET summary_text = ? WHERE id = ?",
            ("Mutated summary", publication.id),
        )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            "DELETE FROM publication_claims WHERE id = ?",
            (claim.id,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            "UPDATE claim_evidence_pointers SET excerpt = ? WHERE id = ?",
            ("Mutated excerpt", pointer.id),
        )