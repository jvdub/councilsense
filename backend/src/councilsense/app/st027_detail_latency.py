from __future__ import annotations

import argparse
import base64
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import time
from typing import Any

from fastapi.testclient import TestClient

from councilsense.app.main import create_app
from councilsense.db import PILOT_CITY_ID


DETAIL_ENDPOINT_LATENCY_REPORT_SCHEMA_VERSION = "st-027-detail-endpoint-latency-report-v1"
DEFAULT_REPEAT_COUNT = 3
DEFAULT_SAMPLE_COUNT = 75
DEFAULT_WARMUP_COUNT = 15


@dataclass(frozen=True)
class DetailEndpointLatencyThresholds:
    flag_off_p95_max_ms: float = 35.0
    flag_on_p95_max_ms: float = 50.0
    flag_on_p95_delta_max_ms: float = 15.0
    flag_on_p95_ratio_max: float = 1.5
    repeat_run_p95_spread_max_ms: float = 8.0


def compute_percentile_ms(samples_ms: Sequence[float], *, percentile: int) -> float:
    if not samples_ms:
        raise ValueError("latency percentile requires at least one sample")
    if not 0 < percentile <= 100:
        raise ValueError("percentile must be in the interval (0, 100]")

    ordered = sorted(float(sample) for sample in samples_ms)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return round(ordered[rank - 1], 3)


def summarize_latency_samples(samples_ms: Sequence[float]) -> dict[str, object]:
    if not samples_ms:
        raise ValueError("latency summary requires at least one sample")

    values = [float(sample) for sample in samples_ms]
    return {
        "sample_count": len(values),
        "min_ms": round(min(values), 3),
        "mean_ms": round(statistics.fmean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": compute_percentile_ms(values, percentile=95),
        "p99_ms": compute_percentile_ms(values, percentile=99),
        "max_ms": round(max(values), 3),
    }


def build_detail_endpoint_latency_report(
    *,
    flag_off_runs_ms: Sequence[Sequence[float]],
    flag_on_runs_ms: Sequence[Sequence[float]],
    repeat_count: int,
    sample_count: int,
    warmup_count: int,
    thresholds: DetailEndpointLatencyThresholds | None = None,
    fixture_profile: dict[str, object] | None = None,
    captured_by: str = "local-release-check",
    environment: str = "local-dev",
    generated_at_utc: datetime | None = None,
) -> dict[str, object]:
    selected_thresholds = thresholds or DetailEndpointLatencyThresholds()
    timestamp = (generated_at_utc or datetime.now(UTC)).replace(microsecond=0).isoformat()

    flag_off_report = _build_scenario_report(
        scenario_id="flag_off_baseline",
        flag_state="off",
        runs_ms=flag_off_runs_ms,
        repeat_run_p95_spread_max_ms=selected_thresholds.repeat_run_p95_spread_max_ms,
    )
    flag_on_report = _build_scenario_report(
        scenario_id="flag_on_additive",
        flag_state="on",
        runs_ms=flag_on_runs_ms,
        repeat_run_p95_spread_max_ms=selected_thresholds.repeat_run_p95_spread_max_ms,
    )

    flag_off_p95 = float(flag_off_report["aggregate_summary"]["p95_ms"])
    flag_on_p95 = float(flag_on_report["aggregate_summary"]["p95_ms"])
    p95_delta_ms = round(flag_on_p95 - flag_off_p95, 3)
    p95_ratio = round((flag_on_p95 / flag_off_p95), 3) if flag_off_p95 > 0 else None

    failed_checks: list[str] = []
    if flag_off_p95 > selected_thresholds.flag_off_p95_max_ms:
        failed_checks.append("flag_off_p95_budget_exceeded")
    if flag_on_p95 > selected_thresholds.flag_on_p95_max_ms:
        failed_checks.append("flag_on_p95_budget_exceeded")
    if p95_delta_ms > selected_thresholds.flag_on_p95_delta_max_ms:
        failed_checks.append("flag_on_p95_delta_budget_exceeded")
    if p95_ratio is not None and p95_ratio > selected_thresholds.flag_on_p95_ratio_max:
        failed_checks.append("flag_on_p95_ratio_budget_exceeded")
    if not bool(flag_off_report["stability"]["within_budget"]):
        failed_checks.append("flag_off_stability_budget_exceeded")
    if not bool(flag_on_report["stability"]["within_budget"]):
        failed_checks.append("flag_on_stability_budget_exceeded")

    return {
        "schema_version": DETAIL_ENDPOINT_LATENCY_REPORT_SCHEMA_VERSION,
        "task_id": "TASK-ST-027-05",
        "story_id": "ST-027",
        "generated_at_utc": timestamp,
        "captured_by": captured_by,
        "environment": environment,
        "endpoint": {"method": "GET", "path": "/v1/meetings/{meeting_id}"},
        "measurement": {
            "repeat_count": repeat_count,
            "sample_count_per_repeat": sample_count,
            "warmup_count_per_repeat": warmup_count,
            "percentile_method": "nearest-rank",
            "clock_source": "time.perf_counter_ns",
            "client": "fastapi.testclient.TestClient",
            "fixture_profile": fixture_profile or {},
        },
        "thresholds": {
            "flag_off_p95_max_ms": selected_thresholds.flag_off_p95_max_ms,
            "flag_on_p95_max_ms": selected_thresholds.flag_on_p95_max_ms,
            "flag_on_p95_delta_max_ms": selected_thresholds.flag_on_p95_delta_max_ms,
            "flag_on_p95_ratio_max": selected_thresholds.flag_on_p95_ratio_max,
            "repeat_run_p95_spread_max_ms": selected_thresholds.repeat_run_p95_spread_max_ms,
        },
        "scenarios": [flag_off_report, flag_on_report],
        "regression_check": {
            "flag_off_p95_ms": flag_off_p95,
            "flag_on_p95_ms": flag_on_p95,
            "flag_on_p95_delta_ms": p95_delta_ms,
            "flag_on_p95_ratio": p95_ratio,
            "within_budget": not failed_checks,
            "failed_checks": failed_checks,
            "rollback_recommended": bool(failed_checks),
        },
    }


def serialize_detail_endpoint_latency_report(report: dict[str, object]) -> str:
    return f"{json.dumps(report, indent=2, sort_keys=True)}\n"


def run_detail_endpoint_latency_benchmark(
    *,
    repeat_count: int = DEFAULT_REPEAT_COUNT,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    warmup_count: int = DEFAULT_WARMUP_COUNT,
    thresholds: DetailEndpointLatencyThresholds | None = None,
    captured_by: str = "local-release-check",
    environment: str = "local-dev",
    generated_at_utc: datetime | None = None,
) -> dict[str, object]:
    fixture_profile = build_benchmark_fixture_profile()
    flag_off_runs_ms = _measure_scenario_runs(
        additive_enabled=False,
        repeat_count=repeat_count,
        sample_count=sample_count,
        warmup_count=warmup_count,
        fixture_profile=fixture_profile,
    )
    flag_on_runs_ms = _measure_scenario_runs(
        additive_enabled=True,
        repeat_count=repeat_count,
        sample_count=sample_count,
        warmup_count=warmup_count,
        fixture_profile=fixture_profile,
    )
    return build_detail_endpoint_latency_report(
        flag_off_runs_ms=flag_off_runs_ms,
        flag_on_runs_ms=flag_on_runs_ms,
        repeat_count=repeat_count,
        sample_count=sample_count,
        warmup_count=warmup_count,
        thresholds=thresholds,
        fixture_profile=fixture_profile,
        captured_by=captured_by,
        environment=environment,
        generated_at_utc=generated_at_utc,
    )


def build_benchmark_fixture_profile() -> dict[str, object]:
    return {
        "city_id": PILOT_CITY_ID,
        "meeting_id": "meeting-st027-latency-benchmark",
        "claim_count": 24,
        "evidence_pointers_per_claim": 3,
        "planned_item_count": 18,
        "outcome_item_count": 18,
        "mismatch_item_count": 12,
        "payload_shape": "high-contention additive detail payload",
    }


def _measure_scenario_runs(
    *,
    additive_enabled: bool,
    repeat_count: int,
    sample_count: int,
    warmup_count: int,
    fixture_profile: dict[str, object],
) -> list[list[float]]:
    runs: list[list[float]] = []
    for repeat_index in range(repeat_count):
        with _benchmark_client(additive_enabled=additive_enabled, fixture_profile=fixture_profile) as (client, headers, meeting_id):
            for _ in range(warmup_count):
                warmup_response = client.get(f"/v1/meetings/{meeting_id}", headers=headers)
                if warmup_response.status_code != 200:
                    raise RuntimeError(
                        f"warmup request failed for additive_enabled={additive_enabled}: "
                        f"status={warmup_response.status_code}"
                    )

            repeat_samples: list[float] = []
            for _ in range(sample_count):
                started_at = time.perf_counter_ns()
                response = client.get(f"/v1/meetings/{meeting_id}", headers=headers)
                finished_at = time.perf_counter_ns()
                if response.status_code != 200:
                    raise RuntimeError(
                        f"benchmark request failed for additive_enabled={additive_enabled}: "
                        f"status={response.status_code}"
                    )
                repeat_samples.append(round((finished_at - started_at) / 1_000_000.0, 3))

            if len(repeat_samples) != sample_count:
                raise RuntimeError(
                    f"benchmark run {repeat_index + 1} produced an unexpected sample count: "
                    f"expected={sample_count} actual={len(repeat_samples)}"
                )
            runs.append(repeat_samples)
    return runs


def _build_scenario_report(
    *,
    scenario_id: str,
    flag_state: str,
    runs_ms: Sequence[Sequence[float]],
    repeat_run_p95_spread_max_ms: float,
) -> dict[str, object]:
    run_summaries = [
        {"run_index": index + 1, **summarize_latency_samples(run_samples)}
        for index, run_samples in enumerate(runs_ms)
    ]
    aggregate_samples = [sample for run_samples in runs_ms for sample in run_samples]
    aggregate_summary = summarize_latency_samples(aggregate_samples)
    run_p95_values = [float(summary["p95_ms"]) for summary in run_summaries]
    p95_spread_ms = round(max(run_p95_values) - min(run_p95_values), 3) if run_p95_values else 0.0
    return {
        "scenario_id": scenario_id,
        "flag_state": flag_state,
        "run_summaries": run_summaries,
        "aggregate_summary": aggregate_summary,
        "stability": {
            "repeat_count": len(run_summaries),
            "p95_spread_ms": p95_spread_ms,
            "within_budget": p95_spread_ms <= repeat_run_p95_spread_max_ms,
        },
    }


@contextmanager
def _benchmark_client(
    *,
    additive_enabled: bool,
    fixture_profile: dict[str, object],
) -> Iterator[tuple[TestClient, dict[str, str], str]]:
    auth_secret = "st027-latency-secret"
    env_updates = {
        "AUTH_SESSION_SECRET": auth_secret,
        "SUPPORTED_CITY_IDS": str(fixture_profile["city_id"]),
        "ST022_API_ADDITIVE_V1_FIELDS_ENABLED": "true" if additive_enabled else "false",
        "ST022_API_ADDITIVE_V1_BLOCKS": (
            "planned,outcomes,planned_outcome_mismatches" if additive_enabled else ""
        ),
    }
    with _temporary_environment(env_updates):
        with TestClient(create_app()) as client:
            token = _issue_token(
                user_id=f"st027-benchmark-{'on' if additive_enabled else 'off'}",
                secret=auth_secret,
                expires_in_seconds=300,
            )
            headers = {"Authorization": f"Bearer {token}"}
            _set_home_city(client, headers=headers, city_id=str(fixture_profile["city_id"]))
            meeting_id = str(fixture_profile["meeting_id"])
            _seed_benchmark_payload(client, fixture_profile=fixture_profile)
            yield client, headers, meeting_id


@contextmanager
def _temporary_environment(updates: dict[str, str]) -> Iterator[None]:
    original_values = {key: os.getenv(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, original in original_values.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


def _b64url(data: dict[str, object]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _issue_token(user_id: str, *, secret: str, expires_in_seconds: int) -> str:
    header = _b64url({"alg": "HS256", "typ": "JWT"})
    exp = int((datetime.now(tz=UTC) + timedelta(seconds=expires_in_seconds)).timestamp())
    payload = _b64url({"sub": user_id, "exp": exp})
    signing_input = f"{header}.{payload}"
    digest = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
    return f"{signing_input}.{signature}"


def _set_home_city(client: TestClient, *, headers: dict[str, str], city_id: str) -> None:
    response = client.patch("/v1/me", headers=headers, json={"home_city_id": city_id})
    if response.status_code != 200:
        raise RuntimeError(f"failed to set home city for latency benchmark: status={response.status_code}")


def _seed_benchmark_payload(client: TestClient, *, fixture_profile: dict[str, object]) -> None:
    meeting_id = str(fixture_profile["meeting_id"])
    publication_id = "pub-st027-latency-benchmark"
    publish_stage_outcome_id = "outcome-publish-st027-latency-benchmark"

    _insert_meeting(
        client,
        meeting_id=meeting_id,
        meeting_uid="uid-st027-latency-benchmark",
        title="ST-027 detail latency benchmark fixture",
        created_at="2026-03-07 12:00:00",
        city_id=str(fixture_profile["city_id"]),
    )

    _insert_publish_stage_outcome(
        client,
        outcome_id=publish_stage_outcome_id,
        run_id="run-st027-latency-benchmark",
        city_id=str(fixture_profile["city_id"]),
        meeting_id=meeting_id,
        metadata={
            "additive_blocks": {
                "planned": {
                    "generated_at": "2026-03-07T12:00:00Z",
                    "source_coverage": {"minutes": "present", "agenda": "present", "packet": "present"},
                    "items": [_planned_item(index) for index in range(int(fixture_profile["planned_item_count"]))],
                },
                "outcomes": {
                    "generated_at": "2026-03-07T12:05:00Z",
                    "authority_source": "minutes",
                    "items": [_outcome_item(index) for index in range(int(fixture_profile["outcome_item_count"]))],
                },
                "planned_outcome_mismatches": {
                    "summary": {
                        "total": int(fixture_profile["mismatch_item_count"]),
                        "high": 4,
                        "medium": 6,
                        "low": int(fixture_profile["mismatch_item_count"]) - 10,
                    },
                    "items": [
                        _mismatch_item(index) for index in range(int(fixture_profile["mismatch_item_count"]))
                    ],
                },
            }
        },
    )

    _insert_publication(
        client,
        publication_id=publication_id,
        meeting_id=meeting_id,
        publication_status="processed",
        confidence_label="high",
        summary_text=(
            "Council handled a representative additive release payload with a large claim set, "
            "planned items, outcomes, and mismatch evaluations."
        ),
        key_decisions_json=json.dumps([
            "Approved the representative consent package",
            "Deferred one procurement ordinance for revision",
        ], separators=(",", ":")),
        key_actions_json=json.dumps([
            "Staff to publish revised procurement language",
            "Clerk to attach supporting exhibits to the minutes bundle",
        ], separators=(",", ":")),
        notable_topics_json=json.dumps([
            "Procurement",
            "Water rates",
            "Capital planning",
        ], separators=(",", ":")),
        published_at="2026-03-07T12:10:00Z",
        publish_stage_outcome_id=publish_stage_outcome_id,
    )

    claim_count = int(fixture_profile["claim_count"])
    evidence_per_claim = int(fixture_profile["evidence_pointers_per_claim"])
    for claim_index in range(claim_count):
        claim_id = f"claim-st027-latency-{claim_index}"
        _insert_claim(
            client,
            claim_id=claim_id,
            publication_id=publication_id,
            claim_order=claim_index + 1,
            claim_text=(
                f"Representative detail claim {claim_index + 1} captures an authoritative decision "
                f"and the supporting rationale for benchmark coverage."
            ),
        )
        for evidence_index in range(evidence_per_claim):
            ordinal = (claim_index * evidence_per_claim) + evidence_index
            _insert_evidence_pointer(
                client,
                pointer_id=f"pointer-st027-latency-{ordinal}",
                claim_id=claim_id,
                artifact_id=f"artifact-st027-latency-{ordinal}",
                section_ref=f"minutes.section.{claim_index + 1}.{evidence_index + 1}",
                char_start=ordinal * 20,
                char_end=(ordinal * 20) + 90,
                excerpt=(
                    "Representative excerpt for latency benchmarking with enough text to reflect "
                    "realistic evidence serialization cost."
                ),
                document_id=f"doc-st027-latency-{claim_index}",
                span_id=f"span-st027-latency-{ordinal}",
                document_kind="minutes",
                section_path=f"minutes/section/{claim_index + 1}/evidence/{evidence_index + 1}",
                precision="offset",
                confidence="high",
            )


def _planned_item(index: int) -> dict[str, object]:
    return {
        "planned_id": f"planned-{index}",
        "title": f"Planned item {index + 1}",
        "category": "ordinance" if index % 2 == 0 else "procurement",
        "status": "planned",
        "confidence": "high" if index % 3 else "medium",
        "evidence_references_v2": [
            {
                "evidence_id": f"planned-ev-{index}",
                "document_id": f"doc-planned-{index}",
                "artifact_id": f"artifact-planned-{index}",
                "document_kind": "agenda",
                "section_path": f"agenda/items/{index + 1}",
                "page_start": (index % 6) + 1,
                "page_end": (index % 6) + 1,
                "char_start": None,
                "char_end": None,
                "precision": "section",
                "confidence": "medium",
                "excerpt": "Agenda language describing the planned action under consideration.",
            }
        ],
    }


def _outcome_item(index: int) -> dict[str, object]:
    result = "approved" if index % 4 else "deferred"
    return {
        "outcome_id": f"outcome-{index}",
        "title": f"Outcome item {index + 1}",
        "result": result,
        "confidence": "high" if result == "approved" else "medium",
        "evidence_references_v2": [
            {
                "evidence_id": f"outcome-ev-{index}",
                "document_id": f"doc-outcome-{index}",
                "artifact_id": f"artifact-outcome-{index}",
                "document_kind": "minutes",
                "section_path": f"minutes/decisions/{index + 1}",
                "page_start": (index % 8) + 1,
                "page_end": (index % 8) + 1,
                "char_start": (index + 1) * 37,
                "char_end": ((index + 1) * 37) + 120,
                "precision": "offset",
                "confidence": "high",
                "excerpt": "Minutes excerpt showing the final action recorded by the clerk.",
            }
        ],
    }


def _mismatch_item(index: int) -> dict[str, object]:
    severity = "high" if index < 4 else "medium" if index < 10 else "low"
    return {
        "mismatch_id": f"mismatch-{index}",
        "planned_id": f"planned-{index}",
        "outcome_id": f"outcome-{index}",
        "severity": severity,
        "mismatch_type": "disposition_change" if index % 2 == 0 else "scope_change",
        "description": "Representative mismatch entry for additive detail benchmark coverage.",
        "reason_codes": ["outcome_changed" if index % 2 == 0 else "scope_shifted"],
        "evidence_references_v2": [
            {
                "evidence_id": f"mismatch-ev-{index}",
                "document_id": f"doc-mismatch-{index}",
                "artifact_id": f"artifact-mismatch-{index}",
                "document_kind": "minutes",
                "section_path": f"minutes/mismatch/{index + 1}",
                "page_start": (index % 7) + 1,
                "page_end": (index % 7) + 1,
                "char_start": (index + 1) * 31,
                "char_end": ((index + 1) * 31) + 110,
                "precision": "offset",
                "confidence": "high",
                "excerpt": "Minutes excerpt justifying the mismatch classification.",
            }
        ],
    }


def _insert_meeting(
    client: TestClient,
    *,
    meeting_id: str,
    meeting_uid: str,
    title: str,
    created_at: str,
    city_id: str,
) -> None:
    connection = _db_connection(client)
    connection.execute(
        """
        INSERT INTO meetings (id, city_id, meeting_uid, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (meeting_id, city_id, meeting_uid, title, created_at, created_at),
    )


def _insert_publication(
    client: TestClient,
    *,
    publication_id: str,
    meeting_id: str,
    publication_status: str,
    confidence_label: str,
    summary_text: str,
    key_decisions_json: str,
    key_actions_json: str,
    notable_topics_json: str,
    published_at: str,
    publish_stage_outcome_id: str,
) -> None:
    connection = _db_connection(client)
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
            published_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            publication_id,
            meeting_id,
            None,
            publish_stage_outcome_id,
            1,
            publication_status,
            confidence_label,
            summary_text,
            key_decisions_json,
            key_actions_json,
            notable_topics_json,
            published_at,
            published_at,
        ),
    )


def _insert_claim(
    client: TestClient,
    *,
    claim_id: str,
    publication_id: str,
    claim_order: int,
    claim_text: str,
) -> None:
    _db_connection(client).execute(
        """
        INSERT INTO publication_claims (id, publication_id, claim_order, claim_text)
        VALUES (?, ?, ?, ?)
        """,
        (claim_id, publication_id, claim_order, claim_text),
    )


def _insert_evidence_pointer(
    client: TestClient,
    *,
    pointer_id: str,
    claim_id: str,
    artifact_id: str,
    section_ref: str,
    char_start: int,
    char_end: int,
    excerpt: str,
    document_id: str,
    span_id: str,
    document_kind: str,
    section_path: str,
    precision: str,
    confidence: str,
) -> None:
    connection = _db_connection(client)
    meeting_id = str(
        connection.execute(
            """
            SELECT sp.meeting_id
            FROM publication_claims pc
            INNER JOIN summary_publications sp ON sp.id = pc.publication_id
            WHERE pc.id = ?
            """,
            (claim_id,),
        ).fetchone()[0]
    )
    current_revision = int(
        connection.execute(
            """
            SELECT COALESCE(MAX(revision_number), 0)
            FROM canonical_documents
            WHERE meeting_id = ? AND document_kind = ?
            """,
            (meeting_id, document_kind),
        ).fetchone()[0]
    )
    revision_number = current_revision + 1
    is_active_revision = 1 if current_revision == 0 else 0

    connection.execute(
        """
        INSERT OR IGNORE INTO canonical_documents (
            id,
            meeting_id,
            document_kind,
            revision_id,
            revision_number,
            is_active_revision,
            authority_level,
            authority_source,
            parser_name,
            parser_version,
            extraction_status,
            extraction_confidence,
            extracted_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            meeting_id,
            document_kind,
            f"revision-{document_id}",
            revision_number,
            is_active_revision,
            "authoritative" if document_kind == "minutes" else "supplemental",
            "test-fixture",
            "test-parser",
            "v1",
            "processed",
            0.95,
            "2026-03-07T12:00:00Z",
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO canonical_document_spans (
            id,
            canonical_document_id,
            artifact_id,
            artifact_scope,
            stable_section_path,
            start_char_offset,
            end_char_offset,
            locator_fingerprint,
            parser_name,
            parser_version,
            span_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            span_id,
            document_id,
            artifact_id,
            "body",
            section_path,
            char_start,
            char_end,
            f"fingerprint-{span_id}",
            "test-parser",
            "v1",
            excerpt,
        ),
    )
    connection.execute(
        """
        INSERT INTO claim_evidence_pointers (
            id,
            claim_id,
            artifact_id,
            section_ref,
            char_start,
            char_end,
            excerpt,
            document_id,
            span_id,
            document_kind,
            section_path,
            precision,
            confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pointer_id,
            claim_id,
            artifact_id,
            section_ref,
            char_start,
            char_end,
            excerpt,
            document_id,
            span_id,
            document_kind,
            section_path,
            precision,
            confidence,
        ),
    )


def _insert_publish_stage_outcome(
    client: TestClient,
    *,
    outcome_id: str,
    run_id: str,
    city_id: str,
    meeting_id: str,
    metadata: dict[str, Any],
) -> None:
    connection = _db_connection(client)
    connection.execute(
        """
        INSERT OR IGNORE INTO processing_runs (
            id,
            city_id,
            cycle_id,
            status,
            parser_version,
            source_version,
            started_at
        )
        VALUES (?, ?, ?, 'processed', ?, ?, ?)
        """,
        (
            run_id,
            city_id,
            f"cycle-{run_id}",
            "v1",
            "test-source",
            "2026-03-07T12:00:00Z",
        ),
    )
    connection.execute(
        """
        INSERT INTO processing_stage_outcomes (
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
        VALUES (?, ?, ?, ?, 'publish', 'processed', ?, ?, ?)
        """,
        (
            outcome_id,
            run_id,
            city_id,
            meeting_id,
            json.dumps(metadata, separators=(",", ":"), sort_keys=True),
            "2026-03-07T12:05:00Z",
            "2026-03-07T12:06:00Z",
        ),
    )


def _db_connection(client: TestClient) -> sqlite3.Connection:
    return client.app.state.db_connection


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ST-027 detail endpoint latency benchmark.")
    parser.add_argument("--repeat-count", type=int, default=DEFAULT_REPEAT_COUNT)
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--warmup-count", type=int, default=DEFAULT_WARMUP_COUNT)
    parser.add_argument("--captured-by", default="local-release-check")
    parser.add_argument("--environment", default="local-dev")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_detail_endpoint_latency_benchmark(
        repeat_count=args.repeat_count,
        sample_count=args.sample_count,
        warmup_count=args.warmup_count,
        captured_by=args.captured_by,
        environment=args.environment,
    )
    rendered = serialize_detail_endpoint_latency_report(report)

    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0 if bool(report["regression_check"]["within_budget"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())