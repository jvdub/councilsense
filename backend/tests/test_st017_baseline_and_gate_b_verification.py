from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from councilsense.app.st017_fixture_scorecard import (
    ST017_VARIANCE_BOUNDS,
    build_baseline_snapshot,
    build_gate_b_verification,
    build_scorecard,
    load_fixture_manifest,
    load_fixture_text,
    run_fixture_via_local_pipeline,
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


def _run_fixture_cohort(*, artifact_root: Path) -> tuple[dict[str, str], list[object]]:
    connection = _init_connection()
    entries = load_fixture_manifest(manifest_path=_manifest_path(), repo_root=_repo_root())

    fixture_texts: dict[str, str] = {}
    runtime_results: list[object] = []
    for entry in entries:
        text = load_fixture_text(entry=entry, repo_root=_repo_root())
        fixture_texts[entry.fixture_id] = text
        runtime_results.append(
            run_fixture_via_local_pipeline(
                connection=connection,
                entry=entry,
                fixture_text=text,
                artifact_root=artifact_root,
            )
        )
    return fixture_texts, runtime_results


def test_st017_baseline_capture_and_gate_b_stability_verification(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    old_root = os.environ.get("COUNCILSENSE_LOCAL_ARTIFACT_ROOT")
    os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = str(artifact_root)

    try:
        first_fixture_texts, first_results = _run_fixture_cohort(artifact_root=artifact_root / "baseline")
        baseline_scorecard = build_scorecard(
            manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
            fixtures=first_results,
            fixture_sources=first_fixture_texts,
            generated_at_utc=datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC),
        )
        baseline_snapshot = build_baseline_snapshot(
            scorecard=baseline_scorecard,
            captured_by="st017-test-suite",
            captured_from="local-ci",
            captured_at_utc=datetime(2026, 3, 3, 10, 5, 0, tzinfo=UTC),
        )

        second_fixture_texts, second_results = _run_fixture_cohort(artifact_root=artifact_root / "rerun")
        rerun_scorecard = build_scorecard(
            manifest_path="backend/tests/fixtures/st017_fixture_manifest.json",
            fixtures=second_results,
            fixture_sources=second_fixture_texts,
            generated_at_utc=datetime(2026, 3, 3, 10, 10, 0, tzinfo=UTC),
        )

        gate_report = build_gate_b_verification(
            baseline_snapshot=baseline_snapshot,
            rerun_scorecard=rerun_scorecard,
            variance_bounds=ST017_VARIANCE_BOUNDS,
            generated_at_utc=datetime(2026, 3, 3, 10, 15, 0, tzinfo=UTC),
        )

        assert baseline_snapshot["schema_version"] == "st-017-fixture-baseline-v1"
        assert baseline_snapshot["fixture_count"] == 3
        assert gate_report["schema_version"] == "st-017-gate-b-verification-v1"
        assert gate_report["gate_b_passed"] is True

        fixture_rows = gate_report["fixtures"]
        assert len(fixture_rows) == 3
        for row in fixture_rows:
            assert row["status"] == "ok"
            for dimension in row["dimensions"]:
                assert dimension["pass_fail_flip"] is False
                assert dimension["stable"] is True
                assert dimension["delta"] <= dimension["allowed_delta"]
    finally:
        if old_root is None:
            os.environ.pop("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", None)
        else:
            os.environ["COUNCILSENSE_LOCAL_ARTIFACT_ROOT"] = old_root


def test_st017_baseline_and_gate_b_artifacts_exist_and_are_schema_shaped() -> None:
    repo_root = _repo_root()
    baseline_path = repo_root / "config" / "ops" / "st-017-fixture-baseline-scorecard.json"
    gate_report_path = repo_root / "docs" / "runbooks" / "st-017-gate-b-verification-report.json"
    workflow_path = repo_root / "docs" / "runbooks" / "st-017-baseline-capture-and-gate-b-workflow.md"

    assert baseline_path.exists()
    assert gate_report_path.exists()
    assert workflow_path.exists()

    baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    gate_payload = json.loads(gate_report_path.read_text(encoding="utf-8"))

    assert baseline_payload["schema_version"] == "st-017-fixture-baseline-v1"
    assert baseline_payload["rubric_version"] == "st-017-rubric-v1"
    assert baseline_payload["fixture_count"] == 3

    fixture_ids = [item["fixture_id"] for item in baseline_payload["scorecard"]["fixtures"]]
    assert fixture_ids == sorted(fixture_ids)
    assert "st017-eagle-mountain-2024-12-03" in fixture_ids

    assert gate_payload["schema_version"] == "st-017-gate-b-verification-v1"
    assert isinstance(gate_payload["gate_b_passed"], bool)
    assert len(gate_payload["fixtures"]) == 3