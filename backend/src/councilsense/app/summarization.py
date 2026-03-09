from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from councilsense.app.notification_fanout import (
    NotificationEnqueueResult,
    NotificationSubscriptionTarget,
    enqueue_publish_notifications_to_outbox,
)
from councilsense.db import (
    ConfidenceCalibrationPolicyRepository,
    ConfidenceLabel,
    MeetingSummaryRepository,
    PublicationStatus,
    SummaryPublicationRecord,
)
from councilsense.db.meeting_summaries import DEFAULT_SUMMARY_CALIBRATION_POLICY_VERSION


SUMMARIZATION_CONTRACT_VERSION = "st-005-v1"
EMPTY_SUMMARY_TEXT = "No summary available."
_LINKAGE_DOCUMENT_KINDS = frozenset({"minutes", "agenda", "packet"})
_LINKAGE_PRECISIONS = frozenset({"offset", "span", "section", "file"})
_LINKAGE_CONFIDENCES = frozenset({"high", "medium", "low"})
_STRUCTURED_RELEVANCE_CONFIDENCES = frozenset({"high", "medium", "low"})


def _normalize_summary(summary: str) -> str:
    normalized = summary.strip()
    if not normalized:
        return EMPTY_SUMMARY_TEXT
    return normalized


def _normalize_section_items(items: Sequence[str] | None) -> tuple[str, ...]:
    if not items:
        return ()

    normalized_items: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized:
            normalized_items.append(normalized)
    return tuple(normalized_items)


def _encode_json_array(items: Sequence[str]) -> str:
    return json.dumps(list(items), ensure_ascii=False, separators=(",", ":"))


def _normalize_location_ref(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _normalize_excerpt(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_structured_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _normalize_structured_confidence(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized


class ClaimEvidenceValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ClaimEvidencePointer:
    artifact_id: str
    section_ref: str | None
    char_start: int | None
    char_end: int | None
    excerpt: str
    document_id: str | None = None
    span_id: str | None = None
    document_kind: str | None = None
    section_path: str | None = None
    precision: str | None = None
    confidence: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> ClaimEvidencePointer:
        artifact_id_raw = payload.get("artifact_id")
        artifact_id = artifact_id_raw.strip() if isinstance(artifact_id_raw, str) else ""
        section_ref = _normalize_location_ref(payload.get("section_ref"))
        char_start_raw = payload.get("char_start")
        char_end_raw = payload.get("char_end")
        char_start = char_start_raw if isinstance(char_start_raw, int) else None
        char_end = char_end_raw if isinstance(char_end_raw, int) else None
        excerpt = _normalize_excerpt(payload.get("excerpt"))
        document_id = _normalize_location_ref(payload.get("document_id"))
        span_id = _normalize_location_ref(payload.get("span_id"))
        document_kind = _normalize_location_ref(payload.get("document_kind"))
        section_path = _normalize_location_ref(payload.get("section_path"))
        precision = _normalize_location_ref(payload.get("precision"))
        confidence = _normalize_location_ref(payload.get("confidence"))

        pointer = cls(
            artifact_id=artifact_id,
            section_ref=section_ref,
            char_start=char_start,
            char_end=char_end,
            excerpt=excerpt,
            document_id=document_id,
            span_id=span_id,
            document_kind=document_kind,
            section_path=section_path,
            precision=precision,
            confidence=confidence,
        )
        pointer.validate()
        return pointer

    def validate(self) -> None:
        if not self.artifact_id:
            raise ClaimEvidenceValidationError("artifact_id is required")
        if not self.excerpt:
            raise ClaimEvidenceValidationError("excerpt is required")

        has_offsets = self.char_start is not None or self.char_end is not None
        if has_offsets and (self.char_start is None or self.char_end is None):
            raise ClaimEvidenceValidationError("char_start and char_end must both be provided")
        if self.char_start is not None and self.char_start < 0:
            raise ClaimEvidenceValidationError("char_start must be >= 0")
        if self.char_start is not None and self.char_end is not None and self.char_end <= self.char_start:
            raise ClaimEvidenceValidationError("char_end must be greater than char_start")

        has_section_ref = self.section_ref is not None
        has_offset_pair = self.char_start is not None and self.char_end is not None
        if not has_section_ref and not has_offset_pair:
            raise ClaimEvidenceValidationError("section_ref or char_start/char_end is required")
        if self.span_id is not None and self.document_id is None:
            raise ClaimEvidenceValidationError("document_id is required when span_id is provided")
        if self.document_kind is not None and self.document_kind not in _LINKAGE_DOCUMENT_KINDS:
            raise ClaimEvidenceValidationError("document_kind must be minutes, agenda, or packet")
        if self.precision is not None and self.precision not in _LINKAGE_PRECISIONS:
            raise ClaimEvidenceValidationError("precision must be offset, span, section, or file")
        if self.confidence is not None and self.confidence not in _LINKAGE_CONFIDENCES:
            raise ClaimEvidenceValidationError("confidence must be high, medium, or low")

    def to_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "section_ref": self.section_ref,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "excerpt": self.excerpt,
            "document_id": self.document_id,
            "span_id": self.span_id,
            "document_kind": self.document_kind,
            "section_path": self.section_path,
            "precision": self.precision,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class SummaryClaim:
    claim_text: str
    evidence: tuple[ClaimEvidencePointer, ...]
    evidence_gap: bool

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> SummaryClaim:
        claim_text_raw = payload.get("claim_text")
        claim_text = claim_text_raw.strip() if isinstance(claim_text_raw, str) else ""
        evidence_payload = payload.get("evidence")

        evidence: list[ClaimEvidencePointer] = []
        if isinstance(evidence_payload, list):
            for raw_pointer in evidence_payload:
                if isinstance(raw_pointer, Mapping):
                    evidence.append(ClaimEvidencePointer.from_payload(raw_pointer))

        return cls(
            claim_text=claim_text,
            evidence=tuple(evidence),
            evidence_gap=not evidence,
        )

    def validate(self) -> None:
        if not self.claim_text:
            raise ClaimEvidenceValidationError("claim_text is required")
        for pointer in self.evidence:
            pointer.validate()

    def to_payload(self) -> dict[str, object]:
        return {
            "claim_text": self.claim_text,
            "evidence": [pointer.to_payload() for pointer in self.evidence],
            "evidence_gap": self.evidence_gap,
        }


@dataclass(frozen=True)
class StructuredRelevanceField:
    value: str
    evidence: tuple[ClaimEvidencePointer, ...] = ()
    confidence: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> StructuredRelevanceField:
        value = _normalize_structured_text(payload.get("value"))
        confidence = _normalize_structured_confidence(payload.get("confidence"))

        evidence: list[ClaimEvidencePointer] = []
        evidence_payload = payload.get("evidence")
        if isinstance(evidence_payload, list):
            for raw_pointer in evidence_payload:
                if isinstance(raw_pointer, Mapping):
                    evidence.append(ClaimEvidencePointer.from_payload(raw_pointer))

        field = cls(value=value, evidence=tuple(evidence), confidence=confidence)
        field.validate()
        return field

    def validate(self) -> None:
        if not self.value:
            raise ClaimEvidenceValidationError("structured relevance field value is required")
        if self.confidence is not None and self.confidence not in _STRUCTURED_RELEVANCE_CONFIDENCES:
            raise ClaimEvidenceValidationError("structured relevance confidence must be high, medium, or low")
        for pointer in self.evidence:
            pointer.validate()

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence == "low"

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"value": self.value}
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.evidence:
            payload["evidence"] = [pointer.to_payload() for pointer in self.evidence]
        return payload


@dataclass(frozen=True)
class StructuredImpactTag:
    tag: str
    evidence: tuple[ClaimEvidencePointer, ...] = ()
    confidence: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> StructuredImpactTag:
        tag = _normalize_structured_text(payload.get("tag"))
        confidence = _normalize_structured_confidence(payload.get("confidence"))

        evidence: list[ClaimEvidencePointer] = []
        evidence_payload = payload.get("evidence")
        if isinstance(evidence_payload, list):
            for raw_pointer in evidence_payload:
                if isinstance(raw_pointer, Mapping):
                    evidence.append(ClaimEvidencePointer.from_payload(raw_pointer))

        impact_tag = cls(tag=tag, evidence=tuple(evidence), confidence=confidence)
        impact_tag.validate()
        return impact_tag

    def validate(self) -> None:
        if not self.tag:
            raise ClaimEvidenceValidationError("impact tag is required")
        if self.confidence is not None and self.confidence not in _STRUCTURED_RELEVANCE_CONFIDENCES:
            raise ClaimEvidenceValidationError("impact tag confidence must be high, medium, or low")
        for pointer in self.evidence:
            pointer.validate()

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence == "low"

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"tag": self.tag}
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.evidence:
            payload["evidence"] = [pointer.to_payload() for pointer in self.evidence]
        return payload


@dataclass(frozen=True)
class StructuredRelevanceItem:
    item_id: str
    subject: StructuredRelevanceField | None = None
    location: StructuredRelevanceField | None = None
    action: StructuredRelevanceField | None = None
    scale: StructuredRelevanceField | None = None
    impact_tags: tuple[StructuredImpactTag, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> StructuredRelevanceItem:
        item = cls(
            item_id=_normalize_structured_text(payload.get("item_id")),
            subject=_read_structured_relevance_field(payload, field="subject"),
            location=_read_structured_relevance_field(payload, field="location"),
            action=_read_structured_relevance_field(payload, field="action"),
            scale=_read_structured_relevance_field(payload, field="scale"),
            impact_tags=_read_structured_impact_tags(payload),
        )
        item.validate()
        return item

    def validate(self) -> None:
        if not self.item_id:
            raise ClaimEvidenceValidationError("structured relevance item_id is required")
        if self.is_empty:
            raise ClaimEvidenceValidationError("structured relevance item requires at least one field or impact tag")

    @property
    def is_empty(self) -> bool:
        return (
            self.subject is None
            and self.location is None
            and self.action is None
            and self.scale is None
            and not self.impact_tags
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"item_id": self.item_id}
        if self.subject is not None:
            payload["subject"] = self.subject.to_payload()
        if self.location is not None:
            payload["location"] = self.location.to_payload()
        if self.action is not None:
            payload["action"] = self.action.to_payload()
        if self.scale is not None:
            payload["scale"] = self.scale.to_payload()
        if self.impact_tags:
            payload["impact_tags"] = [impact_tag.to_payload() for impact_tag in self.impact_tags]
        return payload


@dataclass(frozen=True)
class StructuredRelevance:
    subject: StructuredRelevanceField | None = None
    location: StructuredRelevanceField | None = None
    action: StructuredRelevanceField | None = None
    scale: StructuredRelevanceField | None = None
    impact_tags: tuple[StructuredImpactTag, ...] = ()
    items: tuple[StructuredRelevanceItem, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> StructuredRelevance:
        relevance = cls(
            subject=_read_structured_relevance_field(payload, field="subject"),
            location=_read_structured_relevance_field(payload, field="location"),
            action=_read_structured_relevance_field(payload, field="action"),
            scale=_read_structured_relevance_field(payload, field="scale"),
            impact_tags=_read_structured_impact_tags(payload),
            items=_read_structured_relevance_items(payload),
        )
        return relevance

    @property
    def is_empty(self) -> bool:
        return (
            self.subject is None
            and self.location is None
            and self.action is None
            and self.scale is None
            and not self.impact_tags
            and not self.items
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.subject is not None:
            payload["subject"] = self.subject.to_payload()
        if self.location is not None:
            payload["location"] = self.location.to_payload()
        if self.action is not None:
            payload["action"] = self.action.to_payload()
        if self.scale is not None:
            payload["scale"] = self.scale.to_payload()
        if self.impact_tags:
            payload["impact_tags"] = [impact_tag.to_payload() for impact_tag in self.impact_tags]
        if self.items:
            payload["items"] = [item.to_payload() for item in self.items]
        return payload


@dataclass(frozen=True)
class SummarizationOutput:
    summary: str
    key_decisions: tuple[str, ...]
    key_actions: tuple[str, ...]
    notable_topics: tuple[str, ...]
    claims: tuple[SummaryClaim, ...] = ()
    structured_relevance: StructuredRelevance | None = None
    contract_version: str = SUMMARIZATION_CONTRACT_VERSION

    @classmethod
    def from_sections(
        cls,
        *,
        summary: str,
        key_decisions: Sequence[str] | None,
        key_actions: Sequence[str] | None,
        notable_topics: Sequence[str] | None,
        claims: Sequence[SummaryClaim] | None = None,
        structured_relevance: StructuredRelevance | None = None,
    ) -> SummarizationOutput:
        return cls(
            summary=_normalize_summary(summary),
            key_decisions=_normalize_section_items(key_decisions),
            key_actions=_normalize_section_items(key_actions),
            notable_topics=_normalize_section_items(notable_topics),
            claims=tuple(claims or ()),
            structured_relevance=structured_relevance,
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> SummarizationOutput:
        summary = payload.get("summary")
        if not isinstance(summary, str):
            summary = ""

        return cls.from_sections(
            summary=summary,
            key_decisions=_read_string_list(payload, field="key_decisions"),
            key_actions=_read_string_list(payload, field="key_actions"),
            notable_topics=_read_string_list(payload, field="notable_topics"),
            claims=_read_claims(payload),
            structured_relevance=_read_structured_relevance(payload),
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "contract_version": self.contract_version,
            "summary": self.summary,
            "key_decisions": list(self.key_decisions),
            "key_actions": list(self.key_actions),
            "notable_topics": list(self.notable_topics),
            "claims": [claim.to_payload() for claim in self.claims],
        }
        if self.structured_relevance is not None:
            structured_relevance_payload = self.structured_relevance.to_payload()
            if structured_relevance_payload:
                payload["structured_relevance"] = structured_relevance_payload
        return payload

    @property
    def claim_evidence_gaps(self) -> tuple[str, ...]:
        return tuple(
            claim.claim_text for claim in self.claims if claim.evidence_gap
        )


def _read_string_list(payload: Mapping[str, object], *, field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list):
        return ()

    raw_items: list[str] = []
    for item in value:
        if isinstance(item, str):
            raw_items.append(item)
    return _normalize_section_items(raw_items)


def _read_claims(payload: Mapping[str, object]) -> tuple[SummaryClaim, ...]:
    claims_raw = payload.get("claims")
    if not isinstance(claims_raw, list):
        return ()

    claims: list[SummaryClaim] = []
    for raw_claim in claims_raw:
        if isinstance(raw_claim, Mapping):
            claims.append(SummaryClaim.from_payload(raw_claim))
    return tuple(claims)


def _read_structured_relevance_field(
    payload: Mapping[str, object],
    *,
    field: str,
) -> StructuredRelevanceField | None:
    raw_field = payload.get(field)
    if not isinstance(raw_field, Mapping):
        return None

    field_value = StructuredRelevanceField.from_payload(raw_field)
    return field_value


def _read_structured_impact_tags(payload: Mapping[str, object]) -> tuple[StructuredImpactTag, ...]:
    raw_tags = payload.get("impact_tags")
    if not isinstance(raw_tags, list):
        return ()

    tags: list[StructuredImpactTag] = []
    for raw_tag in raw_tags:
        if isinstance(raw_tag, Mapping):
            tags.append(StructuredImpactTag.from_payload(raw_tag))
    return tuple(tags)


def _read_structured_relevance_items(payload: Mapping[str, object]) -> tuple[StructuredRelevanceItem, ...]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return ()

    items: list[StructuredRelevanceItem] = []
    for raw_item in raw_items:
        if isinstance(raw_item, Mapping):
            items.append(StructuredRelevanceItem.from_payload(raw_item))
    return tuple(items)


def _read_structured_relevance(payload: Mapping[str, object]) -> StructuredRelevance | None:
    raw_relevance = payload.get("structured_relevance")
    if not isinstance(raw_relevance, Mapping):
        return None

    relevance = StructuredRelevance.from_payload(raw_relevance)
    if relevance.is_empty:
        return None
    return relevance


@dataclass(frozen=True)
class ClaimAttachmentResult:
    claims: tuple[str, ...]
    evidence_pointers: tuple[str, ...]
    evidence_gap_claims: tuple[str, ...]


@dataclass(frozen=True)
class QualityGateConfig:
    min_claim_count: int = 1
    min_total_evidence_pointers: int = 1
    min_evidence_coverage_rate: float = 0.75
    max_evidence_gap_claims: int = 0
    min_confidence_score: float | None = None


@dataclass(frozen=True)
class QualityGateDecision:
    publication_status: PublicationStatus
    confidence_label: ConfidenceLabel
    calibration_policy_version: str
    reason_codes: tuple[str, ...]
    claim_count: int
    claims_with_evidence: int
    total_evidence_pointers: int
    evidence_coverage_rate: float
    confidence_score: float | None
    min_confidence_score: float | None


@dataclass(frozen=True)
class PublishedSummarizationResult:
    publication: SummaryPublicationRecord
    quality_gate: QualityGateDecision
    notification_enqueue: NotificationEnqueueResult | None = None
    replay_guard_reason_code: str | None = None


@dataclass(frozen=True)
class QualityGateEnforcementOverride:
    publication_status: PublicationStatus
    confidence_label: ConfidenceLabel
    reason_codes: tuple[str, ...]


def evaluate_quality_gate(
    *,
    output: SummarizationOutput,
    base_confidence_label: ConfidenceLabel = "high",
    config: QualityGateConfig | None = None,
    confidence_score: float | None = None,
    calibration_policy_version: str = DEFAULT_SUMMARY_CALIBRATION_POLICY_VERSION,
) -> QualityGateDecision:
    gate_config = config or QualityGateConfig()

    claim_count = len(output.claims)
    claims_with_evidence = sum(1 for claim in output.claims if not claim.evidence_gap)
    total_evidence_pointers = sum(len(claim.evidence) for claim in output.claims)
    evidence_coverage_rate = (
        claims_with_evidence / claim_count
        if claim_count > 0
        else 0.0
    )

    reason_codes: list[str] = []
    if claim_count < gate_config.min_claim_count:
        reason_codes.append("insufficient_claim_count")
    if total_evidence_pointers < gate_config.min_total_evidence_pointers:
        reason_codes.append("insufficient_evidence_pointers")
    if evidence_coverage_rate < gate_config.min_evidence_coverage_rate:
        reason_codes.append("evidence_coverage_below_threshold")
    evidence_gap_claims = sum(1 for claim in output.claims if claim.evidence_gap)
    if evidence_gap_claims > gate_config.max_evidence_gap_claims:
        reason_codes.append("claim_evidence_gap_present")
    if gate_config.min_confidence_score is not None:
        if confidence_score is None:
            reason_codes.append("confidence_signal_missing_for_policy")
        elif confidence_score < gate_config.min_confidence_score:
            reason_codes.append("confidence_below_policy_threshold")

    if reason_codes:
        return QualityGateDecision(
            publication_status="limited_confidence",
            confidence_label="limited_confidence",
            calibration_policy_version=calibration_policy_version,
            reason_codes=tuple(reason_codes),
            claim_count=claim_count,
            claims_with_evidence=claims_with_evidence,
            total_evidence_pointers=total_evidence_pointers,
            evidence_coverage_rate=evidence_coverage_rate,
            confidence_score=confidence_score,
            min_confidence_score=gate_config.min_confidence_score,
        )

    return QualityGateDecision(
        publication_status="processed",
        confidence_label=base_confidence_label,
        calibration_policy_version=calibration_policy_version,
        reason_codes=("quality_gate_pass",),
        claim_count=claim_count,
        claims_with_evidence=claims_with_evidence,
        total_evidence_pointers=total_evidence_pointers,
        evidence_coverage_rate=evidence_coverage_rate,
        confidence_score=confidence_score,
        min_confidence_score=gate_config.min_confidence_score,
    )


def attach_claim_evidence(
    *,
    repository: MeetingSummaryRepository,
    publication_id: str,
    claims: Sequence[SummaryClaim],
    in_transaction: bool = False,
) -> ClaimAttachmentResult:
    created_claim_ids: list[str] = []
    created_pointer_ids: list[str] = []
    evidence_gap_claims: list[str] = []

    for claim_index, claim in enumerate(claims, start=1):
        claim.validate()
        claim_id = f"{publication_id}:claim:{claim_index}"
        if in_transaction:
            repository.add_claim_in_transaction(
                claim_id=claim_id,
                publication_id=publication_id,
                claim_order=claim_index,
                claim_text=claim.claim_text,
            )
        else:
            repository.add_claim(
                claim_id=claim_id,
                publication_id=publication_id,
                claim_order=claim_index,
                claim_text=claim.claim_text,
            )
        created_claim_ids.append(claim_id)

        if claim.evidence_gap:
            evidence_gap_claims.append(claim_id)
            continue

        for pointer_index, pointer in enumerate(claim.evidence, start=1):
            pointer.validate()
            pointer_id = f"{claim_id}:evidence:{pointer_index}"
            if in_transaction:
                repository.add_claim_evidence_pointer_in_transaction(
                    pointer_id=pointer_id,
                    claim_id=claim_id,
                    artifact_id=pointer.artifact_id,
                    section_ref=pointer.section_ref,
                    char_start=pointer.char_start,
                    char_end=pointer.char_end,
                    excerpt=pointer.excerpt,
                    document_id=pointer.document_id,
                    span_id=pointer.span_id,
                    document_kind=pointer.document_kind,
                    section_path=pointer.section_path,
                    precision=pointer.precision,
                    confidence=pointer.confidence,
                )
            else:
                repository.add_claim_evidence_pointer(
                    pointer_id=pointer_id,
                    claim_id=claim_id,
                    artifact_id=pointer.artifact_id,
                    section_ref=pointer.section_ref,
                    char_start=pointer.char_start,
                    char_end=pointer.char_end,
                    excerpt=pointer.excerpt,
                    document_id=pointer.document_id,
                    span_id=pointer.span_id,
                    document_kind=pointer.document_kind,
                    section_path=pointer.section_path,
                    precision=pointer.precision,
                    confidence=pointer.confidence,
                )
            created_pointer_ids.append(pointer_id)

    return ClaimAttachmentResult(
        claims=tuple(created_claim_ids),
        evidence_pointers=tuple(created_pointer_ids),
        evidence_gap_claims=tuple(evidence_gap_claims),
    )


def persist_summarization_output(
    *,
    repository: MeetingSummaryRepository,
    publication_id: str,
    meeting_id: str,
    processing_run_id: str | None,
    publish_stage_outcome_id: str | None,
    version_no: int,
    publication_status: PublicationStatus,
    confidence_label: ConfidenceLabel,
    output: SummarizationOutput,
    published_at: str | None,
    calibration_policy_version: str = DEFAULT_SUMMARY_CALIBRATION_POLICY_VERSION,
) -> SummaryPublicationRecord:
    with repository.connection:
        write_result = repository.ensure_publication_in_transaction(
            publication_id=publication_id,
            meeting_id=meeting_id,
            processing_run_id=processing_run_id,
            publish_stage_outcome_id=publish_stage_outcome_id,
            version_no=version_no,
            publication_status=publication_status,
            confidence_label=confidence_label,
            calibration_policy_version=calibration_policy_version,
            summary_text=output.summary,
            key_decisions_json=_encode_json_array(output.key_decisions),
            key_actions_json=_encode_json_array(output.key_actions),
            notable_topics_json=_encode_json_array(output.notable_topics),
            published_at=published_at,
        )
        if write_result.created:
            attach_claim_evidence(
                repository=repository,
                publication_id=write_result.publication.id,
                claims=output.claims,
                in_transaction=True,
            )
        return write_result.publication


def publish_summarization_output(
    *,
    repository: MeetingSummaryRepository,
    publication_id: str,
    meeting_id: str,
    processing_run_id: str | None,
    publish_stage_outcome_id: str | None,
    version_no: int,
    base_confidence_label: ConfidenceLabel,
    output: SummarizationOutput,
    published_at: str | None,
    city_id: str | None = None,
    quality_gate_config: QualityGateConfig | None = None,
    confidence_score: float | None = None,
    calibration_policy_version: str | None = None,
    notification_targets: Sequence[NotificationSubscriptionTarget] = (),
    enforcement_override: QualityGateEnforcementOverride | None = None,
) -> PublishedSummarizationResult:
    active_policy_config, active_policy_version = _resolve_calibration_policy(
        repository=repository,
        quality_gate_config=quality_gate_config,
        calibration_policy_version=calibration_policy_version,
    )
    quality_gate = evaluate_quality_gate(
        output=output,
        base_confidence_label=base_confidence_label,
        config=active_policy_config,
        confidence_score=confidence_score,
        calibration_policy_version=active_policy_version,
    )
    if enforcement_override is not None:
        merged_reason_codes: list[str] = []
        for reason_code in [*quality_gate.reason_codes, *enforcement_override.reason_codes]:
            if reason_code not in merged_reason_codes:
                merged_reason_codes.append(reason_code)
        quality_gate = QualityGateDecision(
            publication_status=enforcement_override.publication_status,
            confidence_label=enforcement_override.confidence_label,
            calibration_policy_version=quality_gate.calibration_policy_version,
            reason_codes=tuple(merged_reason_codes),
            claim_count=quality_gate.claim_count,
            claims_with_evidence=quality_gate.claims_with_evidence,
            total_evidence_pointers=quality_gate.total_evidence_pointers,
            evidence_coverage_rate=quality_gate.evidence_coverage_rate,
            confidence_score=quality_gate.confidence_score,
            min_confidence_score=quality_gate.min_confidence_score,
        )
    with repository.connection:
        write_result = repository.ensure_publication_in_transaction(
            publication_id=publication_id,
            meeting_id=meeting_id,
            processing_run_id=processing_run_id,
            publish_stage_outcome_id=publish_stage_outcome_id,
            version_no=version_no,
            publication_status=quality_gate.publication_status,
            confidence_label=quality_gate.confidence_label,
            calibration_policy_version=quality_gate.calibration_policy_version,
            summary_text=output.summary,
            key_decisions_json=_encode_json_array(output.key_decisions),
            key_actions_json=_encode_json_array(output.key_actions),
            notable_topics_json=_encode_json_array(output.notable_topics),
            published_at=published_at,
        )
        if write_result.created:
            attach_claim_evidence(
                repository=repository,
                publication_id=write_result.publication.id,
                claims=output.claims,
                in_transaction=True,
            )
        if publish_stage_outcome_id is not None:
            _annotate_publish_stage_outcome_metadata(
                repository=repository,
                publish_stage_outcome_id=publish_stage_outcome_id,
                quality_gate=quality_gate,
                output=output,
            )
        notification_enqueue = (
            enqueue_publish_notifications_to_outbox(
                connection=repository.connection,
                city_id=city_id,
                meeting_id=meeting_id,
                subscription_targets=notification_targets,
                run_id=processing_run_id,
            )
            if write_result.created and notification_targets and city_id is not None
            else None
        )

    return PublishedSummarizationResult(
        publication=write_result.publication,
        quality_gate=quality_gate,
        notification_enqueue=notification_enqueue,
        replay_guard_reason_code=(None if write_result.created else "publish_stage_outcome_already_materialized"),
    )


def _resolve_calibration_policy(
    *,
    repository: MeetingSummaryRepository,
    quality_gate_config: QualityGateConfig | None,
    calibration_policy_version: str | None,
) -> tuple[QualityGateConfig, str]:
    if quality_gate_config is not None:
        version = calibration_policy_version or DEFAULT_SUMMARY_CALIBRATION_POLICY_VERSION
        return quality_gate_config, version

    policy = ConfidenceCalibrationPolicyRepository(repository.connection).get_active_policy()
    return (
        QualityGateConfig(
            min_claim_count=policy.min_claim_count,
            min_total_evidence_pointers=policy.min_total_evidence_pointers,
            min_evidence_coverage_rate=policy.min_evidence_coverage_rate,
            max_evidence_gap_claims=policy.max_evidence_gap_claims,
            min_confidence_score=policy.min_confidence_score,
        ),
        policy.version,
    )


def _annotate_publish_stage_outcome_metadata(
    *,
    repository: MeetingSummaryRepository,
    publish_stage_outcome_id: str,
    quality_gate: QualityGateDecision,
    output: SummarizationOutput,
) -> None:
    existing_row = repository.connection.execute(
        """
        SELECT metadata_json
        FROM processing_stage_outcomes
        WHERE id = ?
        """,
        (publish_stage_outcome_id,),
    ).fetchone()
    if existing_row is None:
        return

    metadata: dict[str, object]
    metadata_json = existing_row[0]
    if metadata_json is None:
        metadata = {}
    else:
        try:
            parsed = json.loads(str(metadata_json))
        except json.JSONDecodeError:
            parsed = {}
        metadata = parsed if isinstance(parsed, dict) else {}

    metadata["calibration_policy_version"] = quality_gate.calibration_policy_version
    metadata["calibration_min_confidence_score"] = quality_gate.min_confidence_score
    metadata["calibration_confidence_score"] = quality_gate.confidence_score
    metadata["quality_gate_reason_codes"] = list(quality_gate.reason_codes)
    if output.structured_relevance is not None:
        structured_relevance_payload = output.structured_relevance.to_payload()
        if structured_relevance_payload:
            metadata["structured_relevance"] = structured_relevance_payload

    repository.connection.execute(
        """
        UPDATE processing_stage_outcomes
        SET
            metadata_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            json.dumps(metadata, separators=(",", ":"), sort_keys=True),
            publish_stage_outcome_id,
        ),
    )