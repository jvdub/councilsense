from __future__ import annotations

import pytest

from councilsense.app.pipeline_contracts import (
    StageCorrelationIds,
    StageQueueContractError,
    consume_extract_payload,
    consume_ingest_payload,
    consume_publish_payload,
    consume_summarize_payload,
    handoff_extract_to_summarize,
    handoff_ingest_to_extract,
    handoff_summarize_to_publish,
    produce_extract_payload,
    produce_ingest_payload,
    produce_publish_payload,
    produce_summarize_payload,
)


def test_stage_payload_contracts_validate_for_each_stage() -> None:
    ingest = consume_ingest_payload(
        produce_ingest_payload(
            run_id="run-001",
            city_id="city-eagle-mountain-ut",
            meeting_id="meeting-123",
            source_id="source-abc",
        )
    )
    extract = consume_extract_payload(
        produce_extract_payload(
            run_id="run-001",
            city_id="city-eagle-mountain-ut",
            meeting_id="meeting-123",
            raw_artifact_uri="s3://raw/meeting-123.json",
        )
    )
    summarize = consume_summarize_payload(
        produce_summarize_payload(
            run_id="run-001",
            city_id="city-eagle-mountain-ut",
            meeting_id="meeting-123",
            extracted_text_uri="s3://extract/meeting-123.txt",
        )
    )
    publish = consume_publish_payload(
        produce_publish_payload(
            run_id="run-001",
            city_id="city-eagle-mountain-ut",
            meeting_id="meeting-123",
            summary_markdown="## Summary",
        )
    )

    assert ingest.source_id == "source-abc"
    assert extract.raw_artifact_uri == "s3://raw/meeting-123.json"
    assert summarize.extracted_text_uri == "s3://extract/meeting-123.txt"
    assert publish.summary_markdown == "## Summary"


def test_stage_handoffs_preserve_correlation_identifiers() -> None:
    ingest = consume_ingest_payload(
        {
            "run_id": "run-002",
            "city_id": "city-eagle-mountain-ut",
            "meeting_id": "meeting-456",
            "source_id": "source-def",
        }
    )

    extract = handoff_ingest_to_extract(ingest, raw_artifact_uri="s3://raw/meeting-456.json")
    summarize = handoff_extract_to_summarize(extract, extracted_text_uri="s3://extract/meeting-456.txt")
    publish = handoff_summarize_to_publish(summarize, summary_markdown="Final summary")

    expected = StageCorrelationIds(
        run_id="run-002",
        city_id="city-eagle-mountain-ut",
        meeting_id="meeting-456",
    )
    assert ingest.correlation_ids == expected
    assert extract.correlation_ids == expected
    assert summarize.correlation_ids == expected
    assert publish.correlation_ids == expected


@pytest.mark.parametrize(
    ("consumer", "payload", "expected_stage", "expected_field"),
    [
        (
            consume_ingest_payload,
            {
                "run_id": "run-101",
                "city_id": "city-eagle-mountain-ut",
                "meeting_id": "meeting-101",
            },
            "ingest",
            "source_id",
        ),
        (
            consume_extract_payload,
            {
                "run_id": "run-101",
                "city_id": "city-eagle-mountain-ut",
                "meeting_id": "meeting-101",
                "raw_artifact_uri": "   ",
            },
            "extract",
            "raw_artifact_uri",
        ),
        (
            consume_summarize_payload,
            {
                "run_id": "run-101",
                "city_id": 12,
                "meeting_id": "meeting-101",
                "extracted_text_uri": "s3://extract/item.txt",
            },
            "summarize",
            "city_id",
        ),
        (
            consume_publish_payload,
            {
                "run_id": "run-101",
                "city_id": "city-eagle-mountain-ut",
                "meeting_id": "meeting-101",
                "summary_markdown": None,
            },
            "publish",
            "summary_markdown",
        ),
    ],
)
def test_invalid_stage_payloads_are_rejected_explicitly(
    consumer: object,
    payload: dict[str, object],
    expected_stage: str,
    expected_field: str,
) -> None:
    with pytest.raises(StageQueueContractError) as exc:
        consumer(payload)

    assert exc.value.stage == expected_stage
    assert exc.value.field == expected_field