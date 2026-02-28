from __future__ import annotations

import json
import sqlite3

import pytest

from councilsense.app.pipeline_contracts import (
    consume_extract_payload,
    consume_ingest_payload,
    consume_publish_payload,
    consume_summarize_payload,
    handoff_extract_to_summarize,
    handoff_ingest_to_extract,
    handoff_summarize_to_publish,
    produce_ingest_payload,
)
from councilsense.app.pipeline_retry import (
    PermanentStageError,
    StageExecutionService,
    StageRetryPolicy,
    StageWorkItem,
    TransientStageError,
)
from councilsense.app.scheduler import InMemoryCityScanQueueProducer, run_scheduler_cycle
from councilsense.db import PILOT_CITY_ID, ProcessingLifecycleService, ProcessingRunRepository, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_scheduler_actions_feed_contract_valid_stage_handoffs(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "city-second",
            "second-city-ut",
            "Second City",
            "UT",
            "America/Denver",
            1,
            2,
        ),
    )

    queue = InMemoryCityScanQueueProducer()
    enqueued_city_ids = run_scheduler_cycle(
        connection=connection,
        queue_producer=queue,
        cycle_id="2026-02-27T09:00:00Z",
    )

    assert enqueued_city_ids == (PILOT_CITY_ID, "city-second")
    assert len(queue.enqueued_actions) == 2

    for action in queue.enqueued_actions:
        meeting_id = f"meeting-{action.city_id}"

        ingest = consume_ingest_payload(
            produce_ingest_payload(
                run_id=action.run_id,
                city_id=action.city_id,
                meeting_id=meeting_id,
                source_id="source-city-feed",
            )
        )
        extract = consume_extract_payload(
            handoff_ingest_to_extract(
                ingest,
                raw_artifact_uri=f"s3://raw/{meeting_id}.json",
            ).to_payload()
        )
        summarize = consume_summarize_payload(
            handoff_extract_to_summarize(
                extract,
                extracted_text_uri=f"s3://extract/{meeting_id}.txt",
            ).to_payload()
        )
        publish = consume_publish_payload(
            handoff_summarize_to_publish(
                summarize,
                summary_markdown=f"Summary for {meeting_id}",
            ).to_payload()
        )

        assert ingest.correlation_ids == extract.correlation_ids
        assert extract.correlation_ids == summarize.correlation_ids
        assert summarize.correlation_ids == publish.correlation_ids
        assert publish.run_id == action.run_id
        assert publish.city_id == action.city_id
        assert publish.meeting_id == meeting_id


def test_orchestration_retry_failure_isolation_and_lifecycle_persistence(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)
    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "city-second",
            "second-city-ut",
            "Second City",
            "UT",
            "America/Denver",
            1,
            2,
        ),
    )

    queue = InMemoryCityScanQueueProducer()
    run_scheduler_cycle(
        connection=connection,
        queue_producer=queue,
        cycle_id="2026-02-27T10:00:00Z",
    )

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    execution = StageExecutionService(
        repository=repository,
        lifecycle_service=lifecycle,
        retry_policy=StageRetryPolicy(max_attempts=3),
    )

    run_id_by_city = {action.city_id: action.run_id for action in queue.enqueued_actions}
    items = tuple(
        StageWorkItem(
            run_id=action.run_id,
            city_id=action.city_id,
            meeting_id=f"meeting-{action.city_id}",
            source_id="source-city-feed",
        )
        for action in queue.enqueued_actions
    )

    attempts_by_city = {PILOT_CITY_ID: 0, "city-second": 0}

    def _worker(item: StageWorkItem) -> None:
        attempts_by_city[item.city_id] += 1
        if item.city_id == PILOT_CITY_ID and attempts_by_city[item.city_id] == 1:
            raise TransientStageError("upstream timeout")
        if item.city_id == "city-second":
            raise PermanentStageError("parser mismatch")

    results = execution.execute_many(stage_name="ingest", items=items, worker=_worker)

    assert len(results) == 2
    result_by_city = {result.city_id: result for result in results}
    assert result_by_city[PILOT_CITY_ID].status == "processed"
    assert result_by_city[PILOT_CITY_ID].attempts == 2
    assert result_by_city[PILOT_CITY_ID].failure_classification is None
    assert result_by_city["city-second"].status == "failed"
    assert result_by_city["city-second"].attempts == 1
    assert result_by_city["city-second"].failure_classification == "permanent"

    pilot_run = repository.get_run(run_id=run_id_by_city[PILOT_CITY_ID])
    second_run = repository.get_run(run_id=run_id_by_city["city-second"])
    assert pilot_run.status == "processed"
    assert second_run.status == "failed"
    assert pilot_run.started_at is not None
    assert second_run.started_at is not None
    assert pilot_run.finished_at is not None
    assert second_run.finished_at is not None

    pilot_outcomes = repository.list_stage_outcomes_for_run_city(
        run_id=run_id_by_city[PILOT_CITY_ID],
        city_id=PILOT_CITY_ID,
    )
    second_outcomes = repository.list_stage_outcomes_for_run_city(
        run_id=run_id_by_city["city-second"],
        city_id="city-second",
    )

    assert len(pilot_outcomes) == 1
    assert len(second_outcomes) == 1
    assert pilot_outcomes[0].status == "processed"
    assert second_outcomes[0].status == "failed"

    pilot_metadata = json.loads(pilot_outcomes[0].metadata_json or "{}")
    second_metadata = json.loads(second_outcomes[0].metadata_json or "{}")
    assert pilot_metadata["attempts"] == 2
    assert pilot_metadata["failure_classification"] is None
    assert second_metadata["attempts"] == 1
    assert second_metadata["failure_classification"] == "permanent"
