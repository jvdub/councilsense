from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import sqlite3

import pytest

from councilsense.app.reviewer_queue import (
    ReviewerQueueAuthorizationError,
    ReviewerQueueService,
)
from councilsense.app.scheduler import run_weekly_ecr_audit_cycle
from councilsense.db import PILOT_CITY_ID, PILOT_CITY_SOURCE_ID, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> sqlite3.Connection:
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


def test_seed_from_ecr_run_enqueues_low_confidence_and_low_evidence_candidates(
    seeded_connection: sqlite3.Connection,
) -> None:
    window_start = datetime(2026, 2, 16, 0, 0, tzinfo=UTC)
    run_id = "ecrrun-review-1"

    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-review-low-evidence",
        meeting_id="meeting-review-low-evidence",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        publication_status="processed",
        run_status="processed",
        published_at=window_start + timedelta(days=1),
        claims_with_evidence=1,
        claims_without_evidence=1,
    )
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-review-low-confidence",
        meeting_id="meeting-review-low-confidence",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="limited_confidence",
        publication_status="limited_confidence",
        run_status="manual_review_needed",
        published_at=window_start + timedelta(days=2),
        claims_with_evidence=1,
        claims_without_evidence=0,
    )
    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-review-clean",
        meeting_id="meeting-review-clean",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="high",
        publication_status="processed",
        run_status="processed",
        published_at=window_start + timedelta(days=3),
        claims_with_evidence=2,
        claims_without_evidence=0,
    )

    _insert_audit_artifact(
        seeded_connection,
        run_id=run_id,
        window_start=window_start,
        selected_publication_ids=(
            "pub-review-low-evidence",
            "pub-review-low-confidence",
            "pub-review-clean",
        ),
    )

    service = ReviewerQueueService(connection=seeded_connection)
    enqueued = service.seed_from_ecr_audit_run(run_id=run_id)

    assert [item.publication_id for item in enqueued] == [
        "pub-review-low-evidence",
        "pub-review-low-confidence",
    ]

    low_evidence = next(item for item in enqueued if item.publication_id == "pub-review-low-evidence")
    assert low_evidence.status == "open"
    assert set(low_evidence.reason_codes) == {"low_evidence"}
    assert low_evidence.claim_count == 2
    assert low_evidence.claims_with_evidence_count == 1

    low_confidence = next(item for item in enqueued if item.publication_id == "pub-review-low-confidence")
    assert low_confidence.status == "open"
    assert set(low_confidence.reason_codes) == {"low_confidence", "policy_rule"}
    assert low_confidence.claim_count == 1
    assert low_confidence.claims_with_evidence_count == 1

    events = seeded_connection.execute(
        """
        SELECT event_type, reason_codes_json, to_status
        FROM reviewer_queue_events
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()
    assert len(events) == 2
    assert all(row[0] == "enqueued" for row in events)
    assert all(row[2] == "open" for row in events)


def test_weekly_ecr_cycle_seeds_reviewer_queue_for_low_confidence_output(
    seeded_connection: sqlite3.Connection,
) -> None:
    audit_week_start = datetime(2026, 2, 23, 0, 0, tzinfo=UTC)
    scheduler_triggered_at = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)

    _insert_publication_bundle(
        seeded_connection,
        publication_id="pub-scheduler-low-confidence",
        meeting_id="meeting-scheduler-low-confidence",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="limited_confidence",
        publication_status="limited_confidence",
        run_status="manual_review_needed",
        published_at=audit_week_start + timedelta(days=1),
        claims_with_evidence=1,
        claims_without_evidence=1,
    )

    result = run_weekly_ecr_audit_cycle(
        connection=seeded_connection,
        scheduler_triggered_at_utc=scheduler_triggered_at,
    )
    assert result.status == "completed"

    queue_rows = seeded_connection.execute(
        """
        SELECT publication_id, status
        FROM reviewer_queue_items
        WHERE audit_run_id = ?
        ORDER BY publication_id ASC
        """,
        (result.run_id,),
    ).fetchall()
    assert queue_rows == [("pub-scheduler-low-confidence", "open")]


def test_reviewer_can_transition_queue_item_and_capture_outcome_history(
    seeded_connection: sqlite3.Connection,
) -> None:
    queue_item_id = _seed_single_queue_item(seeded_connection)
    service = ReviewerQueueService(connection=seeded_connection)

    in_progress = service.start_review(
        queue_item_id=queue_item_id,
        reviewer_user_id="reviewer-1",
        reviewer_roles=("ops-quality-reviewer",),
    )
    assert in_progress.status == "in_progress"
    assert in_progress.first_in_progress_at is not None
    assert in_progress.resolved_at is None

    resolved = service.record_outcome(
        queue_item_id=queue_item_id,
        reviewer_user_id="reviewer-1",
        reviewer_roles=("ops-quality-reviewer",),
        outcome_code="requires_reprocess",
        recommended_action="rerun_pipeline",
        outcome_notes="Evidence pointers incomplete for one claim.",
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None
    assert resolved.outcome_code == "requires_reprocess"
    assert resolved.recommended_action == "rerun_pipeline"
    assert resolved.last_reviewed_by == "reviewer-1"

    history = service.export_review_history(queue_item_id=queue_item_id)
    assert [event.event_type for event in history] == [
        "enqueued",
        "status_transition",
        "outcome_captured",
        "status_transition",
    ]
    assert history[-1].to_status == "resolved"
    assert history[-1].outcome_code == "requires_reprocess"


def test_reviewer_actions_require_reviewer_role(seeded_connection: sqlite3.Connection) -> None:
    queue_item_id = _seed_single_queue_item(seeded_connection)
    service = ReviewerQueueService(connection=seeded_connection)

    with pytest.raises(ReviewerQueueAuthorizationError, match="reviewer role required"):
        service.start_review(
            queue_item_id=queue_item_id,
            reviewer_user_id="user-no-role",
            reviewer_roles=("member",),
        )

    with pytest.raises(ReviewerQueueAuthorizationError, match="reviewer role required"):
        service.record_outcome(
            queue_item_id=queue_item_id,
            reviewer_user_id="user-no-role",
            reviewer_roles=("member",),
            outcome_code="confirmed_issue",
            recommended_action="none",
            outcome_notes=None,
        )


def test_outcome_taxonomy_constraints_reject_invalid_values(seeded_connection: sqlite3.Connection) -> None:
    queue_item_id = _seed_single_queue_item(seeded_connection)
    service = ReviewerQueueService(connection=seeded_connection)

    service.start_review(
        queue_item_id=queue_item_id,
        reviewer_user_id="reviewer-taxonomy",
        reviewer_roles=("ops-quality-reviewer",),
    )

    with pytest.raises(ValueError, match="outcome_code must be one of"):
        service.record_outcome(
            queue_item_id=queue_item_id,
            reviewer_user_id="reviewer-taxonomy",
            reviewer_roles=("ops-quality-reviewer",),
            outcome_code="invalid_outcome",
            recommended_action="none",
            outcome_notes=None,
        )

    with pytest.raises(sqlite3.IntegrityError):
        seeded_connection.execute(
            """
            INSERT INTO reviewer_queue_events (
                id,
                queue_item_id,
                event_type,
                outcome_code,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "rqevt-invalid-taxonomy",
                queue_item_id,
                "outcome_captured",
                "not_allowed",
                datetime(2026, 2, 28, 13, 0, tzinfo=UTC).isoformat(),
            ),
        )


def _seed_single_queue_item(connection: sqlite3.Connection) -> str:
    window_start = datetime(2026, 2, 16, 0, 0, tzinfo=UTC)
    run_id = "ecrrun-review-single"
    publication_id = "pub-review-single"

    _insert_publication_bundle(
        connection,
        publication_id=publication_id,
        meeting_id="meeting-review-single",
        city_id=PILOT_CITY_ID,
        source_id=PILOT_CITY_SOURCE_ID,
        confidence_label="limited_confidence",
        publication_status="limited_confidence",
        run_status="manual_review_needed",
        published_at=window_start + timedelta(days=1),
        claims_with_evidence=1,
        claims_without_evidence=1,
    )
    _insert_audit_artifact(
        connection,
        run_id=run_id,
        window_start=window_start,
        selected_publication_ids=(publication_id,),
    )

    service = ReviewerQueueService(connection=connection)
    enqueued = service.seed_from_ecr_audit_run(run_id=run_id)
    assert len(enqueued) == 1
    return enqueued[0].id


def _insert_audit_artifact(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    window_start: datetime,
    selected_publication_ids: tuple[str, ...],
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
                0.8,
                10,
                8,
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
