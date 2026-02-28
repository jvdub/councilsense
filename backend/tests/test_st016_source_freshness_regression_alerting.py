from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator

import pytest

from councilsense.app.source_freshness_policy import (
    SourceFreshnessEvaluationInput,
    SourceFreshnessPolicyConfig,
    SourceFreshnessThresholdConfig,
    SourceMaintenanceWindow,
    evaluate_source_freshness,
)
from councilsense.db import PILOT_CITY_ID, PILOT_CITY_SOURCE_ID, ProcessingRunRepository, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_source_freshness_policy_triggers_warning_and_critical_by_age_thresholds() -> None:
    config = SourceFreshnessPolicyConfig(
        default_thresholds=SourceFreshnessThresholdConfig(warning_age_hours=24.0, critical_age_hours=48.0)
    )

    warning = evaluate_source_freshness(
        policy_input=SourceFreshnessEvaluationInput(
            city_id=PILOT_CITY_ID,
            source_id=PILOT_CITY_SOURCE_ID,
            source_type="minutes",
            last_success_at="2026-02-27 00:00:00",
            evaluated_at="2026-02-28T06:00:00Z",
        ),
        config=config,
    )
    assert warning is not None
    assert warning.severity == "warning"

    critical = evaluate_source_freshness(
        policy_input=SourceFreshnessEvaluationInput(
            city_id=PILOT_CITY_ID,
            source_id=PILOT_CITY_SOURCE_ID,
            source_type="minutes",
            last_success_at="2026-02-25 00:00:00",
            evaluated_at="2026-02-28T06:00:00Z",
        ),
        config=config,
    )
    assert critical is not None
    assert critical.severity == "critical"


def test_source_freshness_policy_distinguishes_low_frequency_sources_with_profile_overrides() -> None:
    config = SourceFreshnessPolicyConfig(
        default_thresholds=SourceFreshnessThresholdConfig(warning_age_hours=24.0, critical_age_hours=48.0),
        profile_thresholds={
            "weekly": SourceFreshnessThresholdConfig(warning_age_hours=168.0, critical_age_hours=336.0),
        },
        source_id_profile_overrides={PILOT_CITY_SOURCE_ID: "weekly"},
    )

    decision = evaluate_source_freshness(
        policy_input=SourceFreshnessEvaluationInput(
            city_id=PILOT_CITY_ID,
            source_id=PILOT_CITY_SOURCE_ID,
            source_type="minutes",
            last_success_at="2026-02-21 01:00:00",
            evaluated_at="2026-02-28T00:00:00Z",
        ),
        config=config,
    )
    assert decision is None


def test_source_freshness_breach_events_include_triage_payload_and_parser_drift_correlation(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)

    connection.execute(
        "UPDATE city_sources SET last_success_at = '2026-02-27 00:00:00' WHERE id = ?",
        (PILOT_CITY_SOURCE_ID,),
    )
    repository.create_pending_run(
        run_id="run-st016-freshness-baseline",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-27T01:00:00Z",
        freshness_evaluated_at="2026-02-27T01:00:00Z",
    )

    connection.execute(
        "UPDATE city_sources SET parser_version = 'v2', last_success_at = '2026-02-25 00:00:00' WHERE id = ?",
        (PILOT_CITY_SOURCE_ID,),
    )

    repository.create_pending_run(
        run_id="run-st016-freshness-breach",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T12:00:00Z",
        freshness_evaluated_at="2026-02-28T12:00:00Z",
    )

    events = repository.list_source_freshness_breach_events(city_id=PILOT_CITY_ID)
    assert len(events) == 1

    event = events[0]
    assert event.event_schema_version == "st016.source_freshness_breach_event.v1"
    assert event.severity == "critical"
    assert event.threshold_age_hours == 48.0
    assert event.last_success_at == "2026-02-25 00:00:00"
    assert event.parser_drift_event_id is not None

    payload = json.loads(event.triage_payload_json)
    assert payload["alert_class"] == "source_freshness"
    assert payload["city_id"] == PILOT_CITY_ID
    assert payload["source_id"] == PILOT_CITY_SOURCE_ID
    assert payload["run_id"] == "run-st016-freshness-breach"
    assert payload["last_success_at"] == "2026-02-25 00:00:00"
    assert payload["parser_drift_event_id"] == event.parser_drift_event_id


def test_source_freshness_maintenance_window_suppression_preserves_unscheduled_regressions(
    connection: sqlite3.Connection,
) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    repository = ProcessingRunRepository(connection)

    connection.execute(
        "UPDATE city_sources SET last_success_at = '2026-02-25 00:00:00' WHERE id = ?",
        (PILOT_CITY_SOURCE_ID,),
    )

    policy = SourceFreshnessPolicyConfig(
        maintenance_windows=(
            SourceMaintenanceWindow(
                window_name="planned-source-upgrade",
                starts_at="2026-02-28T00:00:00Z",
                ends_at="2026-02-28T06:00:00Z",
                city_id=PILOT_CITY_ID,
                source_id=PILOT_CITY_SOURCE_ID,
            ),
        ),
    )

    repository.create_pending_run(
        run_id="run-st016-suppressed",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T04:00:00Z",
        freshness_policy_config=policy,
        freshness_evaluated_at="2026-02-28T04:00:00Z",
    )

    repository.create_pending_run(
        run_id="run-st016-unsuppressed",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-02-28T10:00:00Z",
        freshness_policy_config=policy,
        freshness_evaluated_at="2026-02-28T10:00:00Z",
    )

    all_events = repository.list_source_freshness_breach_events(city_id=PILOT_CITY_ID)
    assert len(all_events) == 2

    suppressed_events = repository.list_source_freshness_breach_events(city_id=PILOT_CITY_ID, suppressed=True)
    assert len(suppressed_events) == 1
    assert suppressed_events[0].run_id == "run-st016-suppressed"
    assert suppressed_events[0].suppression_reason == "planned_maintenance_window"

    unsuppressed_events = repository.list_source_freshness_breach_events(city_id=PILOT_CITY_ID, suppressed=False)
    assert len(unsuppressed_events) == 1
    assert unsuppressed_events[0].run_id == "run-st016-unsuppressed"
