from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from councilsense.app.summarization import SUMMARIZATION_CONTRACT_VERSION, SummarizationOutput
from councilsense.app.st030_document_aware_gates import (
    DocumentAwareGateDimension,
    DocumentAwareGateEvaluation,
    DocumentAwareGateInput,
    DocumentAwareGateThresholds,
    default_document_aware_thresholds_payload,
    evaluate_document_aware_gates,
    parse_document_aware_thresholds,
)


QUALITY_GATE_ROLLOUT_SCHEMA_VERSION = "st-021-quality-gate-rollout-v1"
DOCUMENT_AWARE_DIAGNOSTICS_SCHEMA_VERSION = "st-030-report-only-gate-diagnostics-v1"
PROMOTION_ARTIFACT_SCHEMA_VERSION = "st-030-promotion-eligibility-v1"
ROLLBACK_CONTROL_PLAN_SCHEMA_VERSION = "st-030-rollback-controls-v1"

GateIdentifier = Literal["gate_a_contract_safety", "gate_b_quality_parity", "gate_c_operational_reliability"]
GateMode = Literal["report_only", "enforced"]
EnforcementAction = Literal["downgrade", "block"]
PolicyDecision = Literal["observe", "enforce_pass", "enforce_downgrade", "enforce_block"]
DiagnosticGateStatus = Literal["pass", "fail"]
GateReasonFamily = Literal["shadow_gate", "document_aware_gate"]


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
    promotion_artifact_path: str | None
    document_aware_thresholds: DocumentAwareGateThresholds


@dataclass(frozen=True)
class GateDiagnostic:
    gate_id: GateIdentifier
    passed: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class DocumentAwareGateDiagnostic:
    gate_id: DocumentAwareGateDimension
    status: DiagnosticGateStatus
    score: float
    threshold: float
    passed: bool
    reason_codes: tuple[str, ...]
    details: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "score": self.score,
            "threshold": self.threshold,
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class DocumentAwareReportOnlyDiagnostics:
    schema_version: str
    contract_version: str
    evaluation_mode: str
    decision_impact: str
    diagnostics_complete: bool
    all_gates_green: bool
    thresholds: dict[str, object]
    gates: tuple[DocumentAwareGateDiagnostic, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "contract_version": self.contract_version,
            "evaluation_mode": self.evaluation_mode,
            "decision_impact": self.decision_impact,
            "diagnostics_complete": self.diagnostics_complete,
            "all_gates_green": self.all_gates_green,
            "thresholds": dict(self.thresholds),
            "gates": [gate.to_payload() for gate in self.gates],
        }


@dataclass(frozen=True)
class ShadowGateDiagnostics:
    schema_version: str
    generated_at_utc: str
    run_id: str
    city_id: str
    meeting_id: str
    source_id: str | None
    source_type: str | None
    environment: str
    cohort: str
    promotion_scope_key: str
    gate_mode: GateMode
    diagnostics_complete: bool
    all_gates_green: bool
    gates: tuple[GateDiagnostic, ...]
    document_aware_report: DocumentAwareReportOnlyDiagnostics | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generated_at_utc": self.generated_at_utc,
            "run_id": self.run_id,
            "city_id": self.city_id,
            "meeting_id": self.meeting_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "environment": self.environment,
            "cohort": self.cohort,
            "promotion_scope_key": self.promotion_scope_key,
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
            "document_aware_report": (
                None if self.document_aware_report is None else self.document_aware_report.to_payload()
            ),
        }


@dataclass(frozen=True)
class PromotionStatus:
    eligible: bool
    consecutive_green_runs: int
    required_consecutive_green_runs: int
    evaluated_run_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    evaluated_runs: tuple["PromotionRunEvaluation", ...] = ()
    eligible_window_run_ids: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "consecutive_green_runs": self.consecutive_green_runs,
            "required_consecutive_green_runs": self.required_consecutive_green_runs,
            "evaluated_run_ids": list(self.evaluated_run_ids),
            "reason_codes": list(self.reason_codes),
            "evaluated_runs": [run.to_payload() for run in self.evaluated_runs],
            "eligible_window_run_ids": list(self.eligible_window_run_ids),
        }


@dataclass(frozen=True)
class PromotionGateOutcome:
    gate_id: str
    status: DiagnosticGateStatus
    passed: bool
    reason_codes: tuple[str, ...]
    score: float | None = None
    threshold: float | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "gate_id": self.gate_id,
            "status": self.status,
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
        }
        if self.score is not None:
            payload["score"] = self.score
        if self.threshold is not None:
            payload["threshold"] = self.threshold
        return payload


@dataclass(frozen=True)
class PromotionRunEvaluation:
    run_id: str
    gate_mode: GateMode | None
    diagnostics_present: bool
    diagnostics_complete: bool
    all_gates_green: bool
    green_for_promotion: bool
    consecutive_green_runs_after_evaluation: int
    gate_outcomes: tuple[PromotionGateOutcome, ...]
    reason_codes: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "gate_mode": self.gate_mode,
            "diagnostics_present": self.diagnostics_present,
            "diagnostics_complete": self.diagnostics_complete,
            "all_gates_green": self.all_gates_green,
            "green_for_promotion": self.green_for_promotion,
            "consecutive_green_runs_after_evaluation": self.consecutive_green_runs_after_evaluation,
            "gate_outcomes": [gate.to_payload() for gate in self.gate_outcomes],
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class PromotionArtifact:
    schema_version: str
    generated_at_utc: str
    environment: str
    cohort: str
    promotion_scope_key: str
    evaluated_at_run_id: str
    eligible: bool
    required_consecutive_green_runs: int
    consecutive_green_runs: int
    reason_codes: tuple[str, ...]
    evaluated_run_ids: tuple[str, ...]
    eligible_window_run_ids: tuple[str, ...]
    evaluated_runs: tuple[PromotionRunEvaluation, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generated_at_utc": self.generated_at_utc,
            "environment": self.environment,
            "cohort": self.cohort,
            "promotion_scope_key": self.promotion_scope_key,
            "evaluated_at_run_id": self.evaluated_at_run_id,
            "eligible": self.eligible,
            "required_consecutive_green_runs": self.required_consecutive_green_runs,
            "consecutive_green_runs": self.consecutive_green_runs,
            "reason_codes": list(self.reason_codes),
            "evaluated_run_ids": list(self.evaluated_run_ids),
            "eligible_window_run_ids": list(self.eligible_window_run_ids),
            "evaluated_runs": [run.to_payload() for run in self.evaluated_runs],
        }


@dataclass(frozen=True)
class RollbackControlStep:
    step: int
    control: str
    action: str
    pre_check: str
    post_check: str
    resulting_mode: GateMode

    def to_payload(self) -> dict[str, object]:
        return {
            "step": self.step,
            "control": self.control,
            "action": self.action,
            "pre_check": self.pre_check,
            "post_check": self.post_check,
            "resulting_mode": self.resulting_mode,
        }


@dataclass(frozen=True)
class RollbackControlProfile:
    profile_id: str
    goal: str
    prerequisite: str | None
    steps: tuple[RollbackControlStep, ...]

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "profile_id": self.profile_id,
            "goal": self.goal,
            "steps": [step.to_payload() for step in self.steps],
        }
        if self.prerequisite is not None:
            payload["prerequisite"] = self.prerequisite
        return payload


@dataclass(frozen=True)
class RollbackEscalationPolicy:
    primary_owner: str
    secondary_owner: str
    escalation_owner: str
    paging_route: tuple[str, ...]
    escalation_trigger: str

    def to_payload(self) -> dict[str, object]:
        return {
            "primary_owner": self.primary_owner,
            "secondary_owner": self.secondary_owner,
            "escalation_owner": self.escalation_owner,
            "paging_route": list(self.paging_route),
            "escalation_trigger": self.escalation_trigger,
        }


@dataclass(frozen=True)
class RollbackControlPlan:
    schema_version: str
    schema_rollback_required: bool
    profiles: tuple[RollbackControlProfile, ...]
    escalation_policy: RollbackEscalationPolicy

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "schema_rollback_required": self.schema_rollback_required,
            "profiles": [profile.to_payload() for profile in self.profiles],
            "escalation_policy": self.escalation_policy.to_payload(),
        }


@dataclass(frozen=True)
class EnforcementOutcome:
    decision: PolicyDecision
    reason_codes: tuple[str, ...]
    gate_reason_details: tuple["GateReasonDetail", ...] = ()


@dataclass(frozen=True)
class GateReasonDetail:
    gate_family: GateReasonFamily
    gate_id: str
    policy_action: EnforcementAction
    reason_codes: tuple[str, ...]
    score: float | None = None
    threshold: float | None = None
    details: dict[str, object] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "gate_family": self.gate_family,
            "gate_id": self.gate_id,
            "policy_action": self.policy_action,
            "reason_codes": list(self.reason_codes),
        }
        if self.score is not None:
            payload["score"] = self.score
        if self.threshold is not None:
            payload["threshold"] = self.threshold
        if self.details:
            payload["details"] = dict(self.details)
        return payload


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
        "promotion_artifact_path": os.getenv("COUNCILSENSE_QG_PROMOTION_ARTIFACT_PATH"),
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
    promotion_artifact_path = _parse_path_field(payload=defaults, key="promotion_artifact_path")
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
        promotion_artifact_path=promotion_artifact_path,
        document_aware_thresholds=document_aware_thresholds,
    )


def evaluate_shadow_gates(
    *,
    run_id: str,
    city_id: str,
    meeting_id: str,
    source_id: str | None,
    source_type: str | None,
    config: QualityGateRolloutConfig,
    source_text: str,
    output: SummarizationOutput,
    summarize_status: str,
    extract_status: str,
    summarize_fallback_used: bool,
    document_aware_gate_input: DocumentAwareGateInput | None = None,
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
    document_aware_report = None
    if document_aware_gate_input is not None:
        document_aware_report = _build_document_aware_diagnostics(
            gate_input=document_aware_gate_input,
            thresholds=config.document_aware_thresholds,
            evaluation_mode=config.mode,
        )
    return ShadowGateDiagnostics(
        schema_version=QUALITY_GATE_ROLLOUT_SCHEMA_VERSION,
        generated_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat(),
        run_id=run_id,
        city_id=city_id,
        meeting_id=meeting_id,
        source_id=source_id,
        source_type=source_type,
        environment=config.environment,
        cohort=config.cohort,
        promotion_scope_key=f"{config.environment}:{config.cohort}",
        gate_mode=config.mode,
        diagnostics_complete=True,
        all_gates_green=all_gates_green,
        gates=diagnostics,
        document_aware_report=document_aware_report,
    )


def _build_document_aware_diagnostics(
    *,
    gate_input: DocumentAwareGateInput,
    thresholds: DocumentAwareGateThresholds,
    evaluation_mode: GateMode,
) -> DocumentAwareReportOnlyDiagnostics:
    evaluation = evaluate_document_aware_gates(gate_input=gate_input, thresholds=thresholds)
    return DocumentAwareReportOnlyDiagnostics(
        schema_version=DOCUMENT_AWARE_DIAGNOSTICS_SCHEMA_VERSION,
        contract_version=evaluation.schema_version,
        evaluation_mode=evaluation_mode,
        decision_impact=("non_blocking" if evaluation_mode == "report_only" else "policy_driven"),
        diagnostics_complete=True,
        all_gates_green=evaluation.all_dimensions_passed,
        thresholds=thresholds.to_payload(),
        gates=_document_aware_gate_diagnostics(evaluation=evaluation),
    )


def _document_aware_gate_diagnostics(
    *,
    evaluation: DocumentAwareGateEvaluation,
) -> tuple[DocumentAwareGateDiagnostic, ...]:
    return tuple(
        DocumentAwareGateDiagnostic(
            gate_id=result.dimension,
            status=("pass" if result.passed else "fail"),
            score=result.score,
            threshold=result.min_score,
            passed=result.passed,
            reason_codes=result.reason_codes,
            details=result.details,
        )
        for result in evaluation.dimensions
    )


def append_shadow_diagnostics_artifact(*, artifact_path: str | None, diagnostics: ShadowGateDiagnostics) -> None:
    if artifact_path is None:
        return
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = diagnostics.to_payload()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{json.dumps(payload, sort_keys=True)}\n")


def _read_quality_gate_rollout_from_metadata(*, metadata_json: str | None) -> dict[str, object] | None:
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
    return quality_gate_payload


def _read_shadow_diagnostics_from_metadata(*, metadata_json: str | None) -> dict[str, object] | None:
    quality_gate_payload = _read_quality_gate_rollout_from_metadata(metadata_json=metadata_json)
    if quality_gate_payload is None:
        return None
    diagnostics = quality_gate_payload.get("shadow_diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    return diagnostics


def _dedupe_reason_codes(*, reason_codes: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for reason_code in reason_codes:
        if reason_code in seen:
            continue
        seen.add(reason_code)
        deduped.append(reason_code)
    return tuple(deduped)


def _shadow_gate_outcomes_from_payload(*, shadow_diagnostics: dict[str, object]) -> tuple[PromotionGateOutcome, ...]:
    gates = shadow_diagnostics.get("gates")
    if not isinstance(gates, list):
        return ()
    outcomes: list[PromotionGateOutcome] = []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        gate_id = gate.get("gate_id")
        if not isinstance(gate_id, str):
            continue
        passed = bool(gate.get("passed", False))
        raw_reason_codes = gate.get("reason_codes")
        reason_codes = (
            tuple(code for code in raw_reason_codes if isinstance(code, str))
            if isinstance(raw_reason_codes, list)
            else (("gate_pass",) if passed else ())
        )
        outcomes.append(
            PromotionGateOutcome(
                gate_id=gate_id,
                status=("pass" if passed else "fail"),
                passed=passed,
                reason_codes=reason_codes,
            )
        )
    return tuple(outcomes)


def _document_aware_gate_outcomes_from_payload(
    *,
    document_aware_report: dict[str, object],
) -> tuple[PromotionGateOutcome, ...]:
    gates = document_aware_report.get("gates")
    if not isinstance(gates, list):
        return ()
    outcomes: list[PromotionGateOutcome] = []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        gate_id = gate.get("gate_id")
        status = gate.get("status")
        if not isinstance(gate_id, str) or status not in {"pass", "fail"}:
            continue
        raw_reason_codes = gate.get("reason_codes")
        reason_codes = tuple(code for code in raw_reason_codes if isinstance(code, str)) if isinstance(raw_reason_codes, list) else ()
        score = gate.get("score")
        threshold = gate.get("threshold")
        outcomes.append(
            PromotionGateOutcome(
                gate_id=gate_id,
                status=cast(DiagnosticGateStatus, status),
                passed=bool(gate.get("passed", status == "pass")),
                reason_codes=reason_codes,
                score=float(score) if isinstance(score, (int, float)) else None,
                threshold=float(threshold) if isinstance(threshold, (int, float)) else None,
            )
        )
    return tuple(outcomes)


def _with_streak(
    *,
    evaluation: PromotionRunEvaluation,
    consecutive_green_runs_after_evaluation: int,
) -> PromotionRunEvaluation:
    return PromotionRunEvaluation(
        run_id=evaluation.run_id,
        gate_mode=evaluation.gate_mode,
        diagnostics_present=evaluation.diagnostics_present,
        diagnostics_complete=evaluation.diagnostics_complete,
        all_gates_green=evaluation.all_gates_green,
        green_for_promotion=evaluation.green_for_promotion,
        consecutive_green_runs_after_evaluation=consecutive_green_runs_after_evaluation,
        gate_outcomes=evaluation.gate_outcomes,
        reason_codes=evaluation.reason_codes,
    )


def _promotion_evaluation_from_shadow_diagnostics(
    *,
    diagnostics: ShadowGateDiagnostics,
) -> PromotionRunEvaluation | None:
    if diagnostics.gate_mode != "report_only":
        return None

    if diagnostics.document_aware_report is None:
        return PromotionRunEvaluation(
            run_id=diagnostics.run_id,
            gate_mode=diagnostics.gate_mode,
            diagnostics_present=False,
            diagnostics_complete=False,
            all_gates_green=False,
            green_for_promotion=False,
            consecutive_green_runs_after_evaluation=0,
            gate_outcomes=(),
            reason_codes=("promotion_reset_missing_document_aware_diagnostics",),
        )

    gate_outcomes = tuple(
        PromotionGateOutcome(
            gate_id=gate.gate_id,
            status=gate.status,
            passed=gate.passed,
            reason_codes=gate.reason_codes,
            score=gate.score,
            threshold=gate.threshold,
        )
        for gate in diagnostics.document_aware_report.gates
    )
    green_for_promotion = (
        diagnostics.document_aware_report.diagnostics_complete and diagnostics.document_aware_report.all_gates_green
    )
    reason_codes = (
        ("promotion_green_run",)
        if green_for_promotion
        else (
            ("promotion_reset_incomplete_document_aware_diagnostics",)
            if not diagnostics.document_aware_report.diagnostics_complete
            else ("promotion_reset_failed_document_aware_gates",)
        )
    )
    return PromotionRunEvaluation(
        run_id=diagnostics.run_id,
        gate_mode=diagnostics.gate_mode,
        diagnostics_present=True,
        diagnostics_complete=diagnostics.document_aware_report.diagnostics_complete,
        all_gates_green=diagnostics.document_aware_report.all_gates_green,
        green_for_promotion=green_for_promotion,
        consecutive_green_runs_after_evaluation=0,
        gate_outcomes=gate_outcomes,
        reason_codes=reason_codes,
    )


def _promotion_evaluation_from_quality_gate_payload(
    *,
    run_id: str,
    quality_gate_payload: dict[str, object],
    environment: str,
    cohort: str,
) -> PromotionRunEvaluation | None:
    shadow_diagnostics = quality_gate_payload.get("shadow_diagnostics")
    if not isinstance(shadow_diagnostics, dict):
        return None

    payload_environment = quality_gate_payload.get("environment")
    if not isinstance(payload_environment, str):
        payload_environment = shadow_diagnostics.get("environment") if isinstance(shadow_diagnostics.get("environment"), str) else None
    payload_cohort = quality_gate_payload.get("cohort")
    if not isinstance(payload_cohort, str):
        payload_cohort = shadow_diagnostics.get("cohort") if isinstance(shadow_diagnostics.get("cohort"), str) else None
    if payload_environment != environment or payload_cohort != cohort:
        return None

    gate_mode = _parse_mode_field(payload=quality_gate_payload)
    if gate_mode is None:
        gate_mode = _parse_mode_field(payload=shadow_diagnostics)
    if gate_mode == "enforced":
        return None

    document_aware_report = shadow_diagnostics.get("document_aware_report")
    if isinstance(document_aware_report, dict):
        diagnostics_complete = bool(document_aware_report.get("diagnostics_complete", False))
        all_gates_green = bool(document_aware_report.get("all_gates_green", False))
        green_for_promotion = diagnostics_complete and all_gates_green
        reason_codes = (
            ("promotion_green_run",)
            if green_for_promotion
            else (
                ("promotion_reset_incomplete_document_aware_diagnostics",)
                if not diagnostics_complete
                else ("promotion_reset_failed_document_aware_gates",)
            )
        )
        return PromotionRunEvaluation(
            run_id=run_id,
            gate_mode=gate_mode,
            diagnostics_present=True,
            diagnostics_complete=diagnostics_complete,
            all_gates_green=all_gates_green,
            green_for_promotion=green_for_promotion,
            consecutive_green_runs_after_evaluation=0,
            gate_outcomes=_document_aware_gate_outcomes_from_payload(document_aware_report=document_aware_report),
            reason_codes=reason_codes,
        )

    if gate_mode == "report_only":
        return PromotionRunEvaluation(
            run_id=run_id,
            gate_mode=gate_mode,
            diagnostics_present=False,
            diagnostics_complete=False,
            all_gates_green=False,
            green_for_promotion=False,
            consecutive_green_runs_after_evaluation=0,
            gate_outcomes=(),
            reason_codes=("promotion_reset_missing_document_aware_diagnostics",),
        )

    diagnostics_complete = bool(shadow_diagnostics.get("diagnostics_complete", False))
    all_gates_green = bool(shadow_diagnostics.get("all_gates_green", False))
    green_for_promotion = diagnostics_complete and all_gates_green
    reason_codes = (
        ("promotion_green_run",)
        if green_for_promotion
        else (
            ("promotion_reset_incomplete_shadow_diagnostics",)
            if not diagnostics_complete
            else ("promotion_reset_failed_shadow_gates",)
        )
    )
    return PromotionRunEvaluation(
        run_id=run_id,
        gate_mode=gate_mode,
        diagnostics_present=True,
        diagnostics_complete=diagnostics_complete,
        all_gates_green=all_gates_green,
        green_for_promotion=green_for_promotion,
        consecutive_green_runs_after_evaluation=0,
        gate_outcomes=_shadow_gate_outcomes_from_payload(shadow_diagnostics=shadow_diagnostics),
        reason_codes=reason_codes,
    )


def compute_promotion_status(
    *,
    connection: sqlite3.Connection,
    environment: str,
    cohort: str,
    required_consecutive_green_runs: int = 2,
    current_run_diagnostics: ShadowGateDiagnostics | None = None,
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

    evaluated_runs_descending: list[PromotionRunEvaluation] = []
    consecutive_green_runs = 0
    seen_run_ids: set[str] = set()

    if current_run_diagnostics is not None:
        seen_run_ids.add(current_run_diagnostics.run_id)
        evaluation = _promotion_evaluation_from_shadow_diagnostics(diagnostics=current_run_diagnostics)
        if evaluation is not None and current_run_diagnostics.environment == environment and current_run_diagnostics.cohort == cohort:
            consecutive_green_runs = 1 if evaluation.green_for_promotion else 0
            evaluated_runs_descending.append(
                _with_streak(
                    evaluation=evaluation,
                    consecutive_green_runs_after_evaluation=consecutive_green_runs,
                )
            )
            if not evaluation.green_for_promotion or consecutive_green_runs >= required_consecutive_green_runs:
                rows = ()

    for row in rows:
        run_id = str(row[0])
        if run_id in seen_run_ids:
            continue
        seen_run_ids.add(run_id)
        quality_gate_payload = _read_quality_gate_rollout_from_metadata(
            metadata_json=(str(row[1]) if row[1] is not None else None)
        )
        if quality_gate_payload is None:
            continue

        evaluation = _promotion_evaluation_from_quality_gate_payload(
            run_id=run_id,
            quality_gate_payload=quality_gate_payload,
            environment=environment,
            cohort=cohort,
        )
        if evaluation is None:
            continue

        if evaluation.green_for_promotion:
            consecutive_green_runs += 1
            evaluated_runs_descending.append(
                _with_streak(
                    evaluation=evaluation,
                    consecutive_green_runs_after_evaluation=consecutive_green_runs,
                )
            )
            if consecutive_green_runs >= required_consecutive_green_runs:
                break
            continue

        consecutive_green_runs = 0
        evaluated_runs_descending.append(
            _with_streak(
                evaluation=evaluation,
                consecutive_green_runs_after_evaluation=consecutive_green_runs,
            )
        )
        break

    eligible = consecutive_green_runs >= required_consecutive_green_runs
    evaluated_runs = tuple(reversed(evaluated_runs_descending))
    evaluated_run_ids = tuple(run.run_id for run in evaluated_runs)
    eligible_window_run_ids = (
        tuple(run.run_id for run in evaluated_runs[-required_consecutive_green_runs:])
        if eligible
        else ()
    )
    reason_codes: list[str] = []
    if eligible:
        reason_codes.append("promotion_prerequisites_satisfied")
    else:
        if not evaluated_runs:
            reason_codes.append("no_report_only_runs_available")
        else:
            reason_codes.extend(evaluated_runs[-1].reason_codes)
        reason_codes.append("insufficient_consecutive_green_runs")

    return PromotionStatus(
        eligible=eligible,
        consecutive_green_runs=consecutive_green_runs,
        required_consecutive_green_runs=required_consecutive_green_runs,
        evaluated_run_ids=evaluated_run_ids,
        reason_codes=_dedupe_reason_codes(reason_codes=reason_codes),
        evaluated_runs=evaluated_runs,
        eligible_window_run_ids=eligible_window_run_ids,
    )


def build_promotion_artifact(
    *,
    config: QualityGateRolloutConfig,
    evaluated_at_run_id: str,
    promotion_status: PromotionStatus,
) -> PromotionArtifact:
    return PromotionArtifact(
        schema_version=PROMOTION_ARTIFACT_SCHEMA_VERSION,
        generated_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat(),
        environment=config.environment,
        cohort=config.cohort,
        promotion_scope_key=f"{config.environment}:{config.cohort}",
        evaluated_at_run_id=evaluated_at_run_id,
        eligible=promotion_status.eligible,
        required_consecutive_green_runs=promotion_status.required_consecutive_green_runs,
        consecutive_green_runs=promotion_status.consecutive_green_runs,
        reason_codes=promotion_status.reason_codes,
        evaluated_run_ids=promotion_status.evaluated_run_ids,
        eligible_window_run_ids=promotion_status.eligible_window_run_ids,
        evaluated_runs=promotion_status.evaluated_runs,
    )


def append_promotion_artifact(
    *,
    artifact_path: str | None,
    config: QualityGateRolloutConfig,
    evaluated_at_run_id: str,
    promotion_status: PromotionStatus,
) -> None:
    if artifact_path is None:
        return
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_promotion_artifact(
        config=config,
        evaluated_at_run_id=evaluated_at_run_id,
        promotion_status=promotion_status,
    ).to_payload()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{json.dumps(payload, sort_keys=True)}\n")


def build_document_aware_rollback_plan() -> RollbackControlPlan:
    return RollbackControlPlan(
        schema_version=ROLLBACK_CONTROL_PLAN_SCHEMA_VERSION,
        schema_rollback_required=False,
        profiles=(
            RollbackControlProfile(
                profile_id="report_only_reversion",
                goal="Return publish decisioning to observational mode before any feature disablement.",
                prerequisite=None,
                steps=(
                    RollbackControlStep(
                        step=1,
                        control="gate_mode",
                        action="set_report_only",
                        pre_check=(
                            "Confirm the affected environment/cohort currently resolves gate_mode=enforced and capture the latest "
                            "promotion artifact plus shadow diagnostics run IDs for the incident record."
                        ),
                        post_check=(
                            "Publish metadata reports gate_mode=report_only and enforcement_outcome.decision=observe for the "
                            "next verification run."
                        ),
                        resulting_mode="report_only",
                    ),
                ),
            ),
            RollbackControlProfile(
                profile_id="full_disable_after_report_only",
                goal="Disable document-aware feature controls after enforcement has already been reverted to report-only mode.",
                prerequisite=(
                    "Complete report_only_reversion first, or record an equivalent manual override proving publish has returned "
                    "to non-enforced behavior."
                ),
                steps=(
                    RollbackControlStep(
                        step=1,
                        control="specificity_retention_enabled",
                        action="disable",
                        pre_check=(
                            "Confirm gate_mode remains report_only and anchor carry-through is still enabled for the affected "
                            "environment/cohort."
                        ),
                        post_check=(
                            "Anchor carry-through is disabled while publish remains report_only and diagnostics continue to emit "
                            "for the verification run."
                        ),
                        resulting_mode="report_only",
                    ),
                    RollbackControlStep(
                        step=2,
                        control="evidence_projection_enabled",
                        action="disable",
                        pre_check="Confirm specificity_retention_enabled is already disabled for the affected environment/cohort.",
                        post_check=(
                            "Evidence projection precision is disabled after specificity retention, and verification output no "
                            "longer contains the additive precision override behavior."
                        ),
                        resulting_mode="report_only",
                    ),
                    RollbackControlStep(
                        step=3,
                        control="topic_hardening_enabled",
                        action="disable",
                        pre_check=(
                            "Confirm specificity_retention_enabled and evidence_projection_enabled are already disabled for the "
                            "affected environment/cohort."
                        ),
                        post_check=(
                            "Topic hardening is disabled and the publish path is operating on the non-enforced baseline without "
                            "requiring schema rollback."
                        ),
                        resulting_mode="report_only",
                    ),
                ),
            ),
        ),
        escalation_policy=RollbackEscalationPolicy(
            primary_owner="platform/backend on-call",
            secondary_owner="release owner",
            escalation_owner="incident commander",
            paging_route=(
                "platform/backend on-call",
                "release owner",
                "incident commander",
            ),
            escalation_trigger=(
                "Any rollback post-check fails, publish remains enforced after the report-only reversion step, or baseline "
                "behavior is not restored within 15 minutes."
            ),
        ),
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

    gate_reason_details = _collect_gate_reason_details(config=config, diagnostics=diagnostics)

    if not gate_reason_details:
        return EnforcementOutcome(decision="enforce_pass", reason_codes=("all_gates_green",))

    if any(detail.policy_action == "block" for detail in gate_reason_details):
        return EnforcementOutcome(
            decision="enforce_block",
            reason_codes=_build_enforcement_reason_codes(
                default_reason_code="gate_failure_blocked_publish",
                gate_reason_details=gate_reason_details,
            ),
            gate_reason_details=gate_reason_details,
        )

    return EnforcementOutcome(
        decision="enforce_downgrade",
        reason_codes=_build_enforcement_reason_codes(
            default_reason_code="gate_failure_downgraded_publish",
            gate_reason_details=gate_reason_details,
        ),
        gate_reason_details=gate_reason_details,
    )


def _collect_gate_reason_details(
    *,
    config: QualityGateRolloutConfig,
    diagnostics: ShadowGateDiagnostics,
) -> tuple[GateReasonDetail, ...]:
    details: list[GateReasonDetail] = []

    for gate in diagnostics.gates:
        if gate.passed:
            continue
        details.append(
            GateReasonDetail(
                gate_family="shadow_gate",
                gate_id=gate.gate_id,
                policy_action=config.enforcement_action,
                reason_codes=gate.reason_codes,
            )
        )

    if diagnostics.document_aware_report is not None:
        for gate in diagnostics.document_aware_report.gates:
            if gate.passed:
                continue
            details.append(
                GateReasonDetail(
                    gate_family="document_aware_gate",
                    gate_id=gate.gate_id,
                    policy_action=_document_aware_policy_action(gate_id=gate.gate_id),
                    reason_codes=gate.reason_codes,
                    score=gate.score,
                    threshold=gate.threshold,
                    details=gate.details,
                )
            )

    return tuple(details)


def _document_aware_policy_action(*, gate_id: DocumentAwareGateDimension) -> EnforcementAction:
    if gate_id == "authority_alignment":
        return "block"
    return "downgrade"


def _build_enforcement_reason_codes(
    *,
    default_reason_code: str,
    gate_reason_details: tuple[GateReasonDetail, ...],
) -> tuple[str, ...]:
    reason_codes: list[str] = [default_reason_code]

    for detail in gate_reason_details:
        if detail.gate_family != "document_aware_gate":
            continue
        policy_reason_code = (
            f"document_aware_{detail.gate_id}_blocked_publish"
            if detail.policy_action == "block"
            else f"document_aware_{detail.gate_id}_downgraded_publish"
        )
        if policy_reason_code not in reason_codes:
            reason_codes.append(policy_reason_code)
        for reason_code in detail.reason_codes:
            if reason_code not in reason_codes:
                reason_codes.append(reason_code)

    return tuple(reason_codes)


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
            "gate_reason_details": [detail.to_payload() for detail in enforcement_outcome.gate_reason_details],
        },
    }


def build_rollback_sequence() -> tuple[dict[str, object], ...]:
    return (
        {
            "step": 1,
            "control": "specificity_retention_enabled",
            "action": "disable",
            "pre_check": "Confirm the affected environment/cohort is identified and capture the current rollout config snapshot before disabling specificity retention.",
            "post_check": "anchor carry-through may be disabled while publish remains report-only or enforced per mode",
            "resulting_mode": "enforced",
        },
        {
            "step": 2,
            "control": "evidence_projection_enabled",
            "action": "disable",
            "pre_check": "Confirm specificity_retention_enabled is already disabled for the affected environment/cohort.",
            "post_check": "evidence projection precision is disabled after specificity retention",
            "resulting_mode": "enforced",
        },
        {
            "step": 3,
            "control": "topic_hardening_enabled",
            "action": "disable",
            "pre_check": "Confirm specificity_retention_enabled and evidence_projection_enabled are already disabled for the affected environment/cohort.",
            "post_check": "topic hardening is disabled after specificity and evidence controls",
            "resulting_mode": "enforced",
        },
        {
            "step": 4,
            "control": "gate_mode",
            "action": "set_report_only",
            "pre_check": "Confirm the prior flag disablement steps completed or document the reason for stopping at report-only mode only.",
            "post_check": "enforcement is disabled and gates run in report-only mode",
            "resulting_mode": "report_only",
        },
    )
