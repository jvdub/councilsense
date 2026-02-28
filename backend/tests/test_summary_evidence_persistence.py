from __future__ import annotations

import sqlite3

import pytest

from councilsense.db import (
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
    )

    assert pointer.artifact_id == "artifact-minutes-77"
    assert pointer.section_ref == "minutes.section.4"
    assert pointer.char_start == 412
    assert pointer.char_end == 503
    assert pointer.excerpt == "Motion carried unanimously for Resolution 77."

    listed = repository.list_evidence_for_claim(claim_id=claim.id)
    assert listed == (pointer,)


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