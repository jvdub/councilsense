from __future__ import annotations

import sqlite3
from collections.abc import Generator

import pytest

from councilsense.db import apply_migrations, get_migration_status


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_migration_status_and_apply_are_idempotent(connection: sqlite3.Connection) -> None:
    before = get_migration_status(connection)
    assert "0001_city_registry.sql" in before.pending
    assert "0002_meetings_city_linkage.sql" in before.pending
    assert "0003_pipeline_run_lifecycle.sql" in before.pending
    assert "0004_summary_evidence_persistence.sql" in before.pending
    assert "0005_summary_publish_append_only_guards.sql" in before.pending
    assert "0006_meeting_reader_query_indexes.sql" in before.pending
    assert "0007_source_health_failure_context.sql" in before.pending
    assert "0008_processing_run_provenance.sql" in before.pending
    assert "0009_manual_review_needed_status.sql" in before.pending
    assert "0010_notification_outbox_and_attempt_schema.sql" in before.pending
    assert "0011_governance_request_data_model.sql" in before.pending
    assert "0012_governance_export_artifacts.sql" in before.pending
    assert "0013_notification_dlq_schema_and_terminal_state.sql" in before.pending
    assert "0014_st015_ecr_audit_job_and_report_artifacts.sql" in before.pending
    assert "0015_st015_reviewer_queue_and_outcome_capture.sql" in before.pending
    assert "0016_notification_dlq_replay_audit_and_linkage.sql" in before.pending
    assert "0017_st015_confidence_calibration_policy_controls.sql" in before.pending
    assert "0018_st015_quality_ops_dashboard_and_target_validation.sql" in before.pending
    assert "0019_st016_parser_version_and_drift_event_model.sql" in before.pending
    assert "0020_st016_source_freshness_regression_alerting.sql" in before.pending
    assert "0021_st024_canonical_documents_authority_metadata.sql" in before.pending
    assert "0022_st024_canonical_document_artifacts_lineage.sql" in before.pending
    assert "0023_st024_canonical_document_artifacts_lineage.sql" in before.pending
    assert "0023_st024_canonical_document_spans.sql" in before.pending
    assert "0024_st026_claim_evidence_linkage_contract.sql" in before.pending
    assert "0025_st029_pipeline_dlq_contract.sql" in before.pending
    assert "0026_st029_pipeline_replay_audit_history.sql" in before.pending

    applied_once = apply_migrations(connection)
    assert applied_once == (
        "0001_city_registry.sql",
        "0002_meetings_city_linkage.sql",
        "0003_pipeline_run_lifecycle.sql",
        "0004_summary_evidence_persistence.sql",
        "0005_summary_publish_append_only_guards.sql",
        "0006_meeting_reader_query_indexes.sql",
        "0007_source_health_failure_context.sql",
        "0008_processing_run_provenance.sql",
        "0009_manual_review_needed_status.sql",
        "0010_notification_outbox_and_attempt_schema.sql",
        "0011_governance_request_data_model.sql",
        "0012_governance_export_artifacts.sql",
        "0013_notification_dlq_schema_and_terminal_state.sql",
        "0014_st015_ecr_audit_job_and_report_artifacts.sql",
        "0015_st015_reviewer_queue_and_outcome_capture.sql",
        "0016_notification_dlq_replay_audit_and_linkage.sql",
        "0017_st015_confidence_calibration_policy_controls.sql",
        "0018_st015_quality_ops_dashboard_and_target_validation.sql",
        "0019_st016_parser_version_and_drift_event_model.sql",
        "0020_st016_source_freshness_regression_alerting.sql",
        "0021_st024_canonical_documents_authority_metadata.sql",
        "0022_st024_canonical_document_artifacts_lineage.sql",
        "0023_st024_canonical_document_artifacts_lineage.sql",
        "0023_st024_canonical_document_spans.sql",
        "0024_st026_claim_evidence_linkage_contract.sql",
        "0025_st029_pipeline_dlq_contract.sql",
        "0026_st029_pipeline_replay_audit_history.sql",
    )

    after_first_apply = get_migration_status(connection)
    assert after_first_apply.pending == ()
    assert "0001_city_registry.sql" in after_first_apply.applied

    applied_twice = apply_migrations(connection)
    assert applied_twice == ()


def test_city_tables_and_indexes_exist(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)

    table_names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {
        "cities",
        "city_sources",
        "meetings",
        "processing_runs",
        "processing_stage_outcomes",
        "summary_publications",
        "publication_claims",
        "claim_evidence_pointers",
        "notification_outbox",
        "notification_delivery_attempts",
        "notification_delivery_dlq",
        "notification_dlq_replay_audit",
        "governance_export_artifacts",
        "processing_run_sources",
        "parser_drift_events",
        "source_freshness_breach_events",
        "reviewer_queue_items",
        "reviewer_queue_events",
        "confidence_calibration_policies",
        "quality_ops_weekly_reports",
        "canonical_documents",
        "canonical_document_artifacts",
        "pipeline_dlq_entries",
        "pipeline_replay_audit_events",
        "schema_migrations",
    }.issubset(table_names)

    index_names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_cities_enabled_priority" in index_names
    assert "idx_city_sources_city_enabled" in index_names
    assert "idx_city_sources_health_last_success" in index_names
    assert "idx_meetings_city_id" in index_names
    assert "idx_processing_runs_city_status" in index_names
    assert "idx_processing_runs_cycle_city" in index_names
    assert "idx_processing_stage_outcomes_run_city" in index_names
    assert "idx_summary_publications_meeting_published" in index_names
    assert "idx_summary_publications_status" in index_names
    assert "idx_publication_claims_publication_order" in index_names
    assert "idx_claim_evidence_claim_id" in index_names
    assert "idx_claim_evidence_artifact" in index_names
    assert "idx_claim_evidence_document_id" in index_names
    assert "idx_claim_evidence_span_id" in index_names
    assert "idx_meetings_city_created_id" in index_names
    assert "idx_summary_publications_meeting_published_id" in index_names
    assert "idx_notification_outbox_status_next_retry" in index_names
    assert "idx_notification_outbox_city_meeting" in index_names
    assert "idx_notification_outbox_user_created" in index_names
    assert "idx_notification_delivery_attempts_outbox_attempted" in index_names
    assert "idx_notification_delivery_attempts_outcome_attempted" in index_names
    assert "idx_notification_delivery_dlq_city" in index_names
    assert "idx_notification_delivery_dlq_source" in index_names
    assert "idx_notification_delivery_dlq_run" in index_names
    assert "idx_notification_delivery_dlq_message" in index_names
    assert "idx_notification_delivery_dlq_replay_idempotency" in index_names
    assert "idx_notification_delivery_dlq_replay_outbox" in index_names
    assert "idx_notification_dlq_replay_audit_dlq_created" in index_names
    assert "idx_notification_dlq_replay_audit_source_created" in index_names
    assert "idx_governance_export_artifacts_user_created" in index_names
    assert "idx_processing_run_sources_city_source_recorded" in index_names
    assert "idx_processing_run_sources_run_source" in index_names
    assert "idx_parser_drift_events_city_detected" in index_names
    assert "idx_parser_drift_events_source_detected" in index_names
    assert "idx_parser_drift_events_current_version_detected" in index_names
    assert "idx_parser_drift_events_baseline_version_detected" in index_names
    assert "idx_source_freshness_breach_events_city_detected" in index_names
    assert "idx_source_freshness_breach_events_source_detected" in index_names
    assert "idx_source_freshness_breach_events_severity_detected" in index_names
    assert "idx_source_freshness_breach_events_suppressed_detected" in index_names
    assert "idx_canonical_documents_single_active_revision" in index_names
    assert "idx_canonical_documents_meeting_kind_revision" in index_names
    assert "idx_canonical_documents_authority" in index_names
    assert "idx_canonical_document_artifacts_document_checksum" in index_names
    assert "idx_canonical_document_artifacts_root_checksum" in index_names
    assert "idx_canonical_document_artifacts_lineage_parent" in index_names
    assert "idx_pipeline_dlq_entries_city_status" in index_names
    assert "idx_pipeline_dlq_entries_run" in index_names
    assert "idx_pipeline_dlq_entries_source" in index_names
    assert "idx_pipeline_dlq_entries_meeting" in index_names
    assert "idx_pipeline_dlq_entries_stage_status" in index_names
    assert "idx_pipeline_replay_audit_dlq_created" in index_names
    assert "idx_pipeline_replay_audit_city_created" in index_names
    assert "idx_pipeline_replay_audit_run_created" in index_names
    assert "idx_pipeline_replay_audit_meeting_created" in index_names
    assert "idx_pipeline_replay_audit_stage_source_created" in index_names
    assert "idx_pipeline_replay_audit_actor_created" in index_names


def test_city_and_source_constraints_are_enforced(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("city-1", "seattle-wa", "Seattle", "WA", "America/Los_Angeles", 2, 1),
        )

    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("city-1", "seattle-wa", "Seattle", "WA", "America/Los_Angeles", 1, 1),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO city_sources (id, city_id, source_type, source_url, parser_name, parser_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("source-1", "missing-city", "minutes", "https://example.gov/minutes", "parser", "v1"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO city_sources (id, city_id, source_type, source_url, parser_name, parser_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("source-1", "city-1", "minutes", "https://example.gov/minutes", "", "v1"),
        )

    connection.execute(
        """
        INSERT INTO city_sources (
            id,
            city_id,
            source_type,
            source_url,
            parser_name,
            parser_version,
            enabled,
            health_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "source-1",
            "city-1",
            "minutes",
            "https://example.gov/minutes",
            "minutes-parser",
            "v1",
            1,
            "unknown",
        ),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO city_sources (id, city_id, source_type, source_url, parser_name, parser_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "source-2",
                "city-1",
                "minutes",
                "https://example.gov/minutes",
                "minutes-parser",
                "v1",
            ),
        )

    enabled_rows = connection.execute(
        """
        SELECT c.slug, cs.source_type
        FROM cities c
        JOIN city_sources cs ON cs.city_id = c.id
        WHERE c.enabled = 1 AND cs.enabled = 1
        """
    ).fetchall()
    assert enabled_rows == [("seattle-wa", "minutes")]
