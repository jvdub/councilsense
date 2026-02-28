from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator

import pytest

from councilsense.app.parser_drift_policy import ParserDriftComparisonInput, evaluate_parser_drift
from councilsense.db import PILOT_CITY_ID, ProcessingRunRepository, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_parser_drift_policy_detects_expected_changed_fields() -> None:
    no_change = evaluate_parser_drift(
        ParserDriftComparisonInput(
            baseline_parser_name="minutes-html",
            baseline_parser_version="v1",
            current_parser_name="minutes-html",
            current_parser_version="v1",
        )
    )
    assert no_change is None

    version_only_change = evaluate_parser_drift(
        ParserDriftComparisonInput(
            baseline_parser_name="minutes-html",
            baseline_parser_version="v1",
            current_parser_name="minutes-html",
            current_parser_version="v2",
        )
    )
    assert version_only_change == ("parser_version",)

    parser_only_change = evaluate_parser_drift(
        ParserDriftComparisonInput(
            baseline_parser_name="minutes-html",
            baseline_parser_version="v2",
            current_parser_name="minutes-json",
            current_parser_version="v2",
        )
    )
    assert parser_only_change == ("parser_name",)

    parser_and_version_change = evaluate_parser_drift(
        ParserDriftComparisonInput(
            baseline_parser_name="minutes-html",
            baseline_parser_version="v1",
            current_parser_name="minutes-json",
            current_parser_version="v3",
        )
    )
    assert parser_and_version_change == ("parser_name", "parser_version")


def test_run_creation_snapshots_source_parser_versions_and_emits_drift_event_on_change(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)

    baseline_run = repository.create_pending_run(
        run_id="run-st016-parser-baseline",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T10:00:00Z",
    )

    baseline_snapshots = connection.execute(
        """
        SELECT source_id, parser_name, parser_version
        FROM processing_run_sources
        WHERE run_id = ?
        ORDER BY source_id ASC
        """,
        (baseline_run.id,),
    ).fetchall()
    assert baseline_snapshots
    assert baseline_snapshots[0][1] == "civicplus-minutes-html"
    assert baseline_snapshots[0][2] == "v1"

    baseline_events = repository.list_parser_drift_events(city_id=PILOT_CITY_ID)
    assert baseline_events == ()

    connection.execute(
        """
        UPDATE city_sources
        SET parser_version = 'v2', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (baseline_snapshots[0][0],),
    )

    changed_run = repository.create_pending_run(
        run_id="run-st016-parser-changed",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T11:00:00Z",
    )

    drift_events = repository.list_parser_drift_events(city_id=PILOT_CITY_ID)
    assert len(drift_events) == 1
    drift = drift_events[0]

    assert drift.event_schema_version == "st016.parser_drift_event.v1"
    assert drift.baseline_run_id == baseline_run.id
    assert drift.run_id == changed_run.id
    assert drift.baseline_parser_version == "v1"
    assert drift.current_parser_version == "v2"
    assert drift.baseline_source_version.startswith("sources-sha256:")
    assert drift.current_source_version.startswith("sources-sha256:")

    delta_context = json.loads(drift.delta_context_json)
    assert delta_context["changed_fields"] == ["parser_version"]
    assert delta_context["baseline"]["run_id"] == baseline_run.id
    assert delta_context["current"]["run_id"] == changed_run.id


def test_parser_drift_query_supports_city_source_parser_version_and_date_range_filters(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)

    first_run = repository.create_pending_run(
        run_id="run-st016-query-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T12:00:00Z",
    )

    source_row = connection.execute(
        "SELECT id FROM city_sources WHERE city_id = ? ORDER BY id ASC LIMIT 1",
        (PILOT_CITY_ID,),
    ).fetchone()
    assert source_row is not None
    source_id = str(source_row[0])

    connection.execute(
        "UPDATE city_sources SET parser_version = 'v9' WHERE id = ?",
        (source_id,),
    )
    second_run = repository.create_pending_run(
        run_id="run-st016-query-2",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T12:10:00Z",
    )

    connection.execute(
        "UPDATE parser_drift_events SET detected_at = '2026-02-28 12:10:30' WHERE run_id = ?",
        (second_run.id,),
    )

    connection.execute(
        "UPDATE city_sources SET parser_version = 'v10' WHERE id = ?",
        (source_id,),
    )
    third_run = repository.create_pending_run(
        run_id="run-st016-query-3",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T12:20:00Z",
    )

    connection.execute(
        "UPDATE parser_drift_events SET detected_at = '2026-02-28 12:20:30' WHERE run_id = ?",
        (third_run.id,),
    )

    by_city = repository.list_parser_drift_events(city_id=PILOT_CITY_ID)
    assert [event.run_id for event in by_city] == [third_run.id, second_run.id]

    by_source = repository.list_parser_drift_events(city_id=PILOT_CITY_ID, source_id=source_id)
    assert [event.run_id for event in by_source] == [third_run.id, second_run.id]

    by_parser_version = repository.list_parser_drift_events(parser_version="v9")
    assert [event.run_id for event in by_parser_version] == [third_run.id, second_run.id]

    by_date_range = repository.list_parser_drift_events(
        city_id=PILOT_CITY_ID,
        detected_from="2026-02-28 12:15:00",
        detected_to="2026-02-28 12:30:00",
    )
    assert [event.run_id for event in by_date_range] == [third_run.id]

    _ = first_run
