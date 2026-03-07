from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json

import pytest

from councilsense.app.local_pipeline import (
    LocalPipelineOrchestrator,
    _ExtractedPayload,
    _MeetingMaterialContext,
    _evaluate_authority_policy,
)
from councilsense.app.quality_gate_rollout import (
    GateDiagnostic,
    PromotionStatus,
    append_promotion_artifact,
    append_shadow_diagnostics_artifact,
    decide_enforcement_outcome,
    compute_promotion_status,
    evaluate_shadow_gates,
    resolve_rollout_config,
)
from councilsense.app.st030_document_aware_gates import (
    REASON_CODE_CITATION_INPUTS_MISSING,
    REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD,
    REASON_CODE_GATE_PASS,
    REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,
    REASON_CODE_UNRESOLVED_SOURCE_CONFLICT,
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


@pytest.mark.parametrize(
    ("gate_input", "config_payload", "expected_decision", "expected_reason_code", "expected_gate_id", "expected_policy_action"),
    [
        (
            DocumentAwareGateInput(
                authority_outcome="minutes_authoritative",
                authority_reason_codes=(),
                authority_conflict_count=0,
                source_statuses={"minutes": "present", "agenda": "present", "packet": "present"},
                authoritative_locator_precision="precise",
                citation_precision_ratio=1.0,
                citation_pointer_count=3,
            ),
            {
                "defaults": {
                    "gate_mode": "enforced",
                    "enforcement_action": "downgrade",
                    "promotion_required": False,
                }
            },
            "enforce_pass",
            "all_gates_green",
            None,
            None,
        ),
        (
            DocumentAwareGateInput(
                authority_outcome="minutes_authoritative",
                authority_reason_codes=(),
                authority_conflict_count=0,
                source_statuses={"minutes": "present", "agenda": "present", "packet": "missing"},
                authoritative_locator_precision="precise",
                citation_precision_ratio=1.0,
                citation_pointer_count=3,
            ),
            {
                "defaults": {
                    "gate_mode": "enforced",
                    "enforcement_action": "downgrade",
                    "promotion_required": False,
                    "document_aware_thresholds": {
                        "document_coverage_balance": {"min_score": 1.0},
                    },
                }
            },
            "enforce_downgrade",
            "document_aware_document_coverage_balance_downgraded_publish",
            "document_coverage_balance",
            "downgrade",
        ),
        (
            DocumentAwareGateInput(
                authority_outcome="unresolved_conflict",
                authority_reason_codes=(REASON_CODE_UNRESOLVED_SOURCE_CONFLICT,),
                authority_conflict_count=1,
                source_statuses={"minutes": "missing", "agenda": "present", "packet": "present"},
                authoritative_locator_precision=None,
                citation_precision_ratio=1.0,
                citation_pointer_count=3,
            ),
            {
                "defaults": {
                    "gate_mode": "enforced",
                    "enforcement_action": "downgrade",
                    "promotion_required": False,
                }
            },
            "enforce_block",
            "document_aware_authority_alignment_blocked_publish",
            "authority_alignment",
            "block",
        ),
    ],
)
def test_st030_enforced_publish_decision_maps_document_aware_pass_and_fail_cases(
    monkeypatch,
    gate_input: DocumentAwareGateInput,
    config_payload: dict[str, object],
    expected_decision: str,
    expected_reason_code: str,
    expected_gate_id: str | None,
    expected_policy_action: str | None,
) -> None:
    monkeypatch.setenv("COUNCILSENSE_QG_CONFIG_JSON", json.dumps(config_payload))
    config = resolve_rollout_config(environment="local", cohort=PILOT_CITY_ID)

    diagnostics = evaluate_shadow_gates(
        run_id="run-st030-policy-mapping",
        city_id=PILOT_CITY_ID,
        meeting_id="meeting-st030-policy-mapping",
        source_id="source-st030-policy-mapping",
        source_type="minutes",
        config=config,
        source_text="Council adopted a publishable decision.",
        output=_sample_output(pointer_precision="section"),
        summarize_status="processed",
        extract_status="processed",
        summarize_fallback_used=False,
        document_aware_gate_input=gate_input,
    )
    diagnostics = replace(
        diagnostics,
        all_gates_green=True,
        gates=(
            GateDiagnostic(gate_id="gate_a_contract_safety", passed=True, reason_codes=("gate_pass",)),
            GateDiagnostic(gate_id="gate_b_quality_parity", passed=True, reason_codes=("gate_pass",)),
            GateDiagnostic(gate_id="gate_c_operational_reliability", passed=True, reason_codes=("gate_pass",)),
        ),
    )
    outcome = decide_enforcement_outcome(
        config=config,
        diagnostics=diagnostics,
        promotion_status=_eligible_promotion_status(),
    )

    assert outcome.decision == expected_decision
    assert expected_reason_code in outcome.reason_codes

    if expected_gate_id is None:
        assert outcome.gate_reason_details == ()
    else:
        assert any(detail.gate_id == expected_gate_id for detail in outcome.gate_reason_details)
        detail = next(detail for detail in outcome.gate_reason_details if detail.gate_id == expected_gate_id)
        assert detail.gate_family == "document_aware_gate"
        assert detail.policy_action == expected_policy_action


def test_st030_document_aware_coverage_failure_changes_only_enforced_publish_outcome_when_gate_mode_toggles(
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
            "quality_gate_reason_codes": list(stage["metadata"]["quality_gate_reason_codes"]),
            "document_aware_all_gates_green": bool(
                stage["metadata"]["quality_gate_rollout"]["shadow_diagnostics"]["document_aware_report"]["all_gates_green"]
            ),
            "coverage_gate_reason_codes": list(
                next(
                    gate["reason_codes"]
                    for gate in stage["metadata"]["quality_gate_rollout"]["shadow_diagnostics"]["document_aware_report"]["gates"]
                    if gate["gate_id"] == "document_coverage_balance"
                )
            ),
            "enforcement_decision": str(stage["metadata"]["quality_gate_rollout"]["enforcement_outcome"]["decision"]),
            "gate_reason_details": list(stage["metadata"]["quality_gate_rollout"]["enforcement_outcome"]["gate_reason_details"]),
        }

    monkeypatch.delenv("COUNCILSENSE_QG_CONFIG_JSON", raising=False)

    assert observed["report_only"]["stage_status"] == "processed"
    assert observed["enforced"]["stage_status"] == "limited_confidence"
    assert observed["report_only"]["publication_status"] == "processed"
    assert observed["enforced"]["publication_status"] == "limited_confidence"
    assert observed["report_only"]["confidence_label"] == "high"
    assert observed["enforced"]["confidence_label"] == "limited_confidence"
    assert observed["report_only"]["document_aware_all_gates_green"] is False
    assert observed["enforced"]["document_aware_all_gates_green"] is False
    assert observed["report_only"]["coverage_gate_reason_codes"] == [REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD]
    assert observed["enforced"]["coverage_gate_reason_codes"] == [REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD]
    assert observed["report_only"]["enforcement_decision"] == "observe"
    assert observed["enforced"]["enforcement_decision"] == "enforce_downgrade"
    assert "document_aware_document_coverage_balance_downgraded_publish" not in observed["report_only"]["quality_gate_reason_codes"]
    assert "document_aware_document_coverage_balance_downgraded_publish" in observed["enforced"]["quality_gate_reason_codes"]
    assert observed["report_only"]["gate_reason_details"] == []
    assert observed["enforced"]["gate_reason_details"] == [
        {
            "details": {
                "partial_status_credit": 0.5,
                "source_statuses": {"agenda": "present", "packet": "missing"},
                "supporting_source_types": ["agenda", "packet"],
            },
            "gate_family": "document_aware_gate",
            "gate_id": "document_coverage_balance",
            "policy_action": "downgrade",
            "reason_codes": [REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD],
            "score": 0.5,
            "threshold": 1.0,
        }
    ]


def test_st030_enforced_authority_alignment_failure_blocks_publish_and_preserves_reason_lineage(
    monkeypatch,
    tmp_path,
) -> None:
    scenario = {fixture.fixture_id: fixture for fixture in load_fixture_catalog()}["st025-conflict-minutes-authoritative"]
    connection = create_test_connection()
    seed_fixture_scenario(connection=connection, scenario=scenario)
    orchestrator = LocalPipelineOrchestrator(connection)
    compose_input = assemble_fixture_compose(connection=connection, scenario=scenario)
    run_id = "run-st030-authority-block"
    ProcessingRunRepository(connection).create_pending_run(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        cycle_id="cycle-authority-block",
    )

    monkeypatch.setenv(
        "COUNCILSENSE_QG_CONFIG_JSON",
        json.dumps(
            {
                "defaults": {
                    "gate_mode": "enforced",
                    "enforcement_action": "downgrade",
                    "promotion_required": False,
                    "diagnostics_artifact_path": str(tmp_path / "authority-block-gate-diagnostics.jsonl"),
                }
            }
        ),
    )
    rollout_config = resolve_rollout_config(environment="local", cohort=PILOT_CITY_ID)
    summarize_payload, summarize_status = orchestrator._summarize_stage(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        meeting_id=scenario.meeting_id,
        source_id="source-st030-authority-block",
        source_type="minutes",
        extracted=_ExtractedPayload(
            text=compose_input.composed_text,
            artifact_id="artifact://st030-authority-block",
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
        authority_outcome="unresolved_conflict",
        publication_status="limited_confidence",
        reason_codes=(REASON_CODE_MISSING_AUTHORITATIVE_MINUTES, REASON_CODE_UNRESOLVED_SOURCE_CONFLICT),
        authoritative_source_type=None,
        authoritative_locator_precision=None,
        source_statuses={"minutes": "missing", "agenda": "present", "packet": "present"},
        preview_only=True,
    )

    stage = orchestrator._publish_stage(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        source_id="source-st030-authority-block",
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

    assert stage["status"] == "limited_confidence"
    assert stage["metadata"]["publication_id"] is None
    assert "quality_gate_publish_blocked" in stage["metadata"]["quality_gate_reason_codes"]
    assert "document_aware_authority_alignment_blocked_publish" in stage["metadata"]["quality_gate_reason_codes"]
    assert REASON_CODE_MISSING_AUTHORITATIVE_MINUTES in stage["metadata"]["quality_gate_reason_codes"]

    enforcement_outcome = stage["metadata"]["quality_gate_rollout"]["enforcement_outcome"]
    assert enforcement_outcome["decision"] == "enforce_block"
    assert len(enforcement_outcome["gate_reason_details"]) == 1
    detail = enforcement_outcome["gate_reason_details"][0]
    assert detail["gate_family"] == "document_aware_gate"
    assert detail["gate_id"] == "authority_alignment"
    assert detail["policy_action"] == "block"
    assert detail["reason_codes"] == [REASON_CODE_MISSING_AUTHORITATIVE_MINUTES]
    assert detail["score"] == 0.0
    assert detail["threshold"] == 1.0
    assert detail["details"]["authority_outcome"] == "unresolved_conflict"
    assert detail["details"]["authoritative_source_status"] == "missing"


@pytest.mark.parametrize(
    ("history_sequence", "current_outcome", "expected_eligible", "expected_evaluated_run_ids"),
    [
        (("pass",), "pass", True, ("run-history-001", "run-current")),
        (("pass", "fail"), "pass", False, ("run-history-002", "run-current")),
        (("fail", "pass"), "pass", True, ("run-history-002", "run-current")),
    ],
)
def test_st030_promotion_windows_require_two_consecutive_green_report_only_runs(
    history_sequence: tuple[str, ...],
    current_outcome: str,
    expected_eligible: bool,
    expected_evaluated_run_ids: tuple[str, ...],
) -> None:
    connection = create_test_connection()
    _seed_report_only_history(connection=connection, outcomes=history_sequence)

    promotion_status = compute_promotion_status(
        connection=connection,
        environment="local",
        cohort=PILOT_CITY_ID,
        required_consecutive_green_runs=2,
        current_run_diagnostics=_build_report_only_diagnostics(run_id="run-current", outcome=current_outcome),
    )

    assert promotion_status.eligible is expected_eligible
    assert promotion_status.evaluated_run_ids == expected_evaluated_run_ids
    assert promotion_status.consecutive_green_runs == (2 if expected_eligible else 0)
    assert promotion_status.eligible_window_run_ids == (
        expected_evaluated_run_ids[-2:] if expected_eligible else ()
    )


def test_st030_missing_document_aware_diagnostics_reset_promotion_progress_and_emit_artifact(tmp_path) -> None:
    connection = create_test_connection()
    _seed_report_only_history(connection=connection, outcomes=("pass",))
    current_diagnostics = _build_report_only_diagnostics(run_id="run-current", outcome="missing")
    config = resolve_rollout_config(environment="local", cohort=PILOT_CITY_ID)

    promotion_status = compute_promotion_status(
        connection=connection,
        environment="local",
        cohort=PILOT_CITY_ID,
        required_consecutive_green_runs=2,
        current_run_diagnostics=current_diagnostics,
    )
    artifact_path = tmp_path / "promotion-eligibility.jsonl"
    append_promotion_artifact(
        artifact_path=str(artifact_path),
        config=config,
        evaluated_at_run_id=current_diagnostics.run_id,
        promotion_status=promotion_status,
    )

    payload = json.loads(artifact_path.read_text(encoding="utf-8").strip())

    assert promotion_status.eligible is False
    assert promotion_status.consecutive_green_runs == 0
    assert promotion_status.evaluated_run_ids == ("run-current",)
    assert "promotion_reset_missing_document_aware_diagnostics" in promotion_status.reason_codes
    assert payload["evaluated_at_run_id"] == "run-current"
    assert payload["eligible"] is False
    assert payload["evaluated_run_ids"] == ["run-current"]
    assert payload["eligible_window_run_ids"] == []
    assert payload["evaluated_runs"][0]["run_id"] == "run-current"
    assert payload["evaluated_runs"][0]["diagnostics_present"] is False
    assert payload["evaluated_runs"][0]["gate_outcomes"] == []


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


def _seed_report_only_history(*, connection, outcomes: tuple[str, ...]) -> None:
    run_repository = ProcessingRunRepository(connection)
    for index, outcome in enumerate(outcomes, start=1):
        run_id = f"run-history-{index:03d}"
        run = run_repository.create_pending_run(
            run_id=run_id,
            city_id=PILOT_CITY_ID,
            cycle_id=f"cycle-{index:03d}",
        )
        run_repository.upsert_stage_outcome(
            outcome_id=f"outcome-publish-{run_id}",
            run_id=run.id,
            city_id=PILOT_CITY_ID,
            meeting_id=f"meeting-{run_id}",
            stage_name="publish",
            status="processed",
            metadata_json=json.dumps(
                {
                    "quality_gate_rollout": {
                        "environment": "local",
                        "cohort": PILOT_CITY_ID,
                        "gate_mode": "report_only",
                        "shadow_diagnostics": _build_report_only_diagnostics(
                            run_id=run_id,
                            outcome=outcome,
                        ).to_payload(),
                    }
                }
            ),
            started_at=datetime(2026, 3, 6, 10, index, 0, tzinfo=UTC).isoformat(),
            finished_at=datetime(2026, 3, 6, 10, index, 30, tzinfo=UTC).isoformat(),
        )


def _build_report_only_diagnostics(*, run_id: str, outcome: str):
    diagnostics = evaluate_shadow_gates(
        run_id=run_id,
        city_id=PILOT_CITY_ID,
        meeting_id=f"meeting-{run_id}",
        source_id=f"source-{run_id}",
        source_type="minutes",
        config=resolve_rollout_config(environment="local", cohort=PILOT_CITY_ID),
        source_text="Council adopted a publishable decision.",
        output=_sample_output(pointer_precision="section"),
        summarize_status="processed",
        extract_status="processed",
        summarize_fallback_used=False,
        document_aware_gate_input=(
            DocumentAwareGateInput(
                authority_outcome="minutes_authoritative",
                authority_reason_codes=(),
                authority_conflict_count=0,
                source_statuses={"minutes": "present", "agenda": "present", "packet": "present"},
                authoritative_locator_precision="precise",
                citation_precision_ratio=1.0,
                citation_pointer_count=3,
            )
            if outcome != "fail"
            else DocumentAwareGateInput(
                authority_outcome="missing_authoritative_minutes",
                authority_reason_codes=(REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,),
                authority_conflict_count=1,
                source_statuses={"minutes": "missing", "agenda": "present", "packet": "present"},
                authoritative_locator_precision=None,
                citation_precision_ratio=0.25,
                citation_pointer_count=2,
            )
        ),
    )
    if outcome == "missing":
        return replace(diagnostics, document_aware_report=None)
    return diagnostics


def _eligible_promotion_status() -> PromotionStatus:
    return PromotionStatus(
        eligible=True,
        consecutive_green_runs=2,
        required_consecutive_green_runs=2,
        evaluated_run_ids=("run-a", "run-b"),
        reason_codes=("promotion_prerequisites_satisfied",),
    )