from __future__ import annotations

import json
import os

import pytest

from councilsense.app.quality_gate_rollout import resolve_rollout_config
from councilsense.app.st030_document_aware_gates import (
    DOCUMENT_AWARE_GATE_CONTRACT_VERSION,
    REASON_CODE_AUTHORITY_INPUTS_MISSING,
    REASON_CODE_CITATION_INPUTS_MISSING,
    REASON_CODE_CITATION_PRECISION_BELOW_THRESHOLD,
    REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD,
    REASON_CODE_COVERAGE_INPUTS_MISSING,
    REASON_CODE_GATE_PASS,
    REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,
    REASON_CODE_SUPPLEMENTAL_SOURCES_MISSING,
    REASON_CODE_UNRESOLVED_SOURCE_CONFLICT,
    REASON_CODE_WEAK_EVIDENCE_PRECISION,
    DocumentAwareGateInput,
    DocumentAwareGateThresholds,
    evaluate_document_aware_gates,
    parse_document_aware_thresholds,
    reason_code_catalog,
)


def test_st030_threshold_parser_uses_contract_defaults_and_validates_shape() -> None:
    thresholds = parse_document_aware_thresholds(payload=None)

    assert thresholds.to_payload()["schema_version"] == DOCUMENT_AWARE_GATE_CONTRACT_VERSION
    assert thresholds.authoritative_source_type == "minutes"
    assert thresholds.authority_alignment.min_score == 1.0
    assert thresholds.document_coverage_balance.min_score == 0.5
    assert thresholds.document_coverage_balance.supporting_source_types == ("agenda", "packet")
    assert thresholds.citation_precision.min_score == 0.5


def test_st030_threshold_parser_rejects_invalid_ranges_and_duplicate_supporting_sources() -> None:
    with pytest.raises(ValueError, match="authority_alignment.min_score"):
        parse_document_aware_thresholds(
            payload={
                "authority_alignment": {"min_score": 1.1},
            }
        )

    with pytest.raises(ValueError, match="supporting_source_types must not contain duplicates"):
        parse_document_aware_thresholds(
            payload={
                "document_coverage_balance": {
                    "supporting_source_types": ["agenda", "agenda"],
                }
            }
        )


def test_st030_rollout_config_resolves_document_aware_thresholds_with_env_and_cohort_precedence() -> None:
    prior = os.environ.get("COUNCILSENSE_QG_CONFIG_JSON")
    os.environ["COUNCILSENSE_QG_CONFIG_JSON"] = json.dumps(
        {
            "defaults": {
                "document_aware_thresholds": {
                    "authority_alignment": {"min_score": 1.0},
                    "document_coverage_balance": {
                        "min_score": 0.4,
                        "partial_status_credit": 0.25,
                        "supporting_source_types": ["agenda", "packet"],
                    },
                    "citation_precision": {"min_score": 0.55},
                }
            },
            "environments": {
                "staging": {
                    "document_aware_thresholds": {
                        "citation_precision": {"min_score": 0.7},
                    }
                }
            },
            "cohorts": {
                "city-eagle-mountain-ut": {
                    "document_aware_thresholds": {
                        "authority_alignment": {"min_score": 0.95},
                    }
                }
            },
            "environment_cohorts": {
                "staging:city-eagle-mountain-ut": {
                    "document_aware_thresholds": {
                        "document_coverage_balance": {"min_score": 0.75},
                    }
                }
            },
        }
    )

    try:
        config = resolve_rollout_config(environment="staging", cohort="city-eagle-mountain-ut")
    finally:
        if prior is None:
            os.environ.pop("COUNCILSENSE_QG_CONFIG_JSON", None)
        else:
            os.environ["COUNCILSENSE_QG_CONFIG_JSON"] = prior

    assert config.document_aware_thresholds.authority_alignment.min_score == 0.95
    assert config.document_aware_thresholds.document_coverage_balance.min_score == 0.75
    assert config.document_aware_thresholds.document_coverage_balance.partial_status_credit == 0.25
    assert config.document_aware_thresholds.citation_precision.min_score == 0.7


def test_st030_document_aware_gate_evaluation_is_deterministic_for_identical_inputs() -> None:
    gate_input = DocumentAwareGateInput(
        authority_outcome="minutes_authoritative",
        authority_reason_codes=(),
        authority_conflict_count=1,
        source_statuses={"minutes": "present", "agenda": "present", "packet": "partial"},
        authoritative_locator_precision="precise",
        citation_precision_ratio=0.75,
        citation_pointer_count=4,
    )
    thresholds = DocumentAwareGateThresholds()

    first = evaluate_document_aware_gates(gate_input=gate_input, thresholds=thresholds)
    second = evaluate_document_aware_gates(gate_input=gate_input, thresholds=thresholds)

    assert first.to_payload() == second.to_payload()
    assert first.all_dimensions_passed is True
    assert [dimension.reason_codes for dimension in first.dimensions] == [
        (REASON_CODE_GATE_PASS,),
        (REASON_CODE_GATE_PASS,),
        (REASON_CODE_GATE_PASS,),
    ]


def test_st030_document_aware_gate_evaluation_emits_explicit_reason_codes_for_failures() -> None:
    thresholds = DocumentAwareGateThresholds()
    gate_input = DocumentAwareGateInput(
        authority_outcome="unresolved_conflict",
        authority_reason_codes=(REASON_CODE_MISSING_AUTHORITATIVE_MINUTES, REASON_CODE_UNRESOLVED_SOURCE_CONFLICT),
        authority_conflict_count=1,
        source_statuses={"minutes": "missing", "agenda": "partial", "packet": "missing"},
        authoritative_locator_precision="precise",
        citation_precision_ratio=0.25,
        citation_pointer_count=4,
    )

    evaluation = evaluate_document_aware_gates(gate_input=gate_input, thresholds=thresholds)
    results = {dimension.dimension: dimension for dimension in evaluation.dimensions}

    assert evaluation.all_dimensions_passed is False
    assert results["authority_alignment"].reason_codes == (REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,)
    assert results["document_coverage_balance"].reason_codes == (REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD,)
    assert results["citation_precision"].reason_codes == (REASON_CODE_CITATION_PRECISION_BELOW_THRESHOLD,)


def test_st030_document_aware_gate_evaluation_flags_minutes_only_and_weak_locator_cases() -> None:
    thresholds = DocumentAwareGateThresholds()

    minutes_only = evaluate_document_aware_gates(
        gate_input=DocumentAwareGateInput(
            authority_outcome="supplemental_coverage_missing",
            authority_reason_codes=(REASON_CODE_SUPPLEMENTAL_SOURCES_MISSING,),
            authority_conflict_count=0,
            source_statuses={"minutes": "present", "agenda": "missing", "packet": "missing"},
            authoritative_locator_precision="precise",
            citation_precision_ratio=0.8,
            citation_pointer_count=3,
        ),
        thresholds=thresholds,
    )
    weak_locator = evaluate_document_aware_gates(
        gate_input=DocumentAwareGateInput(
            authority_outcome="minutes_authoritative_weak_precision",
            authority_reason_codes=(REASON_CODE_WEAK_EVIDENCE_PRECISION,),
            authority_conflict_count=0,
            source_statuses={"minutes": "present", "agenda": "present", "packet": "missing"},
            authoritative_locator_precision="weak",
            citation_precision_ratio=0.8,
            citation_pointer_count=3,
        ),
        thresholds=thresholds,
    )

    minutes_only_results = {dimension.dimension: dimension for dimension in minutes_only.dimensions}
    weak_locator_results = {dimension.dimension: dimension for dimension in weak_locator.dimensions}

    assert minutes_only_results["document_coverage_balance"].reason_codes == (REASON_CODE_SUPPLEMENTAL_SOURCES_MISSING,)
    assert weak_locator_results["citation_precision"].reason_codes == (REASON_CODE_WEAK_EVIDENCE_PRECISION,)
    assert weak_locator_results["citation_precision"].score == 0.0


def test_st030_document_aware_gate_evaluation_treats_missing_inputs_as_explicit_failures() -> None:
    evaluation = evaluate_document_aware_gates(
        gate_input=DocumentAwareGateInput(
            authority_outcome=None,
            source_statuses={"agenda": "present"},
            authoritative_locator_precision=None,
            citation_precision_ratio=None,
            citation_pointer_count=None,
        )
    )
    results = {dimension.dimension: dimension for dimension in evaluation.dimensions}

    assert results["authority_alignment"].reason_codes == (REASON_CODE_AUTHORITY_INPUTS_MISSING,)
    assert results["document_coverage_balance"].reason_codes == (REASON_CODE_COVERAGE_INPUTS_MISSING,)
    assert results["citation_precision"].reason_codes == (REASON_CODE_CITATION_INPUTS_MISSING,)


def test_st030_reason_code_catalog_is_dimension_scoped_and_stable() -> None:
    catalog = reason_code_catalog()

    assert [entry.code for entry in catalog] == [
        REASON_CODE_AUTHORITY_INPUTS_MISSING,
        REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,
        REASON_CODE_UNRESOLVED_SOURCE_CONFLICT,
        REASON_CODE_COVERAGE_INPUTS_MISSING,
        REASON_CODE_SUPPLEMENTAL_SOURCES_MISSING,
        REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD,
        REASON_CODE_CITATION_INPUTS_MISSING,
        REASON_CODE_WEAK_EVIDENCE_PRECISION,
        REASON_CODE_CITATION_PRECISION_BELOW_THRESHOLD,
    ]
    assert {entry.dimension for entry in catalog} == {
        "authority_alignment",
        "document_coverage_balance",
        "citation_precision",
    }