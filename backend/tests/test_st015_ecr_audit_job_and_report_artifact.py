from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import json
import sqlite3

import pytest

from councilsense.app.ecr_audit_job import WeeklyEcrAuditJob
from councilsense.db import PILOT_CITY_ID, PILOT_CITY_SOURCE_ID, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def seeded_connection(connection: sqlite3.Connection) -> sqlite3.Connection:
    apply_migrations(connection)
    seed_city_registry(connection)
    return connection


def test_scheduled_weekly_ecr_audit_persists_report_artifact(seeded_connection: sqlite3.Connection) -> None:
    window_start = datetime(2026, 2, 23, 0, 0, 0, tzinfo=UTC)
    scheduler_triggered_at = datetime(2026, 3, 2, 7, 0, 0, tzinfo=UTC)

    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-scheduled-1",
        meeting_id="meeting-scheduled-1",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        published_at=window_start + timedelta(days=1, hours=2),
        claims_with_evidence=2,
        claims_without_evidence=0,
    )

    job = WeeklyEcrAuditJob(connection=seeded_connection, now_provider=lambda: scheduler_triggered_at)
    result = job.run_scheduled_weekly_audit(scheduler_triggered_at_utc=scheduler_triggered_at)

    assert result.status == "completed"
    assert result.audit_week_start_utc == window_start
    assert result.report_artifact_uri == "quality/ecr-audits/2026-02-23/weekly-ecr-report.json"

    run_row = seeded_connection.execute(
        """
        SELECT status, sample_size_actual, eligible_frame_count, malformed_exclusion_count, report_artifact_uri
        FROM ecr_audit_runs
        WHERE id = ?
        """,
        (result.run_id,),
    ).fetchone()
    assert run_row == (
        "completed",
        1,
        1,
        0,
        "quality/ecr-audits/2026-02-23/weekly-ecr-report.json",
    )


def test_ecr_formula_and_confidence_breakdown_are_correct_for_fixture(seeded_connection: sqlite3.Connection) -> None:
    window_start = datetime(2026, 2, 16, 0, 0, 0, tzinfo=UTC)
    fixed_now = datetime(2026, 2, 24, 8, 30, 0, tzinfo=UTC)

    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-formula-1",
        meeting_id="meeting-formula-1",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        published_at=window_start + timedelta(days=1, hours=1),
        claims_with_evidence=2,
        claims_without_evidence=0,
    )
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-formula-2",
        meeting_id="meeting-formula-2",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="medium",
        published_at=window_start + timedelta(days=2, hours=1),
        claims_with_evidence=0,
        claims_without_evidence=1,
    )
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-formula-3",
        meeting_id="meeting-formula-3",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="limited_confidence",
        published_at=window_start + timedelta(days=3, hours=1),
        claims_with_evidence=1,
        claims_without_evidence=2,
    )

    job = WeeklyEcrAuditJob(connection=seeded_connection, now_provider=lambda: fixed_now)
    result = job.run_for_week(audit_week_start_utc=window_start, sample_size=60)

    assert result.status == "completed"

    artifact_row = seeded_connection.execute(
        """
        SELECT ecr, claim_count, claims_with_evidence_count, content_json
        FROM ecr_audit_report_artifacts
        WHERE run_id = ?
        """,
        (result.run_id,),
    ).fetchone()
    assert artifact_row is not None
    assert artifact_row[0] == 0.5
    assert artifact_row[1] == 6
    assert artifact_row[2] == 3

    payload = json.loads(str(artifact_row[3]))
    assert payload["report_version"] == "st-015-weekly-audit-report-v1"
    assert payload["formula_version"] == "st-015-ecr-formula-v1"
    assert payload["eligible_frame_count"] == 3
    assert payload["sample_size_actual"] == 3
    assert payload["ecr"] == 0.5
    assert payload["claim_count"] == 6
    assert payload["claims_with_evidence_count"] == 3
    assert payload["confidence_buckets"]["high"] == {
        "publication_count": 1,
        "claim_count": 2,
        "claims_with_evidence_count": 2,
        "ecr": 1.0,
    }
    assert payload["confidence_buckets"]["limited_confidence"] == {
        "publication_count": 1,
        "claim_count": 3,
        "claims_with_evidence_count": 1,
        "ecr": 0.3333,
    }
    assert payload["confidence_buckets"]["medium"] == {
        "publication_count": 1,
        "claim_count": 1,
        "claims_with_evidence_count": 0,
        "ecr": 0.0,
    }


def test_failed_audit_run_is_persisted_with_retryable_status(seeded_connection: sqlite3.Connection) -> None:
    window_start = datetime(2026, 2, 16, 0, 0, 0, tzinfo=UTC)

    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-failure-1",
        meeting_id="meeting-failure-1",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        published_at=window_start + timedelta(days=1),
        claims_with_evidence=1,
        claims_without_evidence=0,
    )

    class _FailingWeeklyEcrAuditJob(WeeklyEcrAuditJob):
        def _compute_claim_metrics(self, selected_publication_ids: tuple[str, ...]) -> tuple[int, int]:
            raise RuntimeError("simulated_claim_metrics_failure")

    job = _FailingWeeklyEcrAuditJob(
        connection=seeded_connection,
        now_provider=lambda: datetime(2026, 2, 24, 8, 0, 0, tzinfo=UTC),
    )
    result = job.run_for_week(audit_week_start_utc=window_start, sample_size=60)

    assert result.status == "failed_retryable"

    failure_row = seeded_connection.execute(
        """
        SELECT status, error_code, error_message
        FROM ecr_audit_runs
        WHERE id = ?
        """,
        (result.run_id,),
    ).fetchone()
    assert failure_row is not None
    assert failure_row[0] == "failed_retryable"
    assert failure_row[1] == "ecr_audit_generation_failed_retryable"
    assert "simulated_claim_metrics_failure" in str(failure_row[2])


def test_backfill_persists_artifacts_for_multiple_weeks_and_trend(seeded_connection: sqlite3.Connection) -> None:
    week_one_start = datetime(2026, 2, 9, 0, 0, 0, tzinfo=UTC)
    week_two_start = datetime(2026, 2, 16, 0, 0, 0, tzinfo=UTC)
    fixed_now = datetime(2026, 2, 24, 10, 0, 0, tzinfo=UTC)

    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-backfill-1",
        meeting_id="meeting-backfill-1",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        published_at=week_one_start + timedelta(days=2),
        claims_with_evidence=1,
        claims_without_evidence=1,
    )
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-backfill-2",
        meeting_id="meeting-backfill-2",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="medium",
        published_at=week_two_start + timedelta(days=3),
        claims_with_evidence=2,
        claims_without_evidence=0,
    )

    job = WeeklyEcrAuditJob(connection=seeded_connection, now_provider=lambda: fixed_now)
    results = job.backfill_weeks(
        audit_week_starts_utc=(week_two_start, week_one_start),
        scheduler_triggered_at_utc=fixed_now,
        sample_size=60,
    )

    assert [result.status for result in results] == ["completed", "completed"]

    rows = seeded_connection.execute(
        """
        SELECT audit_week_start_utc, ecr
        FROM ecr_audit_report_artifacts
        ORDER BY audit_week_start_utc ASC
        """
    ).fetchall()
    assert [row[0] for row in rows] == [week_one_start.isoformat(), week_two_start.isoformat()]

    trend = job.list_weekly_ecr_trend(limit=2)
    assert [item.audit_week_start_utc for item in trend] == [
        week_two_start.isoformat(),
        week_one_start.isoformat(),
    ]


def _insert_publication_bundle(
    connection: sqlite3.Connection,
    *,
    publication_id: str,
    meeting_id: str,
    city_id: str,
    source_id: str,
    confidence_label: str,
    published_at: datetime,
    claims_with_evidence: int,
    claims_without_evidence: int,
) -> None:
    run_id = f"run-{publication_id}"
    publish_outcome_id = f"outcome-{publication_id}"

    connection.execute(
        """
        INSERT OR IGNORE INTO meetings (id, city_id, meeting_uid, title)
        VALUES (?, ?, ?, ?)
        """,
        (meeting_id, city_id, f"uid-{meeting_id}", f"Meeting {meeting_id}"),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO processing_runs (
            id,
            city_id,
            cycle_id,
            status,
            started_at,
            finished_at,
            parser_version,
            source_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            city_id,
            published_at.isoformat(),
            "processed",
            published_at.isoformat(),
            published_at.isoformat(),
            "parser@test",
            "source@test",
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO processing_stage_outcomes (
            id,
            run_id,
            city_id,
            meeting_id,
            stage_name,
            status,
            metadata_json,
            started_at,
            finished_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            publish_outcome_id,
            run_id,
            city_id,
            meeting_id,
            "publish",
            "processed",
            json.dumps({"source_id": source_id}, separators=(",", ":"), sort_keys=True),
            published_at.isoformat(),
            published_at.isoformat(),
        ),
    )
    connection.execute(
        """
        INSERT INTO summary_publications (
            id,
            meeting_id,
            processing_run_id,
            publish_stage_outcome_id,
            version_no,
            publication_status,
            confidence_label,
            summary_text,
            key_decisions_json,
            key_actions_json,
            notable_topics_json,
            published_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            publication_id,
            meeting_id,
            run_id,
            publish_outcome_id,
            1,
            "processed",
            confidence_label,
            f"Summary for {publication_id}",
            "[]",
            "[]",
            "[]",
            published_at.isoformat(),
        ),
    )

    total_claims = claims_with_evidence + claims_without_evidence
    for index in range(total_claims):
        claim_id = f"claim-{publication_id}-{index + 1}"
        connection.execute(
            """
            INSERT INTO publication_claims (id, publication_id, claim_order, claim_text)
            VALUES (?, ?, ?, ?)
            """,
            (
                claim_id,
                publication_id,
                index + 1,
                f"Claim {index + 1} for {publication_id}",
            ),
        )
        if index < claims_with_evidence:
            pointer_id = f"pointer-{publication_id}-{index + 1}"
            connection.execute(
                """
                INSERT INTO claim_evidence_pointers (
                    id,
                    claim_id,
                    artifact_id,
                    section_ref,
                    char_start,
                    char_end,
                    excerpt
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pointer_id,
                    claim_id,
                    f"artifact-{publication_id}",
                    "minutes.section.1",
                    0,
                    50,
                    f"Evidence for {claim_id}",
                ),
            )
