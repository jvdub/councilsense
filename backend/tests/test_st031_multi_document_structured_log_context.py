from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator

import pytest

from councilsense.app.local_latest_fetch import fetch_latest_meeting
from councilsense.app.local_pipeline import LocalPipelineOrchestrator
from councilsense.app.multi_document_observability import (
    MULTI_DOCUMENT_LOG_FIELD_COVERAGE,
    MULTI_DOCUMENT_PIPELINE_STAGES,
    MultiDocumentLogContractError,
    build_bundle_id,
    validate_multi_document_log_event,
)
from councilsense.db import PILOT_CITY_ID, apply_migrations, seed_city_registry


def _stub_fetch(url: str, __: float) -> bytes:
    if "/events?" in url or url.endswith("/events"):
        return (
            '{"value":[{"id":21,"eventName":"City Council Meeting","eventDate":"2026-01-08T00:00:00Z",'
            '"publishedFiles":[{"type":"Minutes","name":"Approved Minutes","fileId":1102,"url":"stream/fixture-minutes.pdf"}]}]}'
        ).encode("utf-8")
    if "GetMeetingFile(" in url and "plainText=true" in url:
        return b'{"blobUri":"https://blob.example/minutes.txt"}'
    if "GetMeetingFile(" in url and "plainText=false" in url:
        return b'{"blobUri":"https://blob.example/minutes.pdf"}'
    if url.endswith("minutes.txt"):
        return b"City Council approved minutes and directed staff to publish updates."
    return b"%PDF-1.7\nmock pdf bytes"


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _multi_document_events(caplog: pytest.LogCaptureFixture) -> tuple[dict[str, object], ...]:
    events: list[dict[str, object]] = []
    for record in caplog.records:
        event = getattr(record, "event", None)
        if not isinstance(event, dict):
            continue
        stage = str(event.get("stage", ""))
        if stage in MULTI_DOCUMENT_PIPELINE_STAGES and str(event.get("event_name", "")).startswith("pipeline_stage_"):
            events.append(event)
    return tuple(events)


def test_st031_success_path_emits_required_correlation_fields_for_all_multi_document_stages(
    connection: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
    tmp_path,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    caplog.set_level(logging.INFO)

    fetch_result = fetch_latest_meeting(
        connection,
        city_id=PILOT_CITY_ID,
        timeout_seconds=5.0,
        artifact_root=str(tmp_path / "artifacts"),
        fetch_url=_stub_fetch,
    )
    orchestrator = LocalPipelineOrchestrator(connection)
    result = orchestrator.process_latest(
        run_id="run-st031-success",
        city_id=PILOT_CITY_ID,
        meeting_id=fetch_result.meeting_id,
        ingest_stage_metadata=fetch_result.stage_outcomes[0]["metadata"],
        llm_provider="none",
        ollama_endpoint=None,
        ollama_model=None,
        ollama_timeout_seconds=20.0,
    )

    assert result.status in {"processed", "limited_confidence"}

    events = _multi_document_events(caplog)
    terminal_events = {str(event["stage"]): event for event in events if event["event_name"] == "pipeline_stage_finished"}
    assert set(terminal_events) == set(MULTI_DOCUMENT_PIPELINE_STAGES)

    expected_bundle_id = build_bundle_id(meeting_id=fetch_result.meeting_id)
    extract_artifact_id = str(terminal_events["extract"]["artifact_id"])
    for stage, event in terminal_events.items():
        required_fields = MULTI_DOCUMENT_LOG_FIELD_COVERAGE[stage]
        assert set(required_fields).issubset(event.keys())
        for field in required_fields:
            assert isinstance(event[field], str)
            assert str(event[field]).strip()
        assert event["bundle_id"] == expected_bundle_id
        assert event["outcome"] == "success"
        if stage in {"compose", "summarize", "publish"}:
            assert event["source_type"] == "bundle"
            assert event["artifact_id"] == extract_artifact_id
        else:
            assert event["source_type"] == "minutes"


def test_st031_publish_failure_path_emits_required_correlation_fields(
    connection: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
    monkeypatch,
    tmp_path,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    fetch_result = fetch_latest_meeting(
        connection,
        city_id=PILOT_CITY_ID,
        timeout_seconds=5.0,
        artifact_root=str(tmp_path / "artifacts"),
        fetch_url=_stub_fetch,
    )

    def _raise_publish(*args, **kwargs):
        raise RuntimeError("publish exploded")

    monkeypatch.setattr("councilsense.app.local_pipeline.publish_summarization_output", _raise_publish)
    caplog.set_level(logging.INFO)

    result = LocalPipelineOrchestrator(connection).process_latest(
        run_id="run-st031-publish-failure",
        city_id=PILOT_CITY_ID,
        meeting_id=fetch_result.meeting_id,
        ingest_stage_metadata=fetch_result.stage_outcomes[0]["metadata"],
        llm_provider="none",
        ollama_endpoint=None,
        ollama_model=None,
        ollama_timeout_seconds=20.0,
    )

    assert result.status == "failed"
    assert result.error_summary is not None
    assert result.error_summary["stage"] == "publish"

    publish_errors = [
        event
        for event in _multi_document_events(caplog)
        if event.get("stage") == "publish" and event.get("event_name") == "pipeline_stage_error"
    ]
    assert len(publish_errors) == 1
    event = publish_errors[0]
    for field in MULTI_DOCUMENT_LOG_FIELD_COVERAGE["publish"]:
        assert isinstance(event[field], str)
        assert str(event[field]).strip()
    assert event["outcome"] == "failure"
    assert event["status"] == "failed"
    assert event["source_type"] == "bundle"
    assert event["bundle_id"] == build_bundle_id(meeting_id=fetch_result.meeting_id)
    assert event["error_message"] == "publish exploded"


def test_st031_missing_required_log_fields_are_detected_explicitly() -> None:
    with pytest.raises(MultiDocumentLogContractError) as exc_info:
        validate_multi_document_log_event(
            stage="compose",
            event={
                "event_name": "pipeline_stage_finished",
                "city_id": PILOT_CITY_ID,
                "meeting_id": "meeting-st031-missing-field",
                "run_id": "run-st031-missing-field",
                "stage": "compose",
                "source_id": "source-minutes",
                "source_type": "bundle",
                "artifact_id": "",
                "bundle_id": build_bundle_id(meeting_id="meeting-st031-missing-field"),
                "dedupe_key": "pipeline-multidoc:broken",
                "outcome": "success",
            },
        )

    assert exc_info.value.stage == "compose"
    assert exc_info.value.missing_fields == ("artifact_id",)