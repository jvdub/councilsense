from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from councilsense.app.local_latest_fetch import fetch_latest_meeting
from councilsense.app.local_pipeline import LocalPipelineOrchestrator
from councilsense.app.pipeline_retry import PermanentStageError, StageExecutionService, StageWorkItem
from councilsense.app.st031_source_observability import (
    PIPELINE_DLQ_BACKLOG_COUNT,
    PIPELINE_DLQ_OLDEST_AGE_SECONDS,
    SOURCE_CITATION_PRECISION_RATIO,
    SOURCE_COVERAGE_RATIO,
    SOURCE_STAGE_OUTCOMES_TOTAL,
)
from councilsense.db import PILOT_CITY_ID, ProcessingLifecycleService, ProcessingRunRepository, apply_migrations, seed_city_registry


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


def _collecting_metric_emitter(samples: list[dict[str, object]]):
    def _emit(
        name: str,
        stage: str,
        outcome: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        samples.append(
            {
                "name": name,
                "stage": stage,
                "outcome": outcome,
                "value": value,
                "labels": dict(labels or {}),
            }
        )

    return _emit


def test_st031_success_path_emits_source_stage_quality_metrics(
    connection: sqlite3.Connection,
    tmp_path,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    samples: list[dict[str, object]] = []
    metric_emitter = _collecting_metric_emitter(samples)

    fetch_result = fetch_latest_meeting(
        connection,
        city_id=PILOT_CITY_ID,
        timeout_seconds=5.0,
        artifact_root=str(tmp_path / "artifacts"),
        fetch_url=_stub_fetch,
        metric_emitter=metric_emitter,
    )
    orchestrator = LocalPipelineOrchestrator(connection, metric_emitter=metric_emitter)
    result = orchestrator.process_latest(
        run_id="run-st031-metrics-success",
        city_id=PILOT_CITY_ID,
        meeting_id=fetch_result.meeting_id,
        ingest_stage_metadata=fetch_result.stage_outcomes[0]["metadata"],
        llm_provider="none",
        ollama_endpoint=None,
        ollama_model=None,
        ollama_timeout_seconds=20.0,
    )

    assert result.status in {"processed", "limited_confidence"}

    stage_samples = [sample for sample in samples if sample["name"] == SOURCE_STAGE_OUTCOMES_TOTAL]
    assert {
        (sample["stage"], sample["outcome"], sample["labels"]["source_type"])
        for sample in stage_samples
    } >= {
        ("ingest", "success", "minutes"),
        ("extract", "success", "minutes"),
        ("compose", "success", "bundle"),
    }

    coverage_sample = next(sample for sample in samples if sample["name"] == SOURCE_COVERAGE_RATIO)
    assert coverage_sample["stage"] == "compose"
    assert coverage_sample["outcome"] == "measured"
    assert coverage_sample["labels"] == {"city_id": PILOT_CITY_ID, "source_type": "bundle"}
    assert 0.0 <= float(coverage_sample["value"]) <= 1.0

    citation_sample = next(sample for sample in samples if sample["name"] == SOURCE_CITATION_PRECISION_RATIO)
    assert citation_sample["stage"] == "summarize"
    assert citation_sample["labels"] == {"city_id": PILOT_CITY_ID, "source_type": "bundle"}
    assert 0.0 <= float(citation_sample["value"]) <= 1.0


def test_st031_terminal_failure_emits_dlq_backlog_and_age_metrics(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    samples: list[dict[str, object]] = []
    metric_emitter = _collecting_metric_emitter(samples)
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        metric_emitter=metric_emitter,
    )

    run = repository.create_pending_run(
        run_id="run-st031-dlq-metrics",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-07T12:00:00Z",
    )
    item = StageWorkItem(
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-st031-dlq-metrics",
        source_id="source-st031-minutes",
        source_type="minutes",
    )

    def _worker(_: StageWorkItem) -> None:
        raise PermanentStageError("parser mismatch")

    result = execution.execute_one(stage_name="extract", item=item, worker=_worker)

    assert result.status == "failed"

    failure_stage = next(
        sample
        for sample in samples
        if sample["name"] == SOURCE_STAGE_OUTCOMES_TOTAL
        and sample["stage"] == "extract"
        and sample["outcome"] == "failure"
    )
    assert failure_stage["labels"] == {
        "city_id": PILOT_CITY_ID,
        "source_type": "minutes",
        "status": "failed",
    }

    backlog_sample = next(sample for sample in samples if sample["name"] == PIPELINE_DLQ_BACKLOG_COUNT)
    assert backlog_sample["stage"] == "extract"
    assert backlog_sample["outcome"] == "backlog"
    assert backlog_sample["labels"] == {
        "city_id": PILOT_CITY_ID,
        "source_id": "source-st031-minutes",
        "source_type": "minutes",
    }
    assert float(backlog_sample["value"]) == 1.0

    oldest_age_sample = next(sample for sample in samples if sample["name"] == PIPELINE_DLQ_OLDEST_AGE_SECONDS)
    assert oldest_age_sample["stage"] == "extract"
    assert oldest_age_sample["outcome"] == "oldest_age"
    assert oldest_age_sample["labels"] == {
        "city_id": PILOT_CITY_ID,
        "source_id": "source-st031-minutes",
        "source_type": "minutes",
    }
    assert float(oldest_age_sample["value"]) >= 0.0