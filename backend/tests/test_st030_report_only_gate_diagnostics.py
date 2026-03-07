from __future__ import annotations

from dataclasses import replace
import json

import pytest

from councilsense.app.local_pipeline import (
    LocalPipelineOrchestrator,
    _ExtractedPayload,
    _MeetingMaterialContext,
    _evaluate_authority_policy,
)
from councilsense.app.quality_gate_rollout import append_shadow_diagnostics_artifact, evaluate_shadow_gates, resolve_rollout_config
from councilsense.app.st030_document_aware_gates import (
    REASON_CODE_CITATION_INPUTS_MISSING,
    REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD,
    REASON_CODE_GATE_PASS,
    REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,
    DocumentAwareGateInput,
)
from councilsense.app.summarization import ClaimEvidencePointer, SummarizationOutput, SummaryClaim
from councilsense.db import MeetingSummaryRepository, PILOT_CITY_ID, ProcessingRunRepository
from councilsense.testing.st025_fixtures import assemble_fixture_compose, create_test_connection, load_fixture_catalog, seed_fixture_scenario


@pytest.mark.parametrize(
    ("case_name", "gate_input", "expected_all_green", "expected_gate_statuses", "expected_reason_code"),
    [
        (
            "pass",
            DocumentAwareGateInput(
                authority_outcome="minutes_authoritative",
                authority_reason_codes=(),
                authority_conflict_count=0,
                source_statuses={"minutes": "present", "agenda": "present", "packet": "partial"},
                authoritative_locator_precision="precise",
                citation_precision_ratio=0.75,
                citation_pointer_count=4,
            ),
            True,
            {"authority_alignment": "pass", "document_coverage_balance": "pass", "citation_precision": "pass"},
            REASON_CODE_GATE_PASS,
        ),
        (
            "fail",
            DocumentAwareGateInput(
                authority_outcome="missing_authoritative_minutes",
                authority_reason_codes=(REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,),
                authority_conflict_count=1,
                source_statuses={"minutes": "missing", "agenda": "present", "packet": "present"},
                authoritative_locator_precision=None,
                citation_precision_ratio=0.25,
                citation_pointer_count=2,
            ),
            False,
            {"authority_alignment": "fail", "document_coverage_balance": "pass", "citation_precision": "fail"},
            REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,
        ),
        (
            "missing-input",
            DocumentAwareGateInput(
                authority_outcome=None,
                authority_reason_codes=(),
                authority_conflict_count=None,
                source_statuses={"agenda": "present"},
                authoritative_locator_precision=None,
                citation_precision_ratio=None,
                citation_pointer_count=0,
            ),
            False,
            {"authority_alignment": "fail", "document_coverage_balance": "fail", "citation_precision": "fail"},
            REASON_CODE_CITATION_INPUTS_MISSING,
        ),
    ],
)
def test_st030_report_only_diagnostics_artifact_emits_complete_machine_readable_records(
    tmp_path,
    case_name: str,
    gate_input: DocumentAwareGateInput,
    expected_all_green: bool,
    expected_gate_statuses: dict[str, str],
    expected_reason_code: str,
) -> None:
    artifact_path = tmp_path / f"{case_name}-gate-diagnostics.jsonl"
    config = resolve_rollout_config(environment="local", cohort=PILOT_CITY_ID)

    diagnostics = evaluate_shadow_gates(
        run_id=f"run-st030-{case_name}",
        city_id=PILOT_CITY_ID,
        meeting_id=f"meeting-st030-{case_name}",
        source_id="source-st030-report-only",
        source_type="minutes",
        config=config,
        source_text="Council adopted a publishable decision.",
        output=_sample_output(pointer_precision="section"),
        summarize_status="processed",
        extract_status="processed",
        summarize_fallback_used=False,
        document_aware_gate_input=gate_input,
    )
    append_shadow_diagnostics_artifact(artifact_path=str(artifact_path), diagnostics=diagnostics)

    payload = json.loads(artifact_path.read_text(encoding="utf-8").strip())
    document_aware_report = payload["document_aware_report"]

    assert payload["run_id"] == f"run-st030-{case_name}"
    assert payload["city_id"] == PILOT_CITY_ID
    assert payload["meeting_id"] == f"meeting-st030-{case_name}"
    assert payload["source_id"] == "source-st030-report-only"
    assert payload["source_type"] == "minutes"
    assert payload["promotion_scope_key"] == f"local:{PILOT_CITY_ID}"

    assert document_aware_report["evaluation_mode"] == "report_only"
    assert document_aware_report["decision_impact"] == "non_blocking"
    assert document_aware_report["diagnostics_complete"] is True
    assert document_aware_report["all_gates_green"] is expected_all_green

    gates = {gate["gate_id"]: gate for gate in document_aware_report["gates"]}
    assert {gate_id: gate["status"] for gate_id, gate in gates.items()} == expected_gate_statuses
    assert all("score" in gate and "threshold" in gate and "reason_codes" in gate and "details" in gate for gate in gates.values())
    assert any(expected_reason_code in gate["reason_codes"] for gate in gates.values())


def test_st030_report_only_document_aware_failures_preserve_publish_parity_when_gate_mode_toggles(
    monkeypatch,
    tmp_path,
) -> None:
    scenario = {fixture.fixture_id: fixture for fixture in load_fixture_catalog()}["st025-conflict-minutes-authoritative"]

    observed: dict[str, dict[str, object]] = {}
    for gate_mode in ("report_only", "enforced"):
        connection = create_test_connection()
        seed_fixture_scenario(connection=connection, scenario=scenario)
        orchestrator = LocalPipelineOrchestrator(connection)
        compose_input = assemble_fixture_compose(connection=connection, scenario=scenario)
        run_id = f"run-st030-parity-{gate_mode}"
        ProcessingRunRepository(connection).create_pending_run(
            run_id=run_id,
            city_id=PILOT_CITY_ID,
            cycle_id=f"cycle-{gate_mode}",
        )

        monkeypatch.setenv(
            "COUNCILSENSE_QG_CONFIG_JSON",
            json.dumps(
                {
                    "defaults": {
                        "gate_mode": gate_mode,
                        "enforcement_action": "downgrade",
                        "promotion_required": False,
                        "diagnostics_artifact_path": str(tmp_path / f"{gate_mode}-gate-diagnostics.jsonl"),
                        "document_aware_thresholds": {
                            "document_coverage_balance": {"min_score": 1.0},
                        },
                    }
                }
            ),
        )
        rollout_config = resolve_rollout_config(environment="local", cohort=PILOT_CITY_ID)
        summarize_payload, summarize_status = orchestrator._summarize_stage(
            run_id=run_id,
            city_id=PILOT_CITY_ID,
            meeting_id=scenario.meeting_id,
            source_id="source-st030-parity",
            source_type="minutes",
            extracted=_ExtractedPayload(
                text=compose_input.composed_text,
                artifact_id="artifact://st030-parity",
                section_ref="minutes/summary",
                metadata={},
            ),
            material_context=_MeetingMaterialContext(
                document_kind="minutes",
                meeting_date_iso=scenario.meeting_datetime_utc[:10],
                meeting_temporal_status="past",
            ),
            rollout_config=rollout_config,
            llm_provider="none",
            ollama_endpoint=None,
            ollama_model=None,
            ollama_timeout_seconds=30.0,
        )
        assert summarize_status == "processed"
        authority_policy = replace(
            summarize_payload.authority_policy,
            source_statuses={"minutes": "present", "agenda": "present", "packet": "missing"},
        )

        stage = orchestrator._publish_stage(
            run_id=run_id,
            city_id=PILOT_CITY_ID,
            source_id="source-st030-parity",
            source_type="minutes",
            meeting_id=scenario.meeting_id,
            output=summarize_payload.output,
            source_text=compose_input.composed_text,
            material_context=_MeetingMaterialContext(
                document_kind="minutes",
                meeting_date_iso=scenario.meeting_datetime_utc[:10],
                meeting_temporal_status="past",
            ),
            authority_policy=authority_policy,
            extract_status="processed",
            summarize_status=summarize_status,
            summarize_fallback_used=False,
            rollout_config=rollout_config,
        )

        publication = MeetingSummaryRepository(connection).connection.execute(
            """
            SELECT publication_status, confidence_label
            FROM summary_publications
            WHERE processing_run_id = ?
            """,
            (run_id,),
        ).fetchone()
        assert publication is not None

        observed[gate_mode] = {
            "stage_status": str(stage["status"]),
            "publication_status": str(publication[0]),
            "confidence_label": str(publication[1]),
            "document_aware_all_gates_green": bool(
                stage["metadata"]["quality_gate_rollout"]["shadow_diagnostics"]["document_aware_report"]["all_gates_green"]
            ),
            "citation_gate_reason_codes": list(
                next(
                    gate["reason_codes"]
                    for gate in stage["metadata"]["quality_gate_rollout"]["shadow_diagnostics"]["document_aware_report"]["gates"]
                    if gate["gate_id"] == "document_coverage_balance"
                )
            ),
        }

    monkeypatch.delenv("COUNCILSENSE_QG_CONFIG_JSON", raising=False)

    assert observed["report_only"]["stage_status"] == "processed"
    assert observed["enforced"]["stage_status"] == "processed"
    assert observed["report_only"]["publication_status"] == observed["enforced"]["publication_status"] == "processed"
    assert observed["report_only"]["confidence_label"] == observed["enforced"]["confidence_label"] == "high"
    assert observed["report_only"]["document_aware_all_gates_green"] is False
    assert observed["enforced"]["document_aware_all_gates_green"] is False
    assert observed["report_only"]["citation_gate_reason_codes"] == [REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD]
    assert observed["enforced"]["citation_gate_reason_codes"] == [REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD]


def _sample_output(*, pointer_precision: str) -> SummarizationOutput:
    char_start = 0 if pointer_precision != "file" else None
    char_end = 48 if pointer_precision != "file" else None
    section_ref = "minutes.section.1" if pointer_precision != "file" else "artifact.pdf"
    return SummarizationOutput.from_sections(
        summary="Council adopted a transportation amendment.",
        key_decisions=["Council adopted a transportation amendment."],
        key_actions=["Staff will publish the implementation timeline."],
        notable_topics=["Transportation"],
        claims=(
            SummaryClaim(
                claim_text="Council adopted a transportation amendment.",
                evidence=(
                    ClaimEvidencePointer(
                        artifact_id="artifact://st030",
                        section_ref=section_ref,
                        char_start=char_start,
                        char_end=char_end,
                        excerpt="Council adopted a transportation amendment.",
                        document_kind="minutes",
                        precision=pointer_precision,
                    ),
                ),
                evidence_gap=False,
            ),
        ),
    )