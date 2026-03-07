from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from councilsense.app.summarization import SUMMARIZATION_CONTRACT_VERSION, SummarizationOutput
from councilsense.app.st030_document_aware_gates import (
    DocumentAwareGateThresholds,
    default_document_aware_thresholds_payload,
    parse_document_aware_thresholds,
)


QUALITY_GATE_ROLLOUT_SCHEMA_VERSION = "st-021-quality-gate-rollout-v1"

GateIdentifier = Literal["gate_a_contract_safety", "gate_b_quality_parity", "gate_c_operational_reliability"]
GateMode = Literal["report_only", "enforced"]
EnforcementAction = Literal["downgrade", "block"]
PolicyDecision = Literal["observe", "enforce_pass", "enforce_downgrade", "enforce_block"]


@dataclass(frozen=True)
class QualityGateBehaviorFlags:
    topic_hardening_enabled: bool
    specificity_retention_enabled: bool
    evidence_projection_enabled: bool


@dataclass(frozen=True)
class QualityGateRolloutConfig:
    environment: str
    cohort: str
    mode: GateMode
    enforcement_action: EnforcementAction
    promotion_required: bool
    behavior_flags: QualityGateBehaviorFlags
    diagnostics_artifact_path: str | None
    document_aware_thresholds: DocumentAwareGateThresholds


@dataclass(frozen=True)
class GateDiagnostic:
    gate_id: GateIdentifier
    passed: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ShadowGateDiagnostics:
    schema_version: str
    generated_at_utc: str
    run_id: str
    city_id: str
    meeting_id: str
    environment: str
    cohort: str
    gate_mode: GateMode
    diagnostics_complete: bool
    all_gates_green: bool
    gates: tuple[GateDiagnostic, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generated_at_utc": self.generated_at_utc,
            "run_id": self.run_id,
            "city_id": self.city_id,
            "meeting_id": self.meeting_id,
            "environment": self.environment,
            "cohort": self.cohort,
            "gate_mode": self.gate_mode,
            "diagnostics_complete": self.diagnostics_complete,
            "all_gates_green": self.all_gates_green,
            "gates": [
                {
                    "gate_id": gate.gate_id,
                    "passed": gate.passed,
                    "reason_codes": list(gate.reason_codes),
                }
                for gate in self.gates
            ],
        }


@dataclass(frozen=True)
class PromotionStatus:
    eligible: bool
    consecutive_green_runs: int
    required_consecutive_green_runs: int
    evaluated_run_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "consecutive_green_runs": self.consecutive_green_runs,
            "required_consecutive_green_runs": self.required_consecutive_green_runs,
            "evaluated_run_ids": list(self.evaluated_run_ids),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class EnforcementOutcome:
    decision: PolicyDecision
    reason_codes: tuple[str, ...]


def _parse_bool_field(*, payload: dict[str, object], key: str) -> bool | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    raise ValueError(f"{key} must be a boolean when provided")


def _parse_mode_field(*, payload: dict[str, object], key: str = "gate_mode") -> GateMode | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if raw in {"report_only", "enforced"}:
        return cast(GateMode, raw)
    raise ValueError(f"{key} must be one of: report_only, enforced")


def _parse_action_field(*, payload: dict[str, object], key: str = "enforcement_action") -> EnforcementAction | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if raw in {"downgrade", "block"}:
        return cast(EnforcementAction, raw)
    raise ValueError(f"{key} must be one of: downgrade, block")


def _parse_path_field(*, payload: dict[str, object], key: str) -> str | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raise ValueError(f"{key} must be a non-empty string when provided")


def _merge_profile(*, base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in override.items():
        if value is not None:
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = _merge_profile(base=cast(dict[str, object], merged[key]), override=value)
            else:
                merged[key] = value
    return merged


def resolve_rollout_config(*, environment: str | None, cohort: str | None) -> QualityGateRolloutConfig:
    resolved_environment = (environment or os.getenv("COUNCILSENSE_RUNTIME_ENV") or "local").strip().lower() or "local"
    resolved_cohort = (cohort or os.getenv("COUNCILSENSE_QG_COHORT") or "default").strip() or "default"

    defaults: dict[str, object] = {
        "topic_hardening_enabled": True,
        "specificity_retention_enabled": True,
        "evidence_projection_enabled": True,
        "gate_mode": "report_only",
        "enforcement_action": "downgrade",
        "promotion_required": True,
        "diagnostics_artifact_path": os.getenv("COUNCILSENSE_QG_DIAGNOSTICS_ARTIFACT_PATH"),
        "document_aware_thresholds": default_document_aware_thresholds_payload(),
    }

    raw_json = os.getenv("COUNCILSENSE_QG_CONFIG_JSON")
    if raw_json:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError("COUNCILSENSE_QG_CONFIG_JSON must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("COUNCILSENSE_QG_CONFIG_JSON must decode to an object")

        matrix_defaults = payload.get("defaults")
        matrix_environments = payload.get("environments")
        matrix_cohorts = payload.get("cohorts")
        matrix_environment_cohorts = payload.get("environment_cohorts")

        if matrix_defaults is not None:
            if not isinstance(matrix_defaults, dict):
                raise ValueError("COUNCILSENSE_QG_CONFIG_JSON.defaults must be an object")
            defaults = _merge_profile(base=defaults, override=matrix_defaults)

        if matrix_environments is not None:
            if not isinstance(matrix_environments, dict):
                raise ValueError("COUNCILSENSE_QG_CONFIG_JSON.environments must be an object")
            selected_environment = matrix_environments.get(resolved_environment)
            if selected_environment is not None:
                if not isinstance(selected_environment, dict):
                    raise ValueError(
                        f"COUNCILSENSE_QG_CONFIG_JSON.environments[{resolved_environment}] must be an object"
                    )
                defaults = _merge_profile(base=defaults, override=selected_environment)

        if matrix_cohorts is not None:
            if not isinstance(matrix_cohorts, dict):
                raise ValueError("COUNCILSENSE_QG_CONFIG_JSON.cohorts must be an object")
            selected_cohort = matrix_cohorts.get(resolved_cohort)
            if selected_cohort is not None:
                if not isinstance(selected_cohort, dict):
                    raise ValueError(f"COUNCILSENSE_QG_CONFIG_JSON.cohorts[{resolved_cohort}] must be an object")
                defaults = _merge_profile(base=defaults, override=selected_cohort)

        if matrix_environment_cohorts is not None:
            if not isinstance(matrix_environment_cohorts, dict):
                raise ValueError("COUNCILSENSE_QG_CONFIG_JSON.environment_cohorts must be an object")
            env_cohort_key = f"{resolved_environment}:{resolved_cohort}"
            selected_env_cohort = matrix_environment_cohorts.get(env_cohort_key)
            if selected_env_cohort is not None:
                if not isinstance(selected_env_cohort, dict):
                    raise ValueError(
                        f"COUNCILSENSE_QG_CONFIG_JSON.environment_cohorts[{env_cohort_key}] must be an object"
                    )
                defaults = _merge_profile(base=defaults, override=selected_env_cohort)

    mode = _parse_mode_field(payload=defaults) or "report_only"
    enforcement_action = _parse_action_field(payload=defaults) or "downgrade"
    promotion_required = _parse_bool_field(payload=defaults, key="promotion_required")
    if promotion_required is None:
        promotion_required = True

    topic_hardening_enabled = _parse_bool_field(payload=defaults, key="topic_hardening_enabled")
    if topic_hardening_enabled is None:
        topic_hardening_enabled = True

    specificity_retention_enabled = _parse_bool_field(payload=defaults, key="specificity_retention_enabled")
    if specificity_retention_enabled is None:
        specificity_retention_enabled = True

    evidence_projection_enabled = _parse_bool_field(payload=defaults, key="evidence_projection_enabled")
    if evidence_projection_enabled is None:
        evidence_projection_enabled = True

    diagnostics_artifact_path = _parse_path_field(payload=defaults, key="diagnostics_artifact_path")
    raw_document_aware_thresholds = defaults.get("document_aware_thresholds")
    if raw_document_aware_thresholds is not None and not isinstance(raw_document_aware_thresholds, dict):
        raise ValueError("document_aware_thresholds must be an object when provided")
    document_aware_thresholds = parse_document_aware_thresholds(
        payload=cast(dict[str, object] | None, raw_document_aware_thresholds),
    )

    if mode == "report_only" and enforcement_action == "block":
        raise ValueError("enforcement_action=block is not valid when gate_mode=report_only")

    return QualityGateRolloutConfig(
        environment=resolved_environment,
        cohort=resolved_cohort,
        mode=mode,
        enforcement_action=enforcement_action,
        promotion_required=promotion_required,
        behavior_flags=QualityGateBehaviorFlags(
            topic_hardening_enabled=topic_hardening_enabled,
            specificity_retention_enabled=specificity_retention_enabled,
            evidence_projection_enabled=evidence_projection_enabled,
        ),
        diagnostics_artifact_path=diagnostics_artifact_path,
        document_aware_thresholds=document_aware_thresholds,
    )


def evaluate_shadow_gates(
    *,
    run_id: str,
    city_id: str,
    meeting_id: str,
    config: QualityGateRolloutConfig,
    source_text: str,
    output: SummarizationOutput,
    summarize_status: str,
    extract_status: str,
    summarize_fallback_used: bool,
) -> ShadowGateDiagnostics:
    from councilsense.app.st017_fixture_scorecard import compute_dimension_scores

    gate_a_reasons: list[str] = []
    if output.contract_version != SUMMARIZATION_CONTRACT_VERSION:
        gate_a_reasons.append("contract_version_mismatch")
    if not output.summary.strip():
        gate_a_reasons.append("summary_missing")
    if not output.key_decisions:
        gate_a_reasons.append("key_decisions_missing")
    if not output.key_actions:
        gate_a_reasons.append("key_actions_missing")
    if not output.claims:
        gate_a_reasons.append("claims_missing")

    dimension_scores = compute_dimension_scores(fixture_text=source_text, output=output)
    gate_b_reasons = [
        f"{name}_below_threshold"
        for name, score in dimension_scores.items()
        if not score.passed
    ]

    gate_c_reasons: list[str] = []
    if extract_status == "failed":
        gate_c_reasons.append("extract_stage_failed")
    if summarize_status == "failed":
        gate_c_reasons.append("summarize_stage_failed")
    if summarize_fallback_used:
        gate_c_reasons.append("summarize_fallback_used")

    diagnostics = (
        GateDiagnostic(
            gate_id="gate_a_contract_safety",
            passed=not gate_a_reasons,
            reason_codes=tuple(gate_a_reasons) if gate_a_reasons else ("gate_pass",),
        ),
        GateDiagnostic(
            gate_id="gate_b_quality_parity",
            passed=not gate_b_reasons,
            reason_codes=tuple(gate_b_reasons) if gate_b_reasons else ("gate_pass",),
        ),
        GateDiagnostic(
            gate_id="gate_c_operational_reliability",
            passed=not gate_c_reasons,
            reason_codes=tuple(gate_c_reasons) if gate_c_reasons else ("gate_pass",),
        ),
    )

    all_gates_green = all(gate.passed for gate in diagnostics)
    return ShadowGateDiagnostics(
        schema_version=QUALITY_GATE_ROLLOUT_SCHEMA_VERSION,
        generated_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat(),
        run_id=run_id,
        city_id=city_id,
        meeting_id=meeting_id,
        environment=config.environment,
        cohort=config.cohort,
        gate_mode=config.mode,
        diagnostics_complete=True,
        all_gates_green=all_gates_green,
        gates=diagnostics,
    )


def append_shadow_diagnostics_artifact(*, artifact_path: str | None, diagnostics: ShadowGateDiagnostics) -> None:
    if artifact_path is None:
        return
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = diagnostics.to_payload()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{json.dumps(payload, sort_keys=True)}\n")


def _read_shadow_diagnostics_from_metadata(*, metadata_json: str | None) -> dict[str, object] | None:
    if metadata_json is None:
        return None
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    quality_gate_payload = parsed.get("quality_gate_rollout")
    if not isinstance(quality_gate_payload, dict):
        return None
    diagnostics = quality_gate_payload.get("shadow_diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    return diagnostics


def compute_promotion_status(
    *,
    connection: sqlite3.Connection,
    environment: str,
    cohort: str,
    required_consecutive_green_runs: int = 2,
) -> PromotionStatus:
    rows = connection.execute(
        """
        SELECT run_id, metadata_json
        FROM processing_stage_outcomes
        WHERE stage_name = 'publish'
        ORDER BY created_at DESC, id DESC
        LIMIT 100
        """
    ).fetchall()

    evaluated_run_ids: list[str] = []
    consecutive_green_runs = 0

    for row in rows:
        run_id = str(row[0])
        diagnostics = _read_shadow_diagnostics_from_metadata(metadata_json=(str(row[1]) if row[1] is not None else None))
        if diagnostics is None:
            consecutive_green_runs = 0
            continue

        if diagnostics.get("environment") != environment or diagnostics.get("cohort") != cohort:
            continue

        evaluated_run_ids.append(run_id)
        diagnostics_complete = bool(diagnostics.get("diagnostics_complete", False))
        all_green = bool(diagnostics.get("all_gates_green", False))
        if diagnostics_complete and all_green:
            consecutive_green_runs += 1
            if consecutive_green_runs >= required_consecutive_green_runs:
                break
            continue
        consecutive_green_runs = 0

    eligible = consecutive_green_runs >= required_consecutive_green_runs
    reason_codes: list[str] = []
    if eligible:
        reason_codes.append("promotion_prerequisites_satisfied")
    else:
        reason_codes.append("insufficient_consecutive_green_runs")

    return PromotionStatus(
        eligible=eligible,
        consecutive_green_runs=consecutive_green_runs,
        required_consecutive_green_runs=required_consecutive_green_runs,
        evaluated_run_ids=tuple(evaluated_run_ids),
        reason_codes=tuple(reason_codes),
    )


def decide_enforcement_outcome(
    *,
    config: QualityGateRolloutConfig,
    diagnostics: ShadowGateDiagnostics,
    promotion_status: PromotionStatus,
) -> EnforcementOutcome:
    if config.mode == "report_only":
        return EnforcementOutcome(decision="observe", reason_codes=("report_only_mode",))

    if config.promotion_required and not promotion_status.eligible:
        return EnforcementOutcome(decision="observe", reason_codes=("promotion_prerequisites_not_met",))

    if diagnostics.all_gates_green:
        return EnforcementOutcome(decision="enforce_pass", reason_codes=("all_gates_green",))

    if config.enforcement_action == "block":
        return EnforcementOutcome(decision="enforce_block", reason_codes=("gate_failure_blocked_publish",))

    return EnforcementOutcome(decision="enforce_downgrade", reason_codes=("gate_failure_downgraded_publish",))


def build_quality_gate_rollout_metadata(
    *,
    config: QualityGateRolloutConfig,
    diagnostics: ShadowGateDiagnostics,
    promotion_status: PromotionStatus,
    enforcement_outcome: EnforcementOutcome,
) -> dict[str, object]:
    return {
        "schema_version": QUALITY_GATE_ROLLOUT_SCHEMA_VERSION,
        "environment": config.environment,
        "cohort": config.cohort,
        "gate_mode": config.mode,
        "enforcement_action": config.enforcement_action,
        "promotion_required": config.promotion_required,
        "feature_flags": {
            "topic_hardening_enabled": config.behavior_flags.topic_hardening_enabled,
            "specificity_retention_enabled": config.behavior_flags.specificity_retention_enabled,
            "evidence_projection_enabled": config.behavior_flags.evidence_projection_enabled,
        },
        "shadow_diagnostics": diagnostics.to_payload(),
        "promotion_status": promotion_status.to_payload(),
        "enforcement_outcome": {
            "decision": enforcement_outcome.decision,
            "reason_codes": list(enforcement_outcome.reason_codes),
        },
    }


def build_rollback_sequence() -> tuple[dict[str, object], ...]:
    return (
        {
            "step": 1,
            "control": "specificity_retention_enabled",
            "action": "disable",
            "post_check": "anchor carry-through may be disabled while publish remains report-only or enforced per mode",
        },
        {
            "step": 2,
            "control": "evidence_projection_enabled",
            "action": "disable",
            "post_check": "evidence projection precision is disabled after specificity retention",
        },
        {
            "step": 3,
            "control": "topic_hardening_enabled",
            "action": "disable",
            "post_check": "topic hardening is disabled after specificity and evidence controls",
        },
        {
            "step": 4,
            "control": "gate_mode",
            "action": "set_report_only",
            "post_check": "enforcement is disabled and gates run in report-only mode",
        },
    )
