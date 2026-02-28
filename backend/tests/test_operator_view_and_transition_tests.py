from __future__ import annotations

import sqlite3

import pytest

from councilsense.app.operator_triage import build_operator_triage_view
from councilsense.db import (
    PILOT_CITY_ID,
    PILOT_CITY_SOURCE_ID,
    ProcessingLifecycleService,
    ProcessingRunRepository,
    SourceHealthRepository,
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


def test_operator_triage_view_lists_stale_failing_and_manual_review_runs(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    connection.execute(
        """
        UPDATE city_sources
        SET
            health_status = 'healthy',
            failure_streak = 0,
            last_attempt_at = '2026-02-27 02:00:00',
            last_success_at = '2026-02-27 02:00:00',
            last_failure_at = NULL,
            last_failure_reason = NULL
        WHERE id = ?
        """,
        (PILOT_CITY_SOURCE_ID,),
    )

    connection.execute(
        """
        INSERT INTO city_sources (
            id,
            city_id,
            source_type,
            source_url,
            enabled,
            parser_name,
            parser_version,
            health_status,
            last_attempt_at,
            last_success_at,
            failure_streak
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "source-eagle-mountain-ut-agenda-stale",
            PILOT_CITY_ID,
            "agenda",
            "https://www.eaglemountain.gov/agenda-center/agenda-stale",
            1,
            "agenda-html",
            "v3",
            "healthy",
            "2026-02-21 08:00:00",
            "2026-02-21 08:00:00",
            0,
        ),
    )

    connection.execute(
        """
        INSERT INTO city_sources (
            id,
            city_id,
            source_type,
            source_url,
            enabled,
            parser_name,
            parser_version,
            health_status,
            last_attempt_at,
            last_success_at,
            last_failure_at,
            last_failure_reason,
            failure_streak
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "source-eagle-mountain-ut-packet-failing",
            PILOT_CITY_ID,
            "packet",
            "https://www.eaglemountain.gov/agenda-center/packet-failing",
            1,
            "packet-html",
            "v2",
            "failing",
            "2026-02-27 01:55:00",
            "2026-02-24 06:00:00",
            "2026-02-27 01:55:00",
            "PermanentStageError: parser mismatch",
            3,
        ),
    )

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    run = repository.create_pending_run(
        run_id="run-manual-review-operator-view-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T09:00:00Z",
    )
    repository.upsert_stage_outcome(
        outcome_id="outcome-manual-review-operator-view-1",
        run_id=run.id,
        city_id=run.city_id,
        meeting_id="meeting-manual-review-operator-view-1",
        stage_name="summarize",
        status="processed",
        metadata_json='{"confidence_score":0.41}',
        started_at="2026-02-27T09:00:01Z",
        finished_at="2026-02-27T09:00:15Z",
    )
    manual_review_run = lifecycle.mark_completed_from_confidence_policy(run_id=run.id)
    assert manual_review_run.status == "manual_review_needed"

    payload = build_operator_triage_view(
        connection=connection,
        stale_before="2026-02-26 00:00:00",
        generated_at="2026-02-27T10:00:00Z",
    )

    assert set(payload.keys()) == {
        "generated_at",
        "stale_before",
        "stale_sources",
        "failing_sources",
        "manual_review_runs",
    }
    assert payload["generated_at"] == "2026-02-27T10:00:00Z"
    assert payload["stale_before"] == "2026-02-26 00:00:00"

    stale_sources = payload["stale_sources"]
    stale_source_ids = {source["source_id"] for source in stale_sources}
    assert "source-eagle-mountain-ut-agenda-stale" in stale_source_ids
    stale_source = next(source for source in stale_sources if source["source_id"] == "source-eagle-mountain-ut-agenda-stale")
    assert set(stale_source.keys()) == {
        "source_id",
        "city_id",
        "city_slug",
        "source_type",
        "source_url",
        "health_status",
        "failure_streak",
        "parser_name",
        "parser_version",
        "last_attempt_at",
        "last_success_at",
        "last_failure_at",
        "last_failure_reason",
    }

    failing_sources = payload["failing_sources"]
    assert [source["source_id"] for source in failing_sources] == ["source-eagle-mountain-ut-packet-failing"]
    assert failing_sources[0]["health_status"] == "failing"
    assert failing_sources[0]["last_failure_reason"] == "PermanentStageError: parser mismatch"

    manual_review_runs = payload["manual_review_runs"]
    assert [entry["run_id"] for entry in manual_review_runs] == [run.id]
    manual_review_entry = manual_review_runs[0]
    assert set(manual_review_entry.keys()) == {
        "run_id",
        "city_id",
        "city_slug",
        "cycle_id",
        "status",
        "parser_version",
        "source_version",
        "started_at",
        "finished_at",
        "confidence_score",
    }
    assert manual_review_entry["status"] == "manual_review_needed"
    assert manual_review_entry["confidence_score"] == 0.41
    assert manual_review_entry["parser_version"] == "agenda-html@v3|civicplus-minutes-html@v1|packet-html@v2"
    assert manual_review_entry["source_version"].startswith("sources-sha256:")


def test_source_health_and_manual_review_transitions_follow_expected_pathways(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    health_repository = SourceHealthRepository(connection)
    health_repository.record_ingest_attempt(
        source_id=PILOT_CITY_SOURCE_ID,
        succeeded=False,
        failure_reason="PermanentStageError: timeout",
    )
    degraded_row = connection.execute(
        """
        SELECT health_status, failure_streak, last_failure_reason, last_attempt_at, last_failure_at
        FROM city_sources
        WHERE id = ?
        """,
        (PILOT_CITY_SOURCE_ID,),
    ).fetchone()
    assert degraded_row is not None
    assert degraded_row[0] == "degraded"
    assert degraded_row[1] == 1
    assert degraded_row[2] == "PermanentStageError: timeout"
    assert degraded_row[3] is not None
    assert degraded_row[4] is not None

    health_repository.record_ingest_attempt(
        source_id=PILOT_CITY_SOURCE_ID,
        succeeded=False,
        failure_reason="PermanentStageError: malformed payload",
    )
    health_repository.record_ingest_attempt(
        source_id=PILOT_CITY_SOURCE_ID,
        succeeded=False,
        failure_reason="PermanentStageError: schema mismatch",
    )
    failing_row = connection.execute(
        """
        SELECT health_status, failure_streak, last_failure_reason
        FROM city_sources
        WHERE id = ?
        """,
        (PILOT_CITY_SOURCE_ID,),
    ).fetchone()
    assert failing_row is not None
    assert failing_row[0] == "failing"
    assert failing_row[1] == 3
    assert failing_row[2] == "PermanentStageError: schema mismatch"

    health_repository.record_ingest_attempt(source_id=PILOT_CITY_SOURCE_ID, succeeded=True)
    recovered_row = connection.execute(
        """
        SELECT health_status, failure_streak, last_success_at
        FROM city_sources
        WHERE id = ?
        """,
        (PILOT_CITY_SOURCE_ID,),
    ).fetchone()
    assert recovered_row is not None
    assert recovered_row[0] == "healthy"
    assert recovered_row[1] == 0
    assert recovered_row[2] is not None

    repository = ProcessingRunRepository(connection)
    lifecycle = ProcessingLifecycleService(repository)
    manual_review_run = repository.create_pending_run(
        run_id="run-transition-manual-review",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T11:00:00Z",
    )
    repository.upsert_stage_outcome(
        outcome_id="outcome-transition-manual-review",
        run_id=manual_review_run.id,
        city_id=manual_review_run.city_id,
        meeting_id="meeting-transition-manual-review",
        stage_name="publish",
        status="processed",
        metadata_json='{"confidence_score":0.22}',
        started_at="2026-02-27T11:00:01Z",
        finished_at="2026-02-27T11:00:15Z",
    )

    processed_run = repository.create_pending_run(
        run_id="run-transition-processed",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T11:10:00Z",
    )
    repository.upsert_stage_outcome(
        outcome_id="outcome-transition-processed",
        run_id=processed_run.id,
        city_id=processed_run.city_id,
        meeting_id="meeting-transition-processed",
        stage_name="publish",
        status="processed",
        metadata_json='{"confidence_score":0.92}',
        started_at="2026-02-27T11:10:01Z",
        finished_at="2026-02-27T11:10:15Z",
    )

    manual_review_result = lifecycle.mark_completed_from_confidence_policy(run_id=manual_review_run.id)
    processed_result = lifecycle.mark_completed_from_confidence_policy(run_id=processed_run.id)

    assert manual_review_result.status == "manual_review_needed"
    assert processed_result.status == "processed"
