from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, cast


DOCUMENT_AWARE_GATE_CONTRACT_VERSION = "st-030-document-aware-gates-v1"

DocumentAwareGateDimension = Literal[
    "authority_alignment",
    "document_coverage_balance",
    "citation_precision",
]
SourceCoverageStatus = Literal["present", "partial", "missing"]
LocatorPrecision = Literal["precise", "weak", "unknown"]

REASON_CODE_AUTHORITY_INPUTS_MISSING = "authority_alignment_inputs_missing"
REASON_CODE_MISSING_AUTHORITATIVE_MINUTES = "missing_authoritative_minutes"
REASON_CODE_UNRESOLVED_SOURCE_CONFLICT = "unresolved_source_conflict"
REASON_CODE_COVERAGE_INPUTS_MISSING = "document_coverage_balance_inputs_missing"
REASON_CODE_SUPPLEMENTAL_SOURCES_MISSING = "supplemental_sources_missing"
REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD = "document_coverage_balance_below_threshold"
REASON_CODE_CITATION_INPUTS_MISSING = "citation_precision_inputs_missing"
REASON_CODE_WEAK_EVIDENCE_PRECISION = "weak_evidence_precision"
REASON_CODE_CITATION_PRECISION_BELOW_THRESHOLD = "citation_precision_below_threshold"
REASON_CODE_GATE_PASS = "document_aware_gate_pass"


@dataclass(frozen=True)
class ReasonCodeDefinition:
    code: str
    dimension: DocumentAwareGateDimension
    description: str
    example_outcomes: tuple[str, ...]


@dataclass(frozen=True)
class AuthorityAlignmentThreshold:
    min_score: float = 1.0

    def validate(self) -> None:
        _validate_probability(name="authority_alignment.min_score", value=self.min_score)


@dataclass(frozen=True)
class CoverageBalanceThreshold:
    min_score: float = 0.5
    partial_status_credit: float = 0.5
    supporting_source_types: tuple[str, ...] = ("agenda", "packet")

    def validate(self) -> None:
        _validate_probability(name="document_coverage_balance.min_score", value=self.min_score)
        _validate_probability(
            name="document_coverage_balance.partial_status_credit",
            value=self.partial_status_credit,
        )
        normalized = tuple(_normalize_source_type(source_type) for source_type in self.supporting_source_types)
        if not normalized:
            raise ValueError("document_coverage_balance.supporting_source_types must contain at least one source type")
        if len(set(normalized)) != len(normalized):
            raise ValueError("document_coverage_balance.supporting_source_types must not contain duplicates")


@dataclass(frozen=True)
class CitationPrecisionThreshold:
    min_score: float = 0.5

    def validate(self) -> None:
        _validate_probability(name="citation_precision.min_score", value=self.min_score)


@dataclass(frozen=True)
class DocumentAwareGateThresholds:
    authoritative_source_type: str = "minutes"
    authority_alignment: AuthorityAlignmentThreshold = field(default_factory=AuthorityAlignmentThreshold)
    document_coverage_balance: CoverageBalanceThreshold = field(default_factory=CoverageBalanceThreshold)
    citation_precision: CitationPrecisionThreshold = field(default_factory=CitationPrecisionThreshold)

    def validate(self) -> None:
        _normalize_source_type(self.authoritative_source_type)
        self.authority_alignment.validate()
        self.document_coverage_balance.validate()
        self.citation_precision.validate()
        if self.authoritative_source_type in self.document_coverage_balance.supporting_source_types:
            raise ValueError("authoritative_source_type must not also appear in supporting_source_types")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": DOCUMENT_AWARE_GATE_CONTRACT_VERSION,
            "authoritative_source_type": self.authoritative_source_type,
            "authority_alignment": {"min_score": self.authority_alignment.min_score},
            "document_coverage_balance": {
                "min_score": self.document_coverage_balance.min_score,
                "partial_status_credit": self.document_coverage_balance.partial_status_credit,
                "supporting_source_types": list(self.document_coverage_balance.supporting_source_types),
            },
            "citation_precision": {"min_score": self.citation_precision.min_score},
        }


@dataclass(frozen=True)
class DocumentAwareGateInput:
    authority_outcome: str | None
    authority_reason_codes: tuple[str, ...] = ()
    authority_conflict_count: int | None = None
    source_statuses: dict[str, SourceCoverageStatus] = field(default_factory=dict)
    authoritative_locator_precision: LocatorPrecision | None = None
    citation_precision_ratio: float | None = None
    citation_pointer_count: int | None = None


@dataclass(frozen=True)
class DocumentAwareGateResult:
    dimension: DocumentAwareGateDimension
    score: float
    min_score: float
    passed: bool
    reason_codes: tuple[str, ...]
    details: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "min_score": self.min_score,
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class DocumentAwareGateEvaluation:
    schema_version: str
    all_dimensions_passed: bool
    dimensions: tuple[DocumentAwareGateResult, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "all_dimensions_passed": self.all_dimensions_passed,
            "dimensions": [dimension.to_payload() for dimension in self.dimensions],
        }


def default_document_aware_thresholds_payload() -> dict[str, object]:
    return DocumentAwareGateThresholds().to_payload()


def parse_document_aware_thresholds(*, payload: Mapping[str, object] | None) -> DocumentAwareGateThresholds:
    if payload is None:
        thresholds = DocumentAwareGateThresholds()
        thresholds.validate()
        return thresholds
    if not isinstance(payload, Mapping):
        raise ValueError("document_aware_thresholds must be an object when provided")

    authoritative_source_type = str(payload.get("authoritative_source_type") or "minutes").strip().lower() or "minutes"

    authority_payload = _read_nested_mapping(payload=payload, key="authority_alignment")
    coverage_payload = _read_nested_mapping(payload=payload, key="document_coverage_balance")
    citation_payload = _read_nested_mapping(payload=payload, key="citation_precision")

    thresholds = DocumentAwareGateThresholds(
        authoritative_source_type=authoritative_source_type,
        authority_alignment=AuthorityAlignmentThreshold(
            min_score=_read_probability(authority_payload, key="min_score", default=1.0),
        ),
        document_coverage_balance=CoverageBalanceThreshold(
            min_score=_read_probability(coverage_payload, key="min_score", default=0.5),
            partial_status_credit=_read_probability(coverage_payload, key="partial_status_credit", default=0.5),
            supporting_source_types=_read_source_type_list(
                coverage_payload,
                key="supporting_source_types",
                default=("agenda", "packet"),
            ),
        ),
        citation_precision=CitationPrecisionThreshold(
            min_score=_read_probability(citation_payload, key="min_score", default=0.5),
        ),
    )
    thresholds.validate()
    return thresholds


def evaluate_document_aware_gates(
    *,
    gate_input: DocumentAwareGateInput,
    thresholds: DocumentAwareGateThresholds | None = None,
) -> DocumentAwareGateEvaluation:
    active_thresholds = thresholds or DocumentAwareGateThresholds()
    active_thresholds.validate()

    authority = _evaluate_authority_alignment(gate_input=gate_input, thresholds=active_thresholds)
    coverage = _evaluate_document_coverage_balance(gate_input=gate_input, thresholds=active_thresholds)
    citation = _evaluate_citation_precision(gate_input=gate_input, thresholds=active_thresholds)
    dimensions = (authority, coverage, citation)
    return DocumentAwareGateEvaluation(
        schema_version=DOCUMENT_AWARE_GATE_CONTRACT_VERSION,
        all_dimensions_passed=all(result.passed for result in dimensions),
        dimensions=dimensions,
    )


def reason_code_catalog() -> tuple[ReasonCodeDefinition, ...]:
    return (
        ReasonCodeDefinition(
            code=REASON_CODE_AUTHORITY_INPUTS_MISSING,
            dimension="authority_alignment",
            description="Required authority outcome or source-status inputs were missing, so authority alignment could not be evaluated.",
            example_outcomes=("authority_outcome missing", "source_statuses missing minutes"),
        ),
        ReasonCodeDefinition(
            code=REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,
            dimension="authority_alignment",
            description="The authoritative minutes source was unavailable, so authority alignment failed.",
            example_outcomes=("agenda preview only", "supplemental-only rerun"),
        ),
        ReasonCodeDefinition(
            code=REASON_CODE_UNRESOLVED_SOURCE_CONFLICT,
            dimension="authority_alignment",
            description="Supplemental sources disagree on an outcome and no authoritative minutes source resolves the conflict.",
            example_outcomes=("agenda says adopt, packet says continue",),
        ),
        ReasonCodeDefinition(
            code=REASON_CODE_COVERAGE_INPUTS_MISSING,
            dimension="document_coverage_balance",
            description="Expected source-coverage dimensions were missing, so coverage balance could not be scored.",
            example_outcomes=("packet status omitted", "agenda status omitted"),
        ),
        ReasonCodeDefinition(
            code=REASON_CODE_SUPPLEMENTAL_SOURCES_MISSING,
            dimension="document_coverage_balance",
            description="No supporting agenda or packet coverage was available alongside the authoritative source.",
            example_outcomes=("minutes only",),
        ),
        ReasonCodeDefinition(
            code=REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD,
            dimension="document_coverage_balance",
            description="Supporting document coverage was present but below the configured environment threshold.",
            example_outcomes=("agenda present, packet missing", "agenda partial, packet missing"),
        ),
        ReasonCodeDefinition(
            code=REASON_CODE_CITATION_INPUTS_MISSING,
            dimension="citation_precision",
            description="Citation pointer counts or precision ratio inputs were missing, so citation precision could not be evaluated.",
            example_outcomes=("no pointer metrics available",),
        ),
        ReasonCodeDefinition(
            code=REASON_CODE_WEAK_EVIDENCE_PRECISION,
            dimension="citation_precision",
            description="Citation precision failed because the authoritative locator precision was weak.",
            example_outcomes=("minutes composed from weak locators",),
        ),
        ReasonCodeDefinition(
            code=REASON_CODE_CITATION_PRECISION_BELOW_THRESHOLD,
            dimension="citation_precision",
            description="The ratio of precise citations to total citations was below the configured threshold.",
            example_outcomes=("majority file-level citations",),
        ),
    )


def _evaluate_authority_alignment(
    *,
    gate_input: DocumentAwareGateInput,
    thresholds: DocumentAwareGateThresholds,
) -> DocumentAwareGateResult:
    authoritative_status = gate_input.source_statuses.get(thresholds.authoritative_source_type)
    if gate_input.authority_outcome is None or authoritative_status is None:
        return _failed_result(
            dimension="authority_alignment",
            min_score=thresholds.authority_alignment.min_score,
            reason_codes=(REASON_CODE_AUTHORITY_INPUTS_MISSING,),
            details={
                "authority_outcome": gate_input.authority_outcome,
                "authoritative_source_type": thresholds.authoritative_source_type,
                "source_statuses": dict(gate_input.source_statuses),
            },
        )

    normalized_reasons = _ordered_unique_codes(*gate_input.authority_reason_codes)
    if authoritative_status == "missing" or REASON_CODE_MISSING_AUTHORITATIVE_MINUTES in normalized_reasons:
        return _failed_result(
            dimension="authority_alignment",
            min_score=thresholds.authority_alignment.min_score,
            reason_codes=(REASON_CODE_MISSING_AUTHORITATIVE_MINUTES,),
            details={
                "authority_outcome": gate_input.authority_outcome,
                "authoritative_source_status": authoritative_status,
                "authority_conflict_count": gate_input.authority_conflict_count,
            },
        )

    if gate_input.authority_outcome == "unresolved_conflict" or REASON_CODE_UNRESOLVED_SOURCE_CONFLICT in normalized_reasons:
        return _failed_result(
            dimension="authority_alignment",
            min_score=thresholds.authority_alignment.min_score,
            reason_codes=(REASON_CODE_UNRESOLVED_SOURCE_CONFLICT,),
            details={
                "authority_outcome": gate_input.authority_outcome,
                "authoritative_source_status": authoritative_status,
                "authority_conflict_count": gate_input.authority_conflict_count,
            },
        )

    score = 1.0
    return _finalize_result(
        dimension="authority_alignment",
        score=score,
        min_score=thresholds.authority_alignment.min_score,
        reason_codes=(REASON_CODE_GATE_PASS,),
        details={
            "authority_outcome": gate_input.authority_outcome,
            "authoritative_source_status": authoritative_status,
            "authority_conflict_count": gate_input.authority_conflict_count,
            "authority_reason_codes": list(normalized_reasons),
        },
    )


def _evaluate_document_coverage_balance(
    *,
    gate_input: DocumentAwareGateInput,
    thresholds: DocumentAwareGateThresholds,
) -> DocumentAwareGateResult:
    missing_sources = [
        source_type
        for source_type in thresholds.document_coverage_balance.supporting_source_types
        if source_type not in gate_input.source_statuses
    ]
    if missing_sources:
        return _failed_result(
            dimension="document_coverage_balance",
            min_score=thresholds.document_coverage_balance.min_score,
            reason_codes=(REASON_CODE_COVERAGE_INPUTS_MISSING,),
            details={
                "missing_source_types": missing_sources,
                "source_statuses": dict(gate_input.source_statuses),
            },
        )

    weights = {
        "present": 1.0,
        "partial": thresholds.document_coverage_balance.partial_status_credit,
        "missing": 0.0,
    }
    observed_statuses = {
        source_type: gate_input.source_statuses[source_type]
        for source_type in thresholds.document_coverage_balance.supporting_source_types
    }
    score = sum(weights[status] for status in observed_statuses.values()) / float(len(observed_statuses))

    reason_codes: list[str] = []
    if score < thresholds.document_coverage_balance.min_score:
        if all(status == "missing" for status in observed_statuses.values()):
            reason_codes.append(REASON_CODE_SUPPLEMENTAL_SOURCES_MISSING)
        else:
            reason_codes.append(REASON_CODE_COVERAGE_BALANCE_BELOW_THRESHOLD)

    return _finalize_result(
        dimension="document_coverage_balance",
        score=score,
        min_score=thresholds.document_coverage_balance.min_score,
        reason_codes=tuple(reason_codes) if reason_codes else (REASON_CODE_GATE_PASS,),
        details={
            "source_statuses": observed_statuses,
            "partial_status_credit": thresholds.document_coverage_balance.partial_status_credit,
            "supporting_source_types": list(thresholds.document_coverage_balance.supporting_source_types),
        },
    )


def _evaluate_citation_precision(
    *,
    gate_input: DocumentAwareGateInput,
    thresholds: DocumentAwareGateThresholds,
) -> DocumentAwareGateResult:
    if gate_input.citation_pointer_count is None or gate_input.citation_precision_ratio is None:
        return _failed_result(
            dimension="citation_precision",
            min_score=thresholds.citation_precision.min_score,
            reason_codes=(REASON_CODE_CITATION_INPUTS_MISSING,),
            details={
                "citation_pointer_count": gate_input.citation_pointer_count,
                "citation_precision_ratio": gate_input.citation_precision_ratio,
            },
        )
    if gate_input.citation_pointer_count <= 0:
        return _failed_result(
            dimension="citation_precision",
            min_score=thresholds.citation_precision.min_score,
            reason_codes=(REASON_CODE_CITATION_INPUTS_MISSING,),
            details={
                "citation_pointer_count": gate_input.citation_pointer_count,
                "citation_precision_ratio": gate_input.citation_precision_ratio,
            },
        )

    score = gate_input.citation_precision_ratio
    reason_codes: list[str] = []
    if gate_input.authoritative_locator_precision == "weak":
        score = 0.0
        reason_codes.append(REASON_CODE_WEAK_EVIDENCE_PRECISION)
    elif score < thresholds.citation_precision.min_score:
        reason_codes.append(REASON_CODE_CITATION_PRECISION_BELOW_THRESHOLD)

    return _finalize_result(
        dimension="citation_precision",
        score=score,
        min_score=thresholds.citation_precision.min_score,
        reason_codes=tuple(reason_codes) if reason_codes else (REASON_CODE_GATE_PASS,),
        details={
            "citation_pointer_count": gate_input.citation_pointer_count,
            "citation_precision_ratio": gate_input.citation_precision_ratio,
            "authoritative_locator_precision": gate_input.authoritative_locator_precision,
        },
    )


def _failed_result(
    *,
    dimension: DocumentAwareGateDimension,
    min_score: float,
    reason_codes: tuple[str, ...],
    details: dict[str, object],
) -> DocumentAwareGateResult:
    return DocumentAwareGateResult(
        dimension=dimension,
        score=0.0,
        min_score=min_score,
        passed=False,
        reason_codes=_ordered_unique_codes(*reason_codes),
        details=details,
    )


def _finalize_result(
    *,
    dimension: DocumentAwareGateDimension,
    score: float,
    min_score: float,
    reason_codes: tuple[str, ...],
    details: dict[str, object],
) -> DocumentAwareGateResult:
    clamped_score = max(0.0, min(1.0, score))
    passed = clamped_score >= min_score and reason_codes == (REASON_CODE_GATE_PASS,)
    if clamped_score >= min_score and REASON_CODE_GATE_PASS not in reason_codes and dimension != "citation_precision":
        passed = False
    if REASON_CODE_GATE_PASS in reason_codes and clamped_score < min_score:
        passed = False
    return DocumentAwareGateResult(
        dimension=dimension,
        score=round(clamped_score, 4),
        min_score=min_score,
        passed=passed,
        reason_codes=_ordered_unique_codes(*reason_codes),
        details=details,
    )


def _read_nested_mapping(*, payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    raw = payload.get(key)
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"document_aware_thresholds.{key} must be an object when provided")
    return cast(Mapping[str, object], raw)


def _read_probability(payload: Mapping[str, object], *, key: str, default: float) -> float:
    raw = payload.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"document_aware_thresholds.{key} must be a number between 0.0 and 1.0")
    return float(raw)


def _read_source_type_list(
    payload: Mapping[str, object],
    *,
    key: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    raw = payload.get(key)
    if raw is None:
        return default
    if not isinstance(raw, list):
        raise ValueError(f"document_aware_thresholds.{key} must be an array when provided")
    return tuple(_normalize_source_type(str(item)) for item in raw)


def _validate_probability(*, name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0")


def _normalize_source_type(source_type: str) -> str:
    normalized = source_type.strip().lower()
    if not normalized:
        raise ValueError("source types must be non-empty strings")
    return normalized


def _ordered_unique_codes(*codes: str) -> tuple[str, ...]:
    ordered: list[str] = []
    for code in codes:
        normalized = code.strip()
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return tuple(ordered)