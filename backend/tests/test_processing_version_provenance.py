from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from councilsense.db import PILOT_CITY_ID, ProcessingRunRepository, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_processing_runs_persist_parser_and_source_provenance(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

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
            failure_streak
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "source-eagle-mountain-ut-agenda-primary",
            PILOT_CITY_ID,
            "agenda",
            "https://www.eaglemountain.gov/agenda-center/agenda",
            1,
            "agenda-html",
            "v3",
            "unknown",
            0,
        ),
    )

    repository = ProcessingRunRepository(connection)
    run = repository.create_pending_run(
        run_id="run-provenance-1",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T12:00:00Z",
    )

    assert run.parser_version == "agenda-html@v3|civicplus-minutes-html@v1"
    assert run.source_version.startswith("sources-sha256:")
    assert len(run.source_version) == len("sources-sha256:") + 12

    fetched = repository.get_run(run_id=run.id)
    assert fetched.parser_version == run.parser_version
    assert fetched.source_version == run.source_version


def test_historical_processing_runs_remain_readable_with_provenance_defaults(
    connection: sqlite3.Connection,
) -> None:
    migration_dir = (
        Path(__file__).resolve().parents[1] / "src" / "councilsense" / "db" / "migrations"
    )
    applied_pre_provenance = (
        "0001_city_registry.sql",
        "0002_meetings_city_linkage.sql",
        "0003_pipeline_run_lifecycle.sql",
        "0004_summary_evidence_persistence.sql",
        "0005_summary_publish_append_only_guards.sql",
        "0006_meeting_reader_query_indexes.sql",
        "0007_source_health_failure_context.sql",
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    for migration_name in applied_pre_provenance:
        migration_sql = (migration_dir / migration_name).read_text(encoding="utf-8")
        with connection:
            connection.executescript(migration_sql)
            connection.execute(
                "INSERT INTO schema_migrations (name) VALUES (?)",
                (migration_name,),
            )

    seed_city_registry(connection)
    connection.execute(
        """
        INSERT INTO processing_runs (id, city_id, cycle_id, status, started_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "run-historical-1",
            PILOT_CITY_ID,
            "2026-02-27T13:00:00Z",
            "processed",
            "2026-02-27T13:00:05Z",
        ),
    )

    apply_migrations(connection)

    repository = ProcessingRunRepository(connection)
    run = repository.get_run(run_id="run-historical-1")
    assert run.parser_version == "unknown"
    assert run.source_version == "unknown"
