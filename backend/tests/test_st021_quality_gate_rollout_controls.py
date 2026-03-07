from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any, cast

from councilsense.app.local_pipeline import LocalPipelineOrchestrator
from councilsense.app.quality_gate_rollout import (
    PromotionStatus,
    build_rollback_sequence,
    compute_promotion_status,
    decide_enforcement_outcome,
    evaluate_shadow_gates,
    resolve_rollout_config,
)
from councilsense.app.summarization import (
    ClaimEvidencePointer,
    QualityGateEnforcementOverride,
    SummarizationOutput,
    SummaryClaim,
    publish_summarization_output,
)
from councilsense.db import (
    MeetingSummaryRepository,
    MeetingWriteRepository,
    PILOT_CITY_ID,
    ProcessingRunRepository,
    apply_migrations,
    seed_city_registry,
)


def _init_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)
    return connection


def _sample_output() -> SummarizationOutput:
    return SummarizationOutput.from_sections(
        summary="Council approved a transportation amendment.",
        key_decisions=["Approved transportation amendment."],
        key_actions=["Staff will publish implementation timeline."],
        notable_topics=["Transportation Infrastructure", "Budget and Fiscal Planning", "Public Hearing Scheduling"],
        claims=(
            SummaryClaim(
                claim_text="Council approved transportation amendment.",
                evidence=(
                    ClaimEvidencePointer(
                        artifact_id="artifact://sample",
                        section_ref="minutes.section.2",
                        char_start=22,
                        char_end=79,
                        excerpt="Council approved transportation amendment.",
                    ),
                ),
                evidence_gap=False,
            ),
        ),
    )


def test_st021_flag_contract_resolves_with_environment_and_cohort_precedence() -> None:
    prior = os.environ.get("COUNCILSENSE_QG_CONFIG_JSON")
    os.environ["COUNCILSENSE_QG_CONFIG_JSON"] = json.dumps(
        {
            "defaults": {
                "topic_hardening_enabled": False,
                "specificity_retention_enabled": False,
                "evidence_projection_enabled": False,
                "gate_mode": "report_only",
                "promotion_required": True,
            },
            "environments": {
                "local": {
                    "topic_hardening_enabled": True,
                }
            },
            "cohorts": {
                "city-eagle-mountain-ut": {
                    "evidence_projection_enabled": True,
                }
            },
            "environment_cohorts": {
                "local:city-eagle-mountain-ut": {
                    "specificity_retention_enabled": True,
                    "gate_mode": "enforced",
                    "enforcement_action": "downgrade",
                }
            },
        }
    )

    try:
        config = resolve_rollout_config(environment="local", cohort="city-eagle-mountain-ut")
    finally:
        if prior is None:
            os.environ.pop("COUNCILSENSE_QG_CONFIG_JSON", None)
        else:
            os.environ["COUNCILSENSE_QG_CONFIG_JSON"] = prior

    assert config.mode == "enforced"
    assert config.enforcement_action == "downgrade"
    assert config.behavior_flags.topic_hardening_enabled is True
    assert config.behavior_flags.specificity_retention_enabled is True
    assert config.behavior_flags.evidence_projection_enabled is True


def test_st021_shadow_mode_emits_failures_but_policy_decision_remains_observe() -> None:
    config = resolve_rollout_config(environment="local", cohort="city-eagle-mountain-ut")
    diagnostics = evaluate_shadow_gates(
        run_id="run-shadow-1",
        city_id="city-eagle-mountain-ut",
        meeting_id="meeting-shadow-1",
        source_id="source-shadow-1",
        source_type="minutes",
        config=config,
        source_text="",
        output=SummarizationOutput.from_sections(
            summary="",
            key_decisions=[],
            key_actions=[],
            notable_topics=[],
            claims=[],
        ),
        summarize_status="processed",
        extract_status="processed",
        summarize_fallback_used=False,
    )

    assert diagnostics.all_gates_green is False
    promotion = PromotionStatus(
        eligible=True,
        consecutive_green_runs=2,
        required_consecutive_green_runs=2,
        evaluated_run_ids=("run-a", "run-b"),
        reason_codes=("promotion_prerequisites_satisfied",),
    )
    outcome = decide_enforcement_outcome(config=config, diagnostics=diagnostics, promotion_status=promotion)
    assert outcome.decision == "observe"


def test_st021_promotion_requires_two_consecutive_green_runs_and_resets_on_failure() -> None:
    connection = _init_connection()
    run_repository = ProcessingRunRepository(connection)

    for run_id, green in (
        ("run-st021-001", True),
        ("run-st021-002", False),
        ("run-st021-003", True),
        ("run-st021-004", True),
    ):
        run = run_repository.create_pending_run(run_id=run_id, city_id=PILOT_CITY_ID, cycle_id=f"cycle-{run_id}")
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
                        "shadow_diagnostics": {
                            "diagnostics_complete": True,
                            "all_gates_green": green,
                            "environment": "local",
                            "cohort": PILOT_CITY_ID,
                        }
                    }
                }
            ),
            started_at=datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC).isoformat(),
            finished_at=datetime(2026, 3, 4, 9, 1, 0, tzinfo=UTC).isoformat(),
        )

    promotion_status = compute_promotion_status(
        connection=connection,
        environment="local",
        cohort=PILOT_CITY_ID,
        required_consecutive_green_runs=2,
    )

    assert promotion_status.eligible is True
    assert promotion_status.consecutive_green_runs == 2


def test_st021_enforcement_override_supports_downgrade_without_contract_break() -> None:
    connection = _init_connection()
    MeetingWriteRepository(connection).upsert_meeting(
        meeting_id="meeting-st021-downgrade",
        meeting_uid="meeting-st021-downgrade-uid",
        city_id=PILOT_CITY_ID,
        title="ST-021 downgrade meeting",
    )

    run = ProcessingRunRepository(connection).create_pending_run(
        run_id="run-st021-downgrade",
        city_id=PILOT_CITY_ID,
        cycle_id="2026-03-04T12:00:00Z",
    )

    result = publish_summarization_output(
        repository=MeetingSummaryRepository(connection),
        publication_id="pub-st021-downgrade",
        meeting_id="meeting-st021-downgrade",
        processing_run_id=run.id,
        publish_stage_outcome_id=None,
        version_no=1,
        base_confidence_label="high",
        output=_sample_output(),
        published_at="2026-03-04T12:01:00Z",
        enforcement_override=QualityGateEnforcementOverride(
            publication_status="limited_confidence",
            confidence_label="limited_confidence",
            reason_codes=("quality_gate_publish_downgraded",),
        ),
    )

    assert result.publication.publication_status == "limited_confidence"
    assert "quality_gate_publish_downgraded" in result.quality_gate.reason_codes


def test_st021_local_pipeline_enforced_block_keeps_publish_non_processed() -> None:
    connection = _init_connection()
    meeting = MeetingWriteRepository(connection).upsert_meeting(
        meeting_id="meeting-st021-block",
        meeting_uid="meeting-st021-block-uid",
        city_id=PILOT_CITY_ID,
        title="Meeting with sparse evidence",
    )

    prior = os.environ.get("COUNCILSENSE_QG_CONFIG_JSON")
    os.environ["COUNCILSENSE_QG_CONFIG_JSON"] = json.dumps(
        {
            "defaults": {
                "gate_mode": "enforced",
                "enforcement_action": "block",
                "promotion_required": False,
                "topic_hardening_enabled": True,
                "specificity_retention_enabled": True,
                "evidence_projection_enabled": True,
            }
        }
    )

    try:
        orchestrator = LocalPipelineOrchestrator(connection)
        result = orchestrator.process_latest(
            run_id="run-st021-block",
            city_id=PILOT_CITY_ID,
            meeting_id=meeting.id,
            ingest_stage_metadata=None,
            llm_provider="none",
            ollama_endpoint=None,
            ollama_model=None,
            ollama_timeout_seconds=20.0,
        )
    finally:
        if prior is None:
            os.environ.pop("COUNCILSENSE_QG_CONFIG_JSON", None)
        else:
            os.environ["COUNCILSENSE_QG_CONFIG_JSON"] = prior

    publish_stage = next(stage for stage in result.stage_outcomes if stage["stage"] == "publish")
    metadata = cast(dict[str, Any], publish_stage["metadata"])
    assert publish_stage["status"] == "limited_confidence"
    assert metadata["publication_id"] is None
    assert "quality_gate_publish_blocked" in cast(list[str], metadata["quality_gate_reason_codes"])


def test_st021_rollback_sequence_is_reverse_order_then_report_only_reversion() -> None:
    sequence = build_rollback_sequence()
    controls = [row["control"] for row in sequence]
    assert controls == [
        "specificity_retention_enabled",
        "evidence_projection_enabled",
        "topic_hardening_enabled",
        "gate_mode",
    ]

