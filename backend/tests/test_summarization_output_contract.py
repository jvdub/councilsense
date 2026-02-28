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
    ClaimEvidenceValidationError,
    EMPTY_SUMMARY_TEXT,
    QualityGateConfig,
    SummarizationOutput,
    attach_claim_evidence,
    publish_summarization_output,
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
        "claims": [],
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


def test_claim_evidence_records_reject_missing_required_fields() -> None:
    with pytest.raises(ClaimEvidenceValidationError, match="artifact_id is required"):
        SummarizationOutput.from_payload(
            {
                "summary": "Summary",
                "key_decisions": [],
                "key_actions": [],
                "notable_topics": [],
                "claims": [
                    {
                        "claim_text": "The council approved Resolution 77.",
                        "evidence": [
                            {
                                "artifact_id": "",
                                "section_ref": "minutes.section.4",
                                "excerpt": "Motion carried unanimously for Resolution 77.",
                            }
                        ],
                    }
                ],
            }
        )

    with pytest.raises(ClaimEvidenceValidationError, match="section_ref or char_start/char_end is required"):
        SummarizationOutput.from_payload(
            {
                "summary": "Summary",
                "key_decisions": [],
                "key_actions": [],
                "notable_topics": [],
                "claims": [
                    {
                        "claim_text": "The council approved Resolution 77.",
                        "evidence": [
                            {
                                "artifact_id": "artifact-minutes-77",
                                "excerpt": "Motion carried unanimously for Resolution 77.",
                            }
                        ],
                    }
                ],
            }
        )

    with pytest.raises(ClaimEvidenceValidationError, match="excerpt is required"):
        SummarizationOutput.from_payload(
            {
                "summary": "Summary",
                "key_decisions": [],
                "key_actions": [],
                "notable_topics": [],
                "claims": [
                    {
                        "claim_text": "The council approved Resolution 77.",
                        "evidence": [
                            {
                                "artifact_id": "artifact-minutes-77",
                                "section_ref": "minutes.section.4",
                                "excerpt": "   ",
                            }
                        ],
                    }
                ],
            }
        )


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
        claims=(
            SummarizationOutput.from_payload(
                {
                    "summary": "",
                    "key_decisions": [],
                    "key_actions": [],
                    "notable_topics": [],
                    "claims": [
                        {
                            "claim_text": "The council adopted the annual budget.",
                            "evidence": [
                                {
                                    "artifact_id": "artifact-minutes-annual-budget",
                                    "section_ref": "minutes.section.8",
                                    "char_start": 124,
                                    "char_end": 198,
                                    "excerpt": "Council vote passed 5-2 to adopt the annual budget.",
                                }
                            ],
                        }
                    ],
                }
            ).claims[0],
        ),
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
    claims = MeetingSummaryRepository(connection).list_claims_for_publication(publication_id=publication.id)
    evidence = MeetingSummaryRepository(connection).list_evidence_for_claim(claim_id=claims[0].id)
    assert len(claims) == 1
    assert claims[0].claim_text == "The council adopted the annual budget."
    assert len(evidence) == 1
    assert evidence[0].artifact_id == "artifact-minutes-annual-budget"


def test_attach_claim_evidence_marks_gap_when_claim_has_no_evidence(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-contract-3", uid="meeting-contract-uid-3")

    repository = MeetingSummaryRepository(connection)
    publication = repository.create_publication(
        publication_id="pub-contract-3",
        meeting_id="meeting-contract-3",
        processing_run_id=None,
        publish_stage_outcome_id=None,
        version_no=1,
        publication_status="processed",
        confidence_label="high",
        summary_text="Summary",
        key_decisions_json="[]",
        key_actions_json="[]",
        notable_topics_json="[]",
        published_at="2026-02-27T13:00:30Z",
    )
    output = SummarizationOutput.from_payload(
        {
            "summary": "Summary",
            "key_decisions": [],
            "key_actions": [],
            "notable_topics": [],
            "claims": [
                {
                    "claim_text": "The council approved Resolution 77.",
                    "evidence": [
                        {
                            "artifact_id": "artifact-minutes-77",
                            "section_ref": "minutes.section.4",
                            "char_start": 412,
                            "char_end": 503,
                            "excerpt": "Motion carried unanimously for Resolution 77.",
                        }
                    ],
                },
                {
                    "claim_text": "Staff will publish implementation memo next week.",
                    "evidence": [],
                },
            ],
        }
    )

    attachment = attach_claim_evidence(
        repository=repository,
        publication_id=publication.id,
        claims=output.claims,
    )

    claims = repository.list_claims_for_publication(publication_id=publication.id)
    first_claim_evidence = repository.list_evidence_for_claim(claim_id=claims[0].id)
    second_claim_evidence = repository.list_evidence_for_claim(claim_id=claims[1].id)

    assert tuple(claim.id for claim in claims) == (
        "pub-contract-3:claim:1",
        "pub-contract-3:claim:2",
    )
    assert attachment.evidence_pointers == ("pub-contract-3:claim:1:evidence:1",)
    assert attachment.evidence_gap_claims == ("pub-contract-3:claim:2",)
    assert len(first_claim_evidence) == 1
    assert first_claim_evidence[0].artifact_id == "artifact-minutes-77"
    assert first_claim_evidence[0].section_ref == "minutes.section.4"
    assert first_claim_evidence[0].char_start == 412
    assert first_claim_evidence[0].char_end == 503
    assert first_claim_evidence[0].excerpt == "Motion carried unanimously for Resolution 77."
    assert second_claim_evidence == ()


def test_publish_quality_gate_routes_weak_evidence_to_limited_confidence(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-contract-4", uid="meeting-contract-uid-4")

    run_repository = ProcessingRunRepository(connection)
    run = run_repository.create_pending_run(
        run_id="run-contract-4",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T14:00:00Z",
    )

    output = SummarizationOutput.from_payload(
        {
            "summary": "The council discussed zoning updates.",
            "key_decisions": ["Continue to staff review"],
            "key_actions": ["Planning department to return with revised draft"],
            "notable_topics": ["Zoning", "Community feedback"],
            "claims": [
                {
                    "claim_text": "The council requested additional zoning analysis.",
                    "evidence": [],
                }
            ],
        }
    )

    result = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-contract-4",
        meeting_id="meeting-contract-4",
        processing_run_id=run.id,
        publish_stage_outcome_id=None,
        version_no=1,
        base_confidence_label="medium",
        output=output,
        published_at="2026-02-27T14:00:30Z",
    )

    assert result.publication.publication_status == "limited_confidence"
    assert result.publication.confidence_label == "limited_confidence"
    assert "claim_evidence_gap_present" in result.quality_gate.reason_codes
    assert "evidence_coverage_below_threshold" in result.quality_gate.reason_codes


def test_publish_quality_gate_routes_sufficient_evidence_to_processed(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    _create_meeting(connection, meeting_id="meeting-contract-5", uid="meeting-contract-uid-5")

    run_repository = ProcessingRunRepository(connection)
    run = run_repository.create_pending_run(
        run_id="run-contract-5",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T15:00:00Z",
    )

    output = SummarizationOutput.from_payload(
        {
            "summary": "Council approved two transportation contracts.",
            "key_decisions": ["Approved contracts A and B"],
            "key_actions": ["Procurement to finalize signatures"],
            "notable_topics": ["Transit", "Budget"],
            "claims": [
                {
                    "claim_text": "Council approved contract A.",
                    "evidence": [
                        {
                            "artifact_id": "artifact-minutes-transport-a",
                            "section_ref": "minutes.section.3",
                            "excerpt": "Vote passed to approve contract A.",
                        }
                    ],
                },
                {
                    "claim_text": "Council approved contract B.",
                    "evidence": [
                        {
                            "artifact_id": "artifact-minutes-transport-b",
                            "section_ref": "minutes.section.4",
                            "excerpt": "Vote passed to approve contract B.",
                        }
                    ],
                },
            ],
        }
    )

    result = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-contract-5",
        meeting_id="meeting-contract-5",
        processing_run_id=run.id,
        publish_stage_outcome_id=None,
        version_no=1,
        base_confidence_label="medium",
        output=output,
        published_at="2026-02-27T15:00:30Z",
        quality_gate_config=QualityGateConfig(min_evidence_coverage_rate=1.0),
    )

    assert result.publication.publication_status == "processed"
    assert result.publication.confidence_label == "medium"
    assert result.quality_gate.reason_codes == ("quality_gate_pass",)