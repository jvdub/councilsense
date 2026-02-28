from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator

import pytest

from councilsense.app.pipeline_retry import PermanentStageError, StageExecutionService, StageWorkItem
from councilsense.db import PILOT_CITY_ID, ProcessingLifecycleService, ProcessingRunRepository, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _pipeline_events(caplog: pytest.LogCaptureFixture) -> tuple[dict[str, object], ...]:
    events: list[dict[str, object]] = []
    for record in caplog.records:
        event = getattr(record, "event", None)
        if isinstance(event, dict) and str(event.get("event_name", "")).startswith("pipeline_"):
            events.append(event)
    return tuple(events)


def test_pipeline_stage_logs_emit_start_and_terminal_events_for_all_required_stages(
    connection: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    execution = StageExecutionService(repository=repository, lifecycle_service=lifecycle)

    caplog.set_level(logging.INFO)

    stage_behaviors = {
        "ingest": "success",
        "extract": "error",
        "summarize": "success",
        "publish": "success",
    }

    for stage_name, behavior in stage_behaviors.items():
        run = repository.create_pending_run(
            run_id=f"run-log-{stage_name}",
            city_id=PILOT_CITY_ID,
            cycle_id="2026-02-28T08:00:00Z",
        )
        item = StageWorkItem(
            run_id=run.id,
            city_id=run.city_id,
            meeting_id=f"meeting-{stage_name}",
            source_id="source-city-feed",
        )

        def _worker(_: StageWorkItem) -> None:
            if behavior == "error":
                raise PermanentStageError("parser mismatch")

        execution.execute_one(stage_name=stage_name, item=item, worker=_worker)

    events = _pipeline_events(caplog)
    stage_events = tuple(event for event in events if str(event.get("event_name", "")).startswith("pipeline_stage_"))

    required_keys = {"city_id", "meeting_id", "run_id", "dedupe_key", "stage", "outcome"}
    for event in stage_events:
        assert required_keys.issubset(event.keys())
        for key in required_keys:
            assert isinstance(event[key], str)
            assert str(event[key]).strip()

    started_stages = {str(event["stage"]) for event in stage_events if event["event_name"] == "pipeline_stage_started"}
    assert started_stages == {"fetch", "parse", "summarize", "publish"}

    terminal_events_by_stage = {
        str(event["stage"]): str(event["event_name"])
        for event in stage_events
        if event["event_name"] in {"pipeline_stage_finished", "pipeline_stage_error"}
    }
    assert terminal_events_by_stage == {
        "fetch": "pipeline_stage_finished",
        "parse": "pipeline_stage_error",
        "summarize": "pipeline_stage_finished",
        "publish": "pipeline_stage_finished",
    }

    parse_error_events = tuple(
        event
        for event in stage_events
        if event["stage"] == "parse" and event["event_name"] == "pipeline_stage_error"
    )
    assert len(parse_error_events) == 1
    assert parse_error_events[0]["error_code"] == "permanent_stage_error"
    assert parse_error_events[0]["error_message"] == "parser mismatch"


def test_pipeline_manual_review_needed_log_includes_required_structured_keys(
    connection: sqlite3.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)

    run = repository.create_pending_run(
        run_id="run-manual-review-log",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T09:00:00Z",
    )
    repository.upsert_stage_outcome(
        outcome_id="outcome-manual-review-log",
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-manual-review-log",
        stage_name="publish",
        status="processed",
        metadata_json='{"confidence_score":0.55}',
        started_at="2026-02-28T09:00:01Z",
        finished_at="2026-02-28T09:00:15Z",
    )

    caplog.set_level(logging.INFO)

    result = lifecycle.mark_completed_from_confidence_policy(run_id=run.id)
    assert result.status == "manual_review_needed"

    events = _pipeline_events(caplog)
    manual_review_events = tuple(event for event in events if event.get("event_name") == "pipeline_manual_review_needed")
    assert len(manual_review_events) == 1

    event = manual_review_events[0]
    required_keys = {"city_id", "meeting_id", "run_id", "dedupe_key", "stage", "outcome"}
    assert required_keys.issubset(event.keys())
    assert event["run_status"] == "manual_review_needed"
    assert event["reason_code"] == "confidence_below_manual_review_threshold"
