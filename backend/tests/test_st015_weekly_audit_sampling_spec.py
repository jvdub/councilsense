from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from councilsense.app.ecr_audit_sampling import AuditSampleCandidate, select_weekly_audit_sample


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _window_start_utc() -> datetime:
    return datetime(2026, 2, 16, 0, 0, 0, tzinfo=timezone.utc)


def _load_contract_fixture() -> dict[str, object]:
    path = _repo_root() / "backend" / "tests" / "fixtures" / "st015_weekly_audit_report_schema_contract.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_st015_sampling_documents_and_schedule_artifacts_exist() -> None:
    repo_root = _repo_root()

    spec_path = repo_root / "docs" / "runbooks" / "st-015-weekly-audit-sampling-spec.md"
    schedule_path = repo_root / "config" / "ops" / "st-015-weekly-ecr-audit-schedule.yaml"

    assert spec_path.exists()
    assert schedule_path.exists()

    content = spec_path.read_text(encoding="utf-8")
    assert "## Sampling Frame Eligibility" in content
    assert "## Sample Size and Selection Method" in content
    assert "## Minimum Representativeness Rules" in content
    assert "## Weekly Schedule and Ownership" in content
    assert "## Report Schema Contract" in content

    schedule_content = schedule_path.read_text(encoding="utf-8")
    assert "cron_utc: \"0 7 * * 1\"" in schedule_content
    assert "primary_role: \"ops-quality-oncall\"" in schedule_content
    assert "backup_role: \"backend-oncall\"" in schedule_content


def test_st015_report_schema_contract_includes_required_fields_and_reason_codes() -> None:
    contract = _load_contract_fixture()

    assert contract["contract_version"] == "st-015-weekly-audit-report-v1"
    assert contract["time_zone"] == "UTC"

    required_field_values = contract["required_report_fields"]
    malformed_reason_values = contract["malformed_reason_codes"]

    assert isinstance(required_field_values, list)
    assert isinstance(malformed_reason_values, list)

    required_fields = set(required_field_values)
    assert "ecr" in required_fields
    assert "claim_count" in required_fields
    assert "claims_with_evidence_count" in required_fields
    assert "selected_publication_ids" in required_fields
    assert "representativeness" in required_fields

    malformed_codes = set(malformed_reason_values)
    assert "missing_city_id" in malformed_codes
    assert "missing_source_id" in malformed_codes
    assert "invalid_publication_status" in malformed_codes


def test_st015_sampling_is_deterministic_for_same_window_and_seed() -> None:
    window_start = _window_start_utc()
    candidates = _candidate_fixture()

    first = select_weekly_audit_sample(
        candidates,
        window_start_utc=window_start,
        sample_size=6,
        seed_salt="v1",
        min_city_slots=3,
        min_source_slots=2,
    )
    second = select_weekly_audit_sample(
        candidates,
        window_start_utc=window_start,
        sample_size=6,
        seed_salt="v1",
        min_city_slots=3,
        min_source_slots=2,
    )

    assert first.seed == second.seed
    assert [item.publication_id for item in first.selected] == [item.publication_id for item in second.selected]
    assert first.sample_size_actual == 6


def test_st015_sampling_enforces_spread_and_records_malformed_rows() -> None:
    result = select_weekly_audit_sample(
        _candidate_fixture(),
        window_start_utc=_window_start_utc(),
        sample_size=6,
        seed_salt="v1",
        min_city_slots=3,
        min_source_slots=2,
    )

    selected_cities = {item.city_id for item in result.selected}
    selected_sources = {item.source_id for item in result.selected}

    assert len(selected_cities) >= result.representativeness.target_city_slots
    assert len(selected_sources) >= result.representativeness.target_source_slots
    assert result.representativeness.is_degraded is False

    malformed_codes = {item.reason_code for item in result.malformed_exclusions}
    assert "missing_city_id" in malformed_codes
    assert "invalid_publication_status" in malformed_codes


def _candidate_fixture() -> list[AuditSampleCandidate]:
    window_start = _window_start_utc()

    def dt(days: int, hour: int) -> datetime:
        return window_start + timedelta(days=days, hours=hour)

    return [
        AuditSampleCandidate(
            publication_id="pub-001",
            meeting_id="meeting-001",
            city_id="city-a",
            source_id="source-legistar",
            publication_status="processed",
            published_at=dt(0, 2),
        ),
        AuditSampleCandidate(
            publication_id="pub-002",
            meeting_id="meeting-002",
            city_id="city-a",
            source_id="source-granicus",
            publication_status="processed",
            published_at=dt(1, 9),
        ),
        AuditSampleCandidate(
            publication_id="pub-003",
            meeting_id="meeting-003",
            city_id="city-b",
            source_id="source-legistar",
            publication_status="limited_confidence",
            published_at=dt(2, 11),
        ),
        AuditSampleCandidate(
            publication_id="pub-004",
            meeting_id="meeting-004",
            city_id="city-b",
            source_id="source-civicplus",
            publication_status="processed",
            published_at=dt(3, 10),
        ),
        AuditSampleCandidate(
            publication_id="pub-005",
            meeting_id="meeting-005",
            city_id="city-c",
            source_id="source-civicplus",
            publication_status="processed",
            published_at=dt(4, 15),
        ),
        AuditSampleCandidate(
            publication_id="pub-006",
            meeting_id="meeting-006",
            city_id="city-c",
            source_id="source-legistar",
            publication_status="processed",
            published_at=dt(5, 8),
        ),
        AuditSampleCandidate(
            publication_id="pub-007",
            meeting_id="meeting-007",
            city_id="city-d",
            source_id="source-granicus",
            publication_status="processed",
            published_at=dt(6, 7),
        ),
        AuditSampleCandidate(
            publication_id="pub-008",
            meeting_id="meeting-008",
            city_id="",
            source_id="source-legistar",
            publication_status="processed",
            published_at=dt(4, 12),
        ),
        AuditSampleCandidate(
            publication_id="pub-009",
            meeting_id="meeting-009",
            city_id="city-a",
            source_id="source-legistar",
            publication_status="draft",
            published_at=dt(4, 12),
        ),
        AuditSampleCandidate(
            publication_id="pub-010",
            meeting_id="meeting-010",
            city_id="city-z",
            source_id="source-legistar",
            publication_status="processed",
            published_at=window_start - timedelta(days=2),
        ),
    ]
