from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from councilsense.app.st017_fixture_scorecard import (
    ST017_PARITY_THRESHOLDS,
    assert_evidence_count_precision,
    assert_grounding_coverage,
    assert_section_completeness,
    assert_specificity_retention,
    assert_topic_semantics,
    build_scorecard,
    load_fixture_manifest,
    load_fixture_text,
    run_fixture_via_local_pipeline,
    serialize_scorecard,
)
from councilsense.db import apply_migrations, seed_city_registry


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _manifest_path() -> Path:
    return _repo_root() / "backend" / "tests" / "fixtures" / "st017_fixture_manifest.json"


def _init_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)
    return connection


def test_st017_manifest_contains_required_fixture_set_and_deterministic_order() -> None:
    entries = load_fixture_manifest(manifest_path=_manifest_path(), repo_root=_repo_root())

    assert len(entries) == 3
    assert [entry.fixture_id for entry in entries] == [
        "st017-eagle-mountain-2024-12-03",
        "st017-riverton-zoning-public-hearing-2025-01-15",
        "st017-highland-work-session-2025-02-10",
    ]

    eagle = entries[0]
    assert eagle.city_id == "city-eagle-mountain-ut"
    assert eagle.meeting_datetime_utc.startswith("2024-12-03")

    first_keys = [entry.stable_fixture_key for entry in entries]
    second_keys = [entry.stable_fixture_key for entry in load_fixture_manifest(manifest_path=_manifest_path(), repo_root=_repo_root())]
    assert first_keys == second_keys


def test_st017_manifest_duplicate_entries_fail_with_clear_error(tmp_path: Path) -> None:
    payload = {
        "manifest_version": "st-017-fixture-manifest-v1",
        "fixtures": [
            {
                "fixture_id": "duplicate-entry",
                "city_id": "city-eagle-mountain-ut",
                "meeting_id": "meeting-dup-a",
                "meeting_uid": "dup-a",
                "meeting_datetime_utc": "2024-12-03T00:00:00Z",
                "source_locator": "fixture://dup-a",
                "source_type": "minutes",
                "structural_profile": "a",
                "fixture_path": "meeting_minutes_baseline_2024-12-03.md",
            },
            {
                "fixture_id": "duplicate-entry",
                "city_id": "city-eagle-mountain-ut",
                "meeting_id": "meeting-dup-b",
                "meeting_uid": "dup-b",
                "meeting_datetime_utc": "2025-01-01T00:00:00Z",
                "source_locator": "fixture://dup-b",
                "source_type": "minutes",
                "structural_profile": "b",
                "fixture_path": "meeting_minutes_baseline_2024-12-03.md",
            },
            {
                "fixture_id": "third-entry",
                "city_id": "city-eagle-mountain-ut",
                "meeting_id": "meeting-third",
                "meeting_uid": "third",
                "meeting_datetime_utc": "2025-02-01T00:00:00Z",
                "source_locator": "fixture://third",
                "source_type": "minutes",
                "structural_profile": "c",
                "fixture_path": "meeting_minutes_baseline_2024-12-03.md",
            },
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate fixture_id"):
        load_fixture_manifest(manifest_path=manifest_path, repo_root=_repo_root())


def test_st017_parity_threshold_constants_and_helpers_cover_all_dimensions() -> None:
    assert ST017_PARITY_THRESHOLDS.section_completeness_min == 1.0
    assert ST017_PARITY_THRESHOLDS.topic_semantics_min > 0
    assert ST017_PARITY_THRESHOLDS.specificity_retention_min == 1.0
    assert ST017_PARITY_THRESHOLDS.grounding_coverage_min == 1.0
    assert ST017_PARITY_THRESHOLDS.evidence_count_precision_min > 0

    assert_section_completeness(1.0)
    assert_topic_semantics(0.75)
    assert_specificity_retention(1.0)
    assert_grounding_coverage(1.0)
    assert_evidence_count_precision(0.6)

    with pytest.raises(AssertionError):
        assert_topic_semantics(0.0)


def test_st017_fixture_set_runs_through_existing_local_pipeline_path_and_generates_deterministic_scorecard(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    old_root = os.environ.get("COUNCILSENSE_LOCAL_ARTIFACT_ROOT")
    os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = str(artifact_root)

    try:
        connection = _init_connection()
        entries = load_fixture_manifest(manifest_path=_manifest_path(), repo_root=_repo_root())

        fixture_texts: dict[str, str] = {}
        runtime_results = []
        for entry in entries:
            text = load_fixture_text(entry=entry, repo_root=_repo_root())
            fixture_texts[entry.fixture_id] = text
            result = run_fixture_via_local_pipeline(
                connection=connection,
                entry=entry,
                fixture_text=text,
                artifact_root=artifact_root,
            )
            runtime_results.append(result)
            assert result.process_status in {"processed", "limited_confidence"}

        for result in runtime_results:
            scores = {
                name: payload
                for name, payload in build_scorecard(
                    manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
                    fixtures=[result],
                    fixture_sources={result.fixture.fixture_id: fixture_texts[result.fixture.fixture_id]},
                    generated_at_utc=datetime(2026, 3, 3, 0, 0, 0, tzinfo=UTC),
                )["fixtures"][0]["dimensions"].items()
            }
            assert set(scores) == {
                "section_completeness",
                "topic_semantics",
                "specificity_retention",
                "grounding_coverage",
                "evidence_count_precision",
            }

        scorecard_one = build_scorecard(
            manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
            fixtures=runtime_results,
            fixture_sources=fixture_texts,
            generated_at_utc=datetime(2026, 3, 3, 0, 0, 0, tzinfo=UTC),
        )
        scorecard_two = build_scorecard(
            manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
            fixtures=runtime_results,
            fixture_sources=fixture_texts,
            generated_at_utc=datetime(2026, 3, 3, 0, 0, 0, tzinfo=UTC),
        )

        assert scorecard_one == scorecard_two
        assert serialize_scorecard(scorecard_one) == serialize_scorecard(scorecard_two)
        assert scorecard_one["schema_version"] == "st-017-fixture-scorecard-v1"
        assert scorecard_one["fixture_count"] == 3
    finally:
        if old_root is None:
            os.environ.pop("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", None)
        else:
            os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = old_root