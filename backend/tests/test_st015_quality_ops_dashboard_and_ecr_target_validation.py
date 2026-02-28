from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import json
import sqlite3

import pytest

from councilsense.app.quality_ops_dashboard import QualityOpsDashboardService
from councilsense.app.reviewer_queue import ReviewerQueueService
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


def test_quality_dashboard_queries_align_with_audit_reviewer_and_calibration_outputs(
    seeded_connection: sqlite3.Connection,
) -> None:
    week_one_start = datetime(2026, 2, 9, 0, 0, tzinfo=UTC)
    week_two_start = datetime(2026, 2, 16, 0, 0, tzinfo=UTC)

    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-week1-low-evidence",
        meeting_id="meeting-week1-low-evidence",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        publication_status="processed",
        run_status="processed",
        published_at=week_one_start + timedelta(days=1),
        claims_with_evidence=1,
        claims_without_evidence=1,
    )
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-week1-clean",
        meeting_id="meeting-week1-clean",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        publication_status="processed",
        run_status="processed",
        published_at=week_one_start + timedelta(days=2),
        claims_with_evidence=2,
        claims_without_evidence=0,
    )

    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-week2-low-confidence",
        meeting_id="meeting-week2-low-confidence",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="limited_confidence",
        publication_status="limited_confidence",
        run_status="manual_review_needed",
        published_at=week_two_start + timedelta(days=1),
        claims_with_evidence=1,
        claims_without_evidence=1,
    )
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-week2-low-evidence",
        meeting_id="meeting-week2-low-evidence",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        publication_status="processed",
        run_status="processed",
        published_at=week_two_start + timedelta(days=2),
        claims_with_evidence=1,
        claims_without_evidence=1,
    )
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-week2-clean",
        meeting_id="meeting-week2-clean",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        publication_status="processed",
        run_status="processed",
        published_at=week_two_start + timedelta(days=3),
        claims_with_evidence=2,
        claims_without_evidence=0,
    )

    _insert_audit_artifact(
        seeded_connection,
        run_id="ecrrun-week1",
        window_start=week_one_start,
        selected_publication_ids=("pub-week1-low-evidence", "pub-week1-clean"),
        ecr=0.9,
        claim_count=10,
        claims_with_evidence_count=9,
    )
    _insert_audit_artifact(
        seeded_connection,
        run_id="ecrrun-week2",
        window_start=week_two_start,
        selected_publication_ids=("pub-week2-low-confidence", "pub-week2-low-evidence", "pub-week2-clean"),
        ecr=0.8,
        claim_count=10,
        claims_with_evidence_count=8,
    )

    reviewer_service = ReviewerQueueService(connection=seeded_connection)
    week_one_items = reviewer_service.seed_from_ecr_audit_run(run_id="ecrrun-week1")
    week_two_items = reviewer_service.seed_from_ecr_audit_run(run_id="ecrrun-week2")

    reviewer_service.start_review(
        queue_item_id=week_one_items[0].id,
        reviewer_user_id="reviewer-week1",
        reviewer_roles=("ops-quality-reviewer",),
    )
    reviewer_service.record_outcome(
        queue_item_id=week_one_items[0].id,
        reviewer_user_id="reviewer-week1",
        reviewer_roles=("ops-quality-reviewer",),
        outcome_code="false_positive",
        recommended_action="none",
        outcome_notes="Evidence pointer present in source transcript.",
    )

    reviewer_service.start_review(
        queue_item_id=week_two_items[0].id,
        reviewer_user_id="reviewer-week2",
        reviewer_roles=("ops-quality-reviewer",),
    )
    reviewer_service.record_outcome(
        queue_item_id=week_two_items[0].id,
        reviewer_user_id="reviewer-week2",
        reviewer_roles=("ops-quality-reviewer",),
        outcome_code="requires_reprocess",
        recommended_action="rerun_pipeline",
        outcome_notes="Missing evidence pointer on one claim.",
    )

    dashboard_service = QualityOpsDashboardService(
        connection=seeded_connection,
        now_provider=lambda: datetime(2026, 2, 25, 10, 0, tzinfo=UTC),
    )
    dashboard_service.refresh_recent_reports(limit=2)
    reports = dashboard_service.list_weekly_reports(limit=2)

    assert [report.audit_week_start_utc for report in reports] == [
        week_two_start.isoformat(),
        week_one_start.isoformat(),
    ]

    week_two_report = reports[0]
    assert week_two_report.ecr == 0.8
    assert week_two_report.target_attained is False
    assert week_two_report.target_status == "below_target"
    assert week_two_report.low_confidence_labeling_rate == 0.3333
    assert week_two_report.reviewer_queue_item_count == 2
    assert week_two_report.reviewer_queue_resolved_count == 1
    assert week_two_report.reviewer_queue_closure_rate == 0.5
    assert week_two_report.reviewer_backlog_open_count == 1
    assert week_two_report.reviewer_outcome_counts["requires_reprocess"] == 1
    assert week_two_report.calibration_policy_version == "st015-calibration-policy-v1-default"


def test_weekly_quality_report_generation_smoke_and_retention(
    seeded_connection: sqlite3.Connection,
) -> None:
    week_start = datetime(2026, 2, 23, 0, 0, tzinfo=UTC)
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-smoke-1",
        meeting_id="meeting-smoke-1",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        publication_status="processed",
        run_status="processed",
        published_at=week_start + timedelta(days=1),
        claims_with_evidence=2,
        claims_without_evidence=0,
    )
    _insert_audit_artifact(
        seeded_connection,
        run_id="ecrrun-smoke",
        window_start=week_start,
        selected_publication_ids=("pub-smoke-1",),
        ecr=0.9,
        claim_count=10,
        claims_with_evidence_count=9,
    )

    service = QualityOpsDashboardService(
        connection=seeded_connection,
        now_provider=lambda: datetime(2026, 3, 2, 8, 0, tzinfo=UTC),
    )
    report = service.upsert_weekly_report(audit_week_start_utc=week_start)
    second_report = service.upsert_weekly_report(audit_week_start_utc=week_start)

    assert report.target_status == "met"
    assert second_report.target_status == "met"

    row = seeded_connection.execute(
        """
        SELECT target_status, summary_json
        FROM quality_ops_weekly_reports
        WHERE audit_week_start_utc = ?
        """,
        (week_start.isoformat(),),
    ).fetchone()
    assert row is not None
    assert row[0] == "met"

    payload = json.loads(str(row[1]))
    assert payload["report_version"] == "st-015-quality-ops-weekly-report-v1"
    assert payload["target"]["target_attained"] is True
    assert payload["metrics"]["reviewer_queue_closure_rate"] == 0.0

    count_row = seeded_connection.execute(
        """
        SELECT COUNT(*)
        FROM quality_ops_weekly_reports
        WHERE audit_week_start_utc = ?
        """,
        (week_start.isoformat(),),
    ).fetchone()
    assert count_row == (1,)


def test_below_target_week_triggers_escalation_owner_and_timestamp(
    seeded_connection: sqlite3.Connection,
) -> None:
    week_start = datetime(2026, 2, 2, 0, 0, tzinfo=UTC)
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-escalate-1",
        meeting_id="meeting-escalate-1",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="limited_confidence",
        publication_status="limited_confidence",
        run_status="manual_review_needed",
        published_at=week_start + timedelta(days=1),
        claims_with_evidence=1,
        claims_without_evidence=2,
    )
    _insert_audit_artifact(
        seeded_connection,
        run_id="ecrrun-escalate",
        window_start=week_start,
        selected_publication_ids=("pub-escalate-1",),
        ecr=0.42,
        claim_count=12,
        claims_with_evidence_count=5,
    )

    service = QualityOpsDashboardService(
        connection=seeded_connection,
        now_provider=lambda: datetime(2026, 2, 10, 9, 45, tzinfo=UTC),
    )
    report = service.upsert_weekly_report(
        audit_week_start_utc=week_start,
        ecr_target=0.85,
        escalation_owner_role="ops-quality-oncall",
    )

    assert report.target_attained is False
    assert report.target_status == "below_target"
    assert report.escalation_owner_role == "ops-quality-oncall"
    assert report.escalation_triggered_at_utc == datetime(2026, 2, 10, 9, 45, tzinfo=UTC).isoformat()

    row = seeded_connection.execute(
        """
        SELECT target_status, escalation_owner_role, escalation_triggered_at_utc
        FROM quality_ops_weekly_reports
        WHERE audit_week_start_utc = ?
        """,
        (week_start.isoformat(),),
    ).fetchone()
    assert row == (
        "below_target",
        "ops-quality-oncall",
        datetime(2026, 2, 10, 9, 45, tzinfo=UTC).isoformat(),
    )


def _insert_audit_artifact(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    window_start: datetime,
    selected_publication_ids: tuple[str, ...],
    ecr: float,
    claim_count: int,
    claims_with_evidence_count: int,
) -> None:
    window_end = window_start + timedelta(days=7)
    generated_at = window_end + timedelta(hours=1)
    content_json = json.dumps(
        {
            "report_version": "st-015-weekly-audit-report-v1",
            "formula_version": "st-015-ecr-formula-v1",
            "audit_week_start_utc": window_start.isoformat(),
            "audit_week_end_utc": window_end.isoformat(),
            "selected_publication_ids": list(selected_publication_ids),
        },
        separators=(",", ":"),
        sort_keys=True,
    )

    with connection:
        connection.execute(
            """
            INSERT INTO ecr_audit_runs (
                id,
                audit_week_start_utc,
                audit_week_end_utc,
                status,
                owner_role,
                scheduler_triggered_at_utc,
                started_at_utc,
                finished_at_utc,
                formula_version,
                report_version,
                sample_size_requested,
                sample_size_actual,
                eligible_frame_count,
                malformed_exclusion_count,
                report_artifact_uri,
                runtime_metadata_json
            )
            VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                window_start.isoformat(),
                window_end.isoformat(),
                "ops-quality-oncall",
                generated_at.isoformat(),
                generated_at.isoformat(),
                generated_at.isoformat(),
                "st-015-ecr-formula-v1",
                "st-015-weekly-audit-report-v1",
                len(selected_publication_ids),
                len(selected_publication_ids),
                len(selected_publication_ids),
                0,
                f"quality/ecr-audits/{window_start.date().isoformat()}/weekly-ecr-report.json",
                "{}",
            ),
        )
        connection.execute(
            """
            INSERT INTO ecr_audit_report_artifacts (
                id,
                run_id,
                audit_week_start_utc,
                audit_week_end_utc,
                artifact_uri,
                report_version,
                formula_version,
                generated_at_utc,
                ecr,
                claim_count,
                claims_with_evidence_count,
                content_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"ecrartifact-{run_id}",
                run_id,
                window_start.isoformat(),
                window_end.isoformat(),
                f"quality/ecr-audits/{window_start.date().isoformat()}/weekly-ecr-report.json",
                "st-015-weekly-audit-report-v1",
                "st-015-ecr-formula-v1",
                generated_at.isoformat(),
                ecr,
                claim_count,
                claims_with_evidence_count,
                content_json,
            ),
        )


def _insert_publication_bundle(
    connection: sqlite3.Connection,
    *,
    publication_id: str,
    meeting_id: str,
    city_id: str,
    source_id: str,
    confidence_label: str,
    publication_status: str,
    run_status: str,
    published_at: datetime,
    claims_with_evidence: int,
    claims_without_evidence: int,
) -> None:
    run_id = f"run-{publication_id}"
    publish_outcome_id = f"outcome-{publication_id}"

    with connection:
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
                run_status,
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
                publication_status,
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
                (claim_id, publication_id, index + 1, f"Claim {index + 1} for {publication_id}"),
            )
            if index < claims_with_evidence:
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
                        f"pointer-{claim_id}",
                        claim_id,
                        f"artifact-{publication_id}",
                        "minutes.section.1",
                        0,
                        20,
                        "evidence excerpt",
                    ),
                )
