from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from councilsense.app.notification_fanout import (
    NotificationEnqueueResult,
    NotificationSubscriptionTarget,
    enqueue_publish_notifications_to_outbox,
)
from councilsense.db import ConfidenceLabel, MeetingSummaryRepository, PublicationStatus, SummaryPublicationRecord


SUMMARIZATION_CONTRACT_VERSION = "st-005-v1"
EMPTY_SUMMARY_TEXT = "No summary available."


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


class ClaimEvidenceValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ClaimEvidencePointer:
    artifact_id: str
    section_ref: str | None
    char_start: int | None
    char_end: int | None
    excerpt: str

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

        pointer = cls(
            artifact_id=artifact_id,
            section_ref=section_ref,
            char_start=char_start,
            char_end=char_end,
            excerpt=excerpt,
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

    def to_payload(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "section_ref": self.section_ref,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "excerpt": self.excerpt,
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
class SummarizationOutput:
    summary: str
    key_decisions: tuple[str, ...]
    key_actions: tuple[str, ...]
    notable_topics: tuple[str, ...]
    claims: tuple[SummaryClaim, ...] = ()
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
    ) -> SummarizationOutput:
        return cls(
            summary=_normalize_summary(summary),
            key_decisions=_normalize_section_items(key_decisions),
            key_actions=_normalize_section_items(key_actions),
            notable_topics=_normalize_section_items(notable_topics),
            claims=tuple(claims or ()),
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
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "summary": self.summary,
            "key_decisions": list(self.key_decisions),
            "key_actions": list(self.key_actions),
            "notable_topics": list(self.notable_topics),
            "claims": [claim.to_payload() for claim in self.claims],
        }

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


@dataclass(frozen=True)
class QualityGateDecision:
    publication_status: PublicationStatus
    confidence_label: ConfidenceLabel
    reason_codes: tuple[str, ...]
    claim_count: int
    claims_with_evidence: int
    total_evidence_pointers: int
    evidence_coverage_rate: float


@dataclass(frozen=True)
class PublishedSummarizationResult:
    publication: SummaryPublicationRecord
    quality_gate: QualityGateDecision
    notification_enqueue: NotificationEnqueueResult | None = None


def evaluate_quality_gate(
    *,
    output: SummarizationOutput,
    base_confidence_label: ConfidenceLabel = "high",
    config: QualityGateConfig | None = None,
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

    if reason_codes:
        return QualityGateDecision(
            publication_status="limited_confidence",
            confidence_label="limited_confidence",
            reason_codes=tuple(reason_codes),
            claim_count=claim_count,
            claims_with_evidence=claims_with_evidence,
            total_evidence_pointers=total_evidence_pointers,
            evidence_coverage_rate=evidence_coverage_rate,
        )

    return QualityGateDecision(
        publication_status="processed",
        confidence_label=base_confidence_label,
        reason_codes=("quality_gate_pass",),
        claim_count=claim_count,
        claims_with_evidence=claims_with_evidence,
        total_evidence_pointers=total_evidence_pointers,
        evidence_coverage_rate=evidence_coverage_rate,
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
) -> SummaryPublicationRecord:
    with repository.connection:
        publication = repository.create_publication_in_transaction(
            publication_id=publication_id,
            meeting_id=meeting_id,
            processing_run_id=processing_run_id,
            publish_stage_outcome_id=publish_stage_outcome_id,
            version_no=version_no,
            publication_status=publication_status,
            confidence_label=confidence_label,
            summary_text=output.summary,
            key_decisions_json=_encode_json_array(output.key_decisions),
            key_actions_json=_encode_json_array(output.key_actions),
            notable_topics_json=_encode_json_array(output.notable_topics),
            published_at=published_at,
        )
        attach_claim_evidence(
            repository=repository,
            publication_id=publication.id,
            claims=output.claims,
            in_transaction=True,
        )
        return publication


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
    notification_targets: Sequence[NotificationSubscriptionTarget] = (),
) -> PublishedSummarizationResult:
    quality_gate = evaluate_quality_gate(
        output=output,
        base_confidence_label=base_confidence_label,
        config=quality_gate_config,
    )
    with repository.connection:
        publication = repository.create_publication_in_transaction(
            publication_id=publication_id,
            meeting_id=meeting_id,
            processing_run_id=processing_run_id,
            publish_stage_outcome_id=publish_stage_outcome_id,
            version_no=version_no,
            publication_status=quality_gate.publication_status,
            confidence_label=quality_gate.confidence_label,
            summary_text=output.summary,
            key_decisions_json=_encode_json_array(output.key_decisions),
            key_actions_json=_encode_json_array(output.key_actions),
            notable_topics_json=_encode_json_array(output.notable_topics),
            published_at=published_at,
        )
        attach_claim_evidence(
            repository=repository,
            publication_id=publication.id,
            claims=output.claims,
            in_transaction=True,
        )
        notification_enqueue = (
            enqueue_publish_notifications_to_outbox(
                connection=repository.connection,
                city_id=city_id,
                meeting_id=meeting_id,
                subscription_targets=notification_targets,
            )
            if notification_targets and city_id is not None
            else None
        )

    return PublishedSummarizationResult(
        publication=publication,
        quality_gate=quality_gate,
        notification_enqueue=notification_enqueue,
    )