from __future__ import annotations

import sqlite3

import pytest

from councilsense.app.pipeline_contracts import (
    consume_extract_payload,
    consume_ingest_payload,
    consume_summarize_payload,
    handoff_extract_to_summarize,
    handoff_ingest_to_extract,
    produce_ingest_payload,
)
from councilsense.app.summarization import (
    EMPTY_SUMMARY_TEXT,
    SummarizationOutput,
    persist_summarization_output,
)
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


def test_contract_is_stable_and_empty_safe_for_sparse_input() -> None:
    output = SummarizationOutput.from_payload(
        {
            "summary": "   ",
            "key_decisions": [" ", "Approve final budget"],
            "key_actions": None,
            "notable_topics": ["Road repair timeline", ""],
        }
    )

    assert output.summary == EMPTY_SUMMARY_TEXT
    assert output.key_decisions == ("Approve final budget",)
    assert output.key_actions == ()
    assert output.notable_topics == ("Road repair timeline",)
    assert output.to_payload() == {
        "contract_version": "st-005-v1",
        "summary": EMPTY_SUMMARY_TEXT,
        "key_decisions": ["Approve final budget"],
        "key_actions": [],
        "notable_topics": ["Road repair timeline"],
    }


def test_contract_output_persists_required_sections_to_publication_record(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-contract-1", uid="meeting-contract-uid-1")

    run_repository = ProcessingRunRepository(connection)
    run = run_repository.create_pending_run(
        run_id="run-contract-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T11:00:00Z",
    )
    publish_outcome = run_repository.upsert_stage_outcome(
        outcome_id="outcome-contract-publish-1",
        run_id=run.id,
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-contract-1",
        stage_name="publish",
        status="processed",
        metadata_json='{"source":"summarizer"}',
        started_at="2026-02-27T11:00:10Z",
        finished_at="2026-02-27T11:00:20Z",
    )

    output = SummarizationOutput.from_sections(
        summary="Council approved the transportation package.",
        key_decisions=["Approved transportation package"],
        key_actions=["Staff to publish implementation timeline"],
        notable_topics=["Funding allocation", "Project sequencing"],
    )

    publication = persist_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-contract-1",
        meeting_id="meeting-contract-1",
        processing_run_id=run.id,
        publish_stage_outcome_id=publish_outcome.id,
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        output=output,
        published_at="2026-02-27T11:00:30Z",
    )

    assert publication.summary_text == "Council approved the transportation package."
    assert publication.key_decisions_json == '["Approved transportation package"]'
    assert publication.key_actions_json == '["Staff to publish implementation timeline"]'
    assert publication.notable_topics_json == '["Funding allocation","Project sequencing"]'
    assert publication.processing_run_id == run.id
    assert publication.publish_stage_outcome_id == publish_outcome.id


def test_end_to_end_processing_run_persists_summarization_sections(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-contract-2", uid="meeting-contract-uid-2")

    run_repository = ProcessingRunRepository(connection)
    run = run_repository.create_pending_run(
        run_id="run-contract-2",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T12:00:00Z",
    )
    publish_outcome = run_repository.upsert_stage_outcome(
        outcome_id="outcome-contract-publish-2",
        run_id=run.id,
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-contract-2",
        stage_name="publish",
        status="processed",
        metadata_json='{"pipeline":"e2e"}',
        started_at="2026-02-27T12:00:10Z",
        finished_at="2026-02-27T12:00:20Z",
    )

    ingest = consume_ingest_payload(
        produce_ingest_payload(
            run_id=run.id,
            city_id=PILOT_CITY_ID,
            meeting_id="meeting-contract-2",
            source_id="source-city-feed",
        )
    )
    extract = consume_extract_payload(
        handoff_ingest_to_extract(
            ingest,
            raw_artifact_uri="s3://raw/meeting-contract-2.json",
        ).to_payload()
    )
    summarize = consume_summarize_payload(
        handoff_extract_to_summarize(
            extract,
            extracted_text_uri="s3://extract/meeting-contract-2.txt",
        ).to_payload()
    )

    output = SummarizationOutput.from_sections(
        summary=f"Summary for {summarize.meeting_id}",
        key_decisions=["Adopted annual budget"],
        key_actions=["City manager to issue implementation memo"],
        notable_topics=["Transportation", "Public safety"],
    )

    publication = persist_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-contract-2",
        meeting_id=summarize.meeting_id,
        processing_run_id=summarize.run_id,
        publish_stage_outcome_id=publish_outcome.id,
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        output=output,
        published_at="2026-02-27T12:00:30Z",
    )

    assert publication.summary_text == "Summary for meeting-contract-2"
    assert publication.key_decisions_json == '["Adopted annual budget"]'
    assert publication.key_actions_json == '["City manager to issue implementation memo"]'
    assert publication.notable_topics_json == '["Transportation","Public safety"]'