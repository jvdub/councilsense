from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from councilsense.app.quality_gate_rollout import (
    QualityGateRolloutConfig,
    append_promotion_artifact,
    append_shadow_diagnostics_artifact,
    build_quality_gate_rollout_metadata,
    compute_promotion_status,
    decide_enforcement_outcome,
    evaluate_shadow_gates,
    resolve_rollout_config,
)
from councilsense.app.canonical_persistence import EvidenceSpanInput, persist_pipeline_canonical_records
from councilsense.app.multi_document_compose import (
    ComposedSourceDocument,
    ComposedSourceSpan,
    LocatorPrecision,
    SourceCoverageStatus,
    SummarizeComposeInput,
    assemble_summarize_compose_input,
)
from councilsense.app.multi_document_observability import (
    MultiDocumentLogContractError,
    derive_artifact_id,
    emit_multi_document_stage_event,
    resolve_stage_source_type,
)
from councilsense.app.notable_topics import sanitize_notable_topics
from councilsense.app.st031_source_observability import (
    SourceAwareMetricEmitter,
    emit_citation_precision_ratio,
    emit_source_coverage_ratio,
    emit_source_stage_outcome,
)
from councilsense.app.st030_document_aware_gates import DocumentAwareGateInput
from councilsense.app.summarization import (
    ClaimEvidencePointer,
    QualityGateEnforcementOverride,
    StructuredImpactTag,
    StructuredRelevance,
    StructuredRelevanceField,
    StructuredRelevanceItem,
    SummaryClaim,
    SummarizationOutput,
    publish_summarization_output,
)
from councilsense.app.specificity import anchor_present_in_projection, harvest_relevance_anchors, harvest_specificity_anchors
from councilsense.db import MeetingSummaryRepository, ProcessingLifecycleService, ProcessingRunRepository, RunLifecycleStatus


_DEFAULT_ARTIFACT_ROOT = "/tmp/councilsense-local-latest-artifacts"
_DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
_DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
_DEFAULT_OPENAI_ENDPOINT = "https://api.openai.com/v1"
_DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", flags=re.IGNORECASE | re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", flags=re.DOTALL)
_GENERIC_TOPIC_TOKENS = frozenset(
    {
        "approved",
        "approve",
        "agreement",
        "item",
        "meeting",
        "minutes",
        "agenda",
        "scheduled",
        "motion",
        "vote",
        "council",
        "city",
        "staff",
    }
)
_TOPIC_SUPPRESSION_TOKENS = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "were",
        "have",
        "will",
        "local",
        "runtime",
        "ollama",
        "generated",
        "provider",
        "summary",
        "claim",
        "selected",
        "file",
        "published",
        "eagle",
        "mountain",
        "utah",
        "present",
        "officials",
        "recording",
        "found",
        "online",
        "councilmember",
        "mayor",
        "determined",
    }
)
_TOPIC_CONCEPT_RULES: tuple[tuple[str, str], ...] = (
    ("appointment", "Board and Commission Appointments"),
    ("legislative update", "Legislative Update"),
    ("legislative", "Legislative Update"),
    ("financial report", "Quarterly Financial Report"),
    ("quarterly financial report", "Quarterly Financial Report"),
    ("purchase agreement", "Purchase Agreement Approval"),
    ("right-of-way", "Right-of-Way Acquisition"),
    ("consent agenda", "Consent Agenda Changes"),
    ("public hearing", "Public Hearing Scheduling"),
    ("future land use", "Land Use Planning"),
    ("land use", "Land Use Planning"),
    ("zoning", "Zoning and Land Use"),
    ("youth council", "Youth Council Code"),
    ("ordinance", "Ordinance Adoption"),
    ("resolution", "Resolution Approval"),
    ("budget", "Budget and Fiscal Planning"),
    ("fiscal", "Budget and Fiscal Planning"),
    ("bond release", "Bond Releases"),
    ("bond releases", "Bond Releases"),
    ("change order", "Project Change Orders"),
    ("transportation", "Transportation Infrastructure"),
    ("traffic", "Transportation Infrastructure"),
    ("water", "Water and Utility Infrastructure"),
    ("wastewater", "Water and Utility Infrastructure"),
    ("capital improvement", "Capital Improvement Planning"),
    ("annexation", "Annexation and Boundary Planning"),
    ("title transfer", "Property Title Transfer"),
    ("development agreement", "Development Agreement Terms"),
    ("road", "Roadway Improvements"),
    ("sidewalk", "Roadway Improvements"),
    ("park", "Parks and Recreation Planning"),
    ("safety", "Public Safety Measures"),
)
_TOPIC_FALLBACK_LABELS: tuple[tuple[str, str], ...] = (
    ("appointment", "Board and Commission Appointments"),
    ("legislative", "Legislative Update"),
    ("financial report", "Quarterly Financial Report"),
    ("budget", "Budget and Fiscal Planning"),
    ("land use", "Land Use Planning"),
    ("youth council", "Youth Council Code"),
    ("bond release", "Bond Releases"),
    ("change order", "Project Change Orders"),
    ("zoning", "Zoning and Land Use"),
    ("hearing", "Public Hearing Scheduling"),
    ("transportation", "Transportation Infrastructure"),
    ("traffic", "Transportation Infrastructure"),
    ("water", "Water and Utility Infrastructure"),
    ("wastewater", "Water and Utility Infrastructure"),
    ("road", "Roadway Improvements"),
    ("agreement", "Agreement and Contract Actions"),
    ("ordinance", "Ordinance Adoption"),
    ("resolution", "Resolution Approval"),
)

_MEETING_OPERATIONS_MARKERS: tuple[str, ...] = (
    "roll call",
    "call to order",
    "pledge of allegiance",
    "present electronically",
    "joined the meeting",
    "was excused",
    "mayor pro tempore",
    "council chambers",
    "city recorder",
    "attendance",
)
_STRUCTURED_ACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:approved?|authorize[sd]?|adopt(?:ed)?|ratif(?:ied|y)|accepted?|awarded?)\b", flags=re.IGNORECASE), "approved"),
    (re.compile(r"\b(?:direct(?:ed)?|instruct(?:ed)?)\b", flags=re.IGNORECASE), "directed"),
    (re.compile(r"\b(?:schedule[sd]?|public hearing)\b", flags=re.IGNORECASE), "scheduled"),
    (re.compile(r"\b(?:continue[sd]?|deferred?|postponed|tabled)\b", flags=re.IGNORECASE), "continued"),
    (re.compile(r"\b(?:denied|deny|rejected|reject)\b", flags=re.IGNORECASE), "denied"),
    (re.compile(r"\breview(?:ed)?\b", flags=re.IGNORECASE), "reviewed"),
)
_STRUCTURED_SUBJECT_ENDINGS = (
    "right-of-way acquisition",
    "paving contract",
    "purchase agreement",
    "development agreement",
    "road closure permit",
    "rezoning application",
    "rezoning",
    "capital improvement plan",
    "improvement plan",
    "master plan",
    "general plan",
    "site plan",
    "bond documents",
    "budget transfer",
    "fee schedule",
    "ordinance",
    "resolution",
    "contract",
    "agreement",
    "permit",
    "acquisition",
    "project",
    "plan",
    "annexation",
    "subdivision",
    "application",
    "amendment",
)
_STRUCTURED_SUBJECT_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z0-9&'./-]+(?:\s+[A-Z][A-Za-z0-9&'./-]+){0,5}\s+(?:"
    + "|".join(re.escape(item) for item in _STRUCTURED_SUBJECT_ENDINGS)
    + r")\b",
)
_STRUCTURED_GENERIC_SUBJECTS = frozenset(
    {
        "agenda item",
        "item",
        "proposal",
        "amendment",
        "resolution",
        "ordinance",
        "contract",
        "agreement",
        "permit",
        "plan",
        "project",
        "application",
    }
)
_GENERIC_CARRY_THROUGH_PATTERN = re.compile(
    r"\b(?:approved?|authorize[sd]?|adopt(?:ed)?|ratif(?:ied|y)|accepted?|awarded?|continue[sd]?|denied|reject(?:ed)?|review(?:ed)?|schedule[sd]?|direct(?:ed)?)\b"
    r"(?:\s+(?:the|a|an))?\s+(?:agenda item|item|items|proposal|project|plan|request|application|amendment|resolution|ordinance|contract|agreement|measure)\b",
    flags=re.IGNORECASE,
)
_APPROVED_IMPACT_TAGS: tuple[str, ...] = (
    "housing",
    "traffic",
    "utilities",
    "parks",
    "fees",
    "land_use",
)
_HOUSING_TERMS_PATTERN = re.compile(
    r"\b(?:housing|residential|apartment(?:s)?|dwelling(?:s)?|home(?:s)?|townhome(?:s)?|condo(?:minium)?s?|multifamily|single-family|affordable housing|subdivision)\b",
    flags=re.IGNORECASE,
)
_HOUSING_UNITS_PATTERN = re.compile(r"\b\d{1,5}\s+units\b", flags=re.IGNORECASE)
_HOUSING_PROJECT_PATTERN = re.compile(
    r"\b(?:development|rezoning|zoning|site plan|annexation|plat|planned community)\b",
    flags=re.IGNORECASE,
)
_TRAFFIC_TERMS_PATTERN = re.compile(
    r"\b(?:traffic|transportation|paving|right-of-way|road closure|intersection|signal(?:ization)?|sidewalk|crosswalk|parking|lane|corridor|transit|traffic control)\b",
    flags=re.IGNORECASE,
)
_UTILITIES_TERMS_PATTERN = re.compile(
    r"\b(?:utility|utilities|water|wastewater|stormwater|sewer|drainage|power|electric|broadband)\b",
    flags=re.IGNORECASE,
)
_PARKS_TERMS_PATTERN = re.compile(
    r"\b(?:park|parks|playground|recreation|trail|open space)\b",
    flags=re.IGNORECASE,
)
_FEES_TERMS_PATTERN = re.compile(
    r"\b(?:fee(?:s)?|rate(?:s)?|ratepayer(?:s)?|tariff|assessment(?:s)?)\b",
    flags=re.IGNORECASE,
)
_LAND_USE_TERMS_PATTERN = re.compile(
    r"\b(?:rezoning|rezone|zoning|land use|annexation|subdivision|plat|overlay|site plan|general plan|master plan|development agreement)\b",
    flags=re.IGNORECASE,
)



logger = logging.getLogger(__name__)


def _load_topic_token_config(*, env_key: str, defaults: frozenset[str]) -> frozenset[str]:
    raw = os.getenv(env_key)
    if raw is None:
        return defaults

    configured = {
        token.strip().lower()
        for token in raw.split(",")
        if token.strip()
    }
    if not configured:
        return defaults
    return frozenset({*defaults, *configured})


def _topic_suppression_tokens() -> frozenset[str]:
    return _load_topic_token_config(
        env_key="COUNCILSENSE_TOPIC_SUPPRESSION_TOKENS",
        defaults=_TOPIC_SUPPRESSION_TOKENS,
    )


def _topic_generic_tokens() -> frozenset[str]:
    return _load_topic_token_config(
        env_key="COUNCILSENSE_TOPIC_GENERIC_TOKENS",
        defaults=_GENERIC_TOPIC_TOKENS,
    )


class LocalPipelineError(RuntimeError):
    def __init__(self, *, stage: str, message: str, operator_hint: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.operator_hint = operator_hint


@dataclass(frozen=True)
class ProcessLatestResult:
    run_id: str
    city_id: str
    source_id: str | None
    meeting_id: str | None
    status: str
    stage_outcomes: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]
    error_summary: dict[str, object] | None


@dataclass(frozen=True)
class _MeetingContext:
    meeting_id: str
    title: str


@dataclass(frozen=True)
class _ExtractedPayload:
    text: str
    artifact_id: str
    section_ref: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class _SummarizePayload:
    output: SummarizationOutput
    provider_requested: str
    provider_used: str
    fallback_reason: str | None
    authority_policy: _AuthorityPolicyResult


@dataclass(frozen=True)
class _MeetingMaterialContext:
    document_kind: str | None
    meeting_date_iso: str | None
    meeting_temporal_status: str | None

    @property
    def is_preview_only(self) -> bool:
        return self.document_kind in {"agenda", "packet"}

    @property
    def is_same_day_or_future(self) -> bool:
        return self.meeting_temporal_status == "same_day_or_future"


@dataclass(frozen=True)
class LlmProviderConfig:
    provider: str
    endpoint: str | None = None
    model: str | None = None
    timeout_seconds: float = 20.0
    api_key: str | None = None

    @property
    def normalized_provider(self) -> str:
        normalized = self.provider.strip().lower()
        return normalized or "none"


@dataclass(frozen=True)
class _AuthorityConflictSignal:
    authoritative_source_type: str | None
    conflicting_source_type: str
    subject: str | None
    authoritative_action: str | None
    conflicting_action: str | None
    authoritative_finding: str | None
    conflicting_finding: str
    resolution: str

    def to_metadata_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "conflicting_source_type": self.conflicting_source_type,
            "resolution": self.resolution,
        }
        if self.authoritative_source_type is not None:
            payload["authoritative_source_type"] = self.authoritative_source_type
        if self.subject is not None:
            payload["subject"] = self.subject
        if self.authoritative_action is not None:
            payload["authoritative_action"] = self.authoritative_action
        if self.conflicting_action is not None:
            payload["conflicting_action"] = self.conflicting_action
        if self.authoritative_finding is not None:
            payload["authoritative_finding"] = self.authoritative_finding
        payload["conflicting_finding"] = self.conflicting_finding
        return payload


@dataclass(frozen=True)
class _AuthorityPolicyResult:
    authority_outcome: str
    publication_status: str
    reason_codes: tuple[str, ...]
    summarize_text: str
    authoritative_source_type: str | None
    authoritative_locator_precision: LocatorPrecision | None
    outcome_source_types: tuple[str, ...]
    source_statuses: dict[str, SourceCoverageStatus]
    preview_only: bool
    conflicts: tuple[_AuthorityConflictSignal, ...]

    def to_metadata_payload(self) -> dict[str, object]:
        return {
            "authority_outcome": self.authority_outcome,
            "publication_status": self.publication_status,
            "reason_codes": list(self.reason_codes),
            "authoritative_source_type": self.authoritative_source_type,
            "authoritative_locator_precision": self.authoritative_locator_precision,
            "outcome_source_types": list(self.outcome_source_types),
            "source_statuses": dict(self.source_statuses),
            "preview_only": self.preview_only,
            "has_conflicts": bool(self.conflicts),
            "conflicts": [signal.to_metadata_payload() for signal in self.conflicts],
        }


def _ordered_unique_codes(*codes: str) -> tuple[str, ...]:
    ordered: list[str] = []
    for code in codes:
        normalized = code.strip()
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return tuple(ordered)


def _build_authority_policy_result(
    *,
    authority_outcome: str,
    publication_status: str,
    reason_codes: tuple[str, ...],
    summarize_text: str,
    authoritative_source_type: str | None,
    authoritative_locator_precision: LocatorPrecision | None,
    outcome_source_types: tuple[str, ...],
    source_statuses: dict[str, SourceCoverageStatus],
    preview_only: bool,
    conflicts: tuple[_AuthorityConflictSignal, ...],
) -> _AuthorityPolicyResult:
    return _AuthorityPolicyResult(
        authority_outcome=authority_outcome,
        publication_status=publication_status,
        reason_codes=_ordered_unique_codes(*reason_codes),
        summarize_text=summarize_text,
        authoritative_source_type=authoritative_source_type,
        authoritative_locator_precision=authoritative_locator_precision,
        outcome_source_types=tuple(dict.fromkeys(outcome_source_types)),
        source_statuses=dict(source_statuses),
        preview_only=preview_only,
        conflicts=conflicts,
    )


@dataclass(frozen=True)
class _AuthorityOutcomeSignal:
    source_type: str
    finding: str
    subject: str | None
    action_class: str


@dataclass(frozen=True)
class _RelevanceSnippet:
    text: str
    source: ComposedSourceDocument | None
    span: ComposedSourceSpan | None
    sentence_index: int | None
    char_start: int | None
    char_end: int | None


@dataclass(frozen=True)
class _StructuredRelevanceCandidate:
    subject: str | None
    location: str | None
    action: str | None
    scale: str | None
    evidence: ClaimEvidencePointer
    source_type: str | None
    rank: tuple[int, int, int, int, str]


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if normalized:
            self._parts.append(normalized)

    def as_text(self) -> str:
        return " ".join(self._parts).strip()


class LocalPipelineOrchestrator:
    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        metric_emitter: SourceAwareMetricEmitter | None = None,
    ) -> None:
        self._connection = connection
        self._run_repository = ProcessingRunRepository(connection)
        self._lifecycle_service = ProcessingLifecycleService(self._run_repository)
        self._metric_emitter = metric_emitter

    def process_latest(
        self,
        *,
        run_id: str,
        city_id: str,
        meeting_id: str | None,
        ingest_stage_metadata: dict[str, object] | None,
        llm_config: LlmProviderConfig,
    ) -> ProcessLatestResult:
        stage_outcomes: list[dict[str, object]] = []
        warnings: list[str] = []
        resolved_meeting_id: str | None = None
        extracted_artifact_id: str | None = None
        source_id, source_type, source_url = self._resolve_source(city_id=city_id)
        cycle_id = _now_iso_utc()
        self._run_repository.create_pending_run(run_id=run_id, city_id=city_id, cycle_id=cycle_id)

        fallback_used = False
        try:
            meeting = self._resolve_meeting(city_id=city_id, meeting_id=meeting_id)
            resolved_meeting_id = meeting.meeting_id
            try:
                rollout_config = resolve_rollout_config(environment=os.getenv("COUNCILSENSE_RUNTIME_ENV"), cohort=city_id)
            except ValueError as exc:
                raise LocalPipelineError(
                    stage="summarize",
                    message=f"Invalid ST-021 rollout configuration: {exc}",
                    operator_hint="Fix COUNCILSENSE_QG_CONFIG_JSON or rollout environment variables and rerun process-latest.",
                ) from exc

            if ingest_stage_metadata is not None:
                self._upsert_stage_outcome(
                    run_id=run_id,
                    city_id=city_id,
                    meeting_id=meeting.meeting_id,
                    stage_name="ingest",
                    status="processed",
                    metadata=ingest_stage_metadata,
                    started_at=_now_iso_utc(),
                    finished_at=_now_iso_utc(),
                )

            material_context = self._resolve_meeting_material_context(
                meeting_id=meeting.meeting_id,
                ingest_stage_metadata=ingest_stage_metadata,
            )

            extract_payload, extract_status = self._extract_stage(
                run_id=run_id,
                city_id=city_id,
                meeting=meeting,
                source_id=source_id,
                source_type=source_type,
                source_url=source_url,
            )
            extracted_artifact_id = extract_payload.artifact_id
            stage_outcomes.append(
                {
                    "stage": "extract",
                    "status": extract_status,
                    "metadata": extract_payload.metadata,
                }
            )
            if extract_status == "limited_confidence":
                warnings.append("extract_metadata_fallback_used")

            summarize_payload, summarize_status = self._summarize_stage(
                run_id=run_id,
                city_id=city_id,
                meeting_id=meeting.meeting_id,
                source_id=source_id,
                source_type=source_type,
                extracted=extract_payload,
                material_context=material_context,
                rollout_config=rollout_config,
                llm_config=llm_config,
            )
            summarize_metadata: dict[str, object] = {
                "provider_used": summarize_payload.provider_used,
                "claim_count": len(summarize_payload.output.claims),
                "authority_policy": summarize_payload.authority_policy.to_metadata_payload(),
            }
            if summarize_payload.output.structured_relevance is not None:
                structured_relevance_payload = summarize_payload.output.structured_relevance.to_payload()
                if structured_relevance_payload:
                    summarize_metadata["structured_relevance"] = structured_relevance_payload
            if summarize_payload.fallback_reason is not None:
                fallback_used = True
                summarize_metadata["fallback_reason"] = summarize_payload.fallback_reason
                warnings.append(f"{summarize_payload.provider_requested}_fallback_to_deterministic")

            stage_outcomes.append(
                {
                    "stage": "summarize",
                    "status": summarize_status,
                    "metadata": summarize_metadata,
                }
            )

            persist_pipeline_canonical_records(
                self._connection,
                meeting_id=meeting.meeting_id,
                source_id=source_id,
                source_url=source_url,
                extracted_text=extract_payload.text,
                extraction_status=extract_status,
                extraction_confidence=(0.95 if extract_status == "processed" else 0.6),
                artifact_storage_uri=(
                    str(extract_payload.metadata.get("artifact_path"))
                    if isinstance(extract_payload.metadata.get("artifact_path"), str)
                    else None
                ),
                evidence_spans=_evidence_spans_from_output(summarize_payload.output),
            )

            publish_stage = self._publish_stage(
                run_id=run_id,
                city_id=city_id,
                source_id=source_id,
                source_type=source_type,
                artifact_id=extract_payload.artifact_id,
                meeting_id=meeting.meeting_id,
                output=summarize_payload.output,
                source_text=extract_payload.text,
                material_context=material_context,
                authority_policy=summarize_payload.authority_policy,
                extract_status=extract_status,
                summarize_status=summarize_status,
                summarize_fallback_used=(summarize_payload.fallback_reason is not None),
                rollout_config=rollout_config,
            )
            stage_outcomes.append(publish_stage)

            if fallback_used or publish_stage["status"] == "limited_confidence":
                run = self._lifecycle_service.mark_limited_confidence(run_id=run_id)
            else:
                run = self._lifecycle_service.mark_processed(run_id=run_id)

            return ProcessLatestResult(
                run_id=run.id,
                city_id=city_id,
                source_id=source_id,
                meeting_id=resolved_meeting_id,
                status=run.status,
                stage_outcomes=tuple(stage_outcomes),
                warnings=tuple(warnings),
                error_summary=None,
            )
        except LocalPipelineError as exc:
            failure_meeting_id = resolved_meeting_id or "meeting-unknown"
            failure_artifact_id = extracted_artifact_id or derive_artifact_id(
                artifact_path=(
                    str(ingest_stage_metadata.get("artifact_path"))
                    if isinstance(ingest_stage_metadata, dict) and isinstance(ingest_stage_metadata.get("artifact_path"), str)
                    else None
                ),
                meeting_id=failure_meeting_id,
            )
            failure_source_id = source_id or "source-unknown"
            if exc.stage != "publish":
                try:
                    emit_multi_document_stage_event(
                        event_name="pipeline_stage_error",
                        stage=exc.stage,
                        outcome="failure",
                        status="failed",
                        city_id=city_id,
                        meeting_id=failure_meeting_id,
                        run_id=run_id,
                        source_id=failure_source_id,
                        source_type=resolve_stage_source_type(stage=exc.stage, source_type=source_type),
                        artifact_id=failure_artifact_id,
                        extra_fields={
                            "error_code": exc.__class__.__name__,
                            "error_message": str(exc),
                        },
                    )
                except MultiDocumentLogContractError:
                    logger.exception("pipeline_multi_document_failure_log_contract_error")
            if exc.stage != "publish":
                emit_source_stage_outcome(
                    self._metric_emitter,
                    stage=exc.stage,
                    outcome="failure",
                    city_id=city_id,
                    source_type=resolve_stage_source_type(stage=exc.stage, source_type=source_type),
                    status="failed",
                )
            self._lifecycle_service.mark_failed(run_id=run_id)
            return ProcessLatestResult(
                run_id=run_id,
                city_id=city_id,
                source_id=source_id,
                meeting_id=resolved_meeting_id,
                status="failed",
                stage_outcomes=self._list_stage_outcomes(run_id=run_id, city_id=city_id),
                warnings=tuple(warnings),
                error_summary={
                    "stage": exc.stage,
                    "error_class": exc.__class__.__name__,
                    "message": str(exc),
                    "operator_hint": exc.operator_hint,
                },
            )

    def _list_stage_outcomes(self, *, run_id: str, city_id: str) -> tuple[dict[str, object], ...]:
        ordered_stage_names = ("ingest", "extract", "summarize", "publish")
        stage_order = {name: index for index, name in enumerate(ordered_stage_names)}
        records = self._run_repository.list_stage_outcomes_for_run_city(run_id=run_id, city_id=city_id)

        normalized: list[dict[str, object]] = []
        for record in records:
            metadata: dict[str, object] = {}
            if record.metadata_json:
                try:
                    parsed = json.loads(record.metadata_json)
                    if isinstance(parsed, dict):
                        metadata = parsed
                except json.JSONDecodeError:
                    metadata = {}
            normalized.append(
                {
                    "stage": record.stage_name,
                    "status": record.status,
                    "metadata": metadata,
                }
            )

        normalized.sort(key=lambda item: stage_order.get(str(item["stage"]), 99))
        return tuple(normalized)

    def _resolve_meeting_material_context(
        self,
        *,
        meeting_id: str,
        ingest_stage_metadata: dict[str, object] | None,
    ) -> _MeetingMaterialContext:
        metadata = ingest_stage_metadata or self._load_latest_ingest_stage_metadata(meeting_id=meeting_id)
        if metadata is None:
            return _MeetingMaterialContext(document_kind=None, meeting_date_iso=None, meeting_temporal_status=None)

        raw_document_kind = metadata.get("candidate_document_kind") or metadata.get("selected_file_type")
        document_kind = _normalize_document_kind(str(raw_document_kind)) if raw_document_kind is not None else None

        raw_meeting_date = metadata.get("meeting_date") or metadata.get("selected_event_date")
        meeting_date_iso = str(raw_meeting_date).strip() if isinstance(raw_meeting_date, str) and raw_meeting_date.strip() else None

        raw_temporal_status = metadata.get("meeting_temporal_status")
        meeting_temporal_status = (
            str(raw_temporal_status).strip() if isinstance(raw_temporal_status, str) and raw_temporal_status.strip() else None
        )
        if meeting_temporal_status is None:
            meeting_temporal_status = _classify_meeting_temporal_status(meeting_date_iso)

        return _MeetingMaterialContext(
            document_kind=document_kind,
            meeting_date_iso=meeting_date_iso,
            meeting_temporal_status=meeting_temporal_status,
        )

    def _load_latest_ingest_stage_metadata(self, *, meeting_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            """
            SELECT metadata_json
            FROM processing_stage_outcomes
            WHERE meeting_id = ?
              AND stage_name = 'ingest'
            ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
            LIMIT 1
            """,
            (meeting_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        try:
            parsed = json.loads(str(row[0]))
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def _resolve_meeting(self, *, city_id: str, meeting_id: str | None) -> _MeetingContext:
        if meeting_id is not None:
            row = self._connection.execute(
                """
                SELECT id, title
                FROM meetings
                WHERE city_id = ?
                  AND id = ?
                """,
                (city_id, meeting_id),
            ).fetchone()
            if row is None:
                raise LocalPipelineError(
                    stage="extract",
                    message=f"Meeting not found for city_id={city_id}: meeting_id={meeting_id}",
                    operator_hint="Run fetch-latest first or pass a valid --meeting-id.",
                )
            return _MeetingContext(meeting_id=str(row[0]), title=str(row[1]))

        row = self._connection.execute(
            """
            SELECT id, title
            FROM meetings
            WHERE city_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (city_id,),
        ).fetchone()
        if row is None:
            raise LocalPipelineError(
                stage="extract",
                message=f"No meetings available for city_id={city_id}",
                operator_hint="Run fetch-latest to ingest the latest source before process-latest.",
            )
        return _MeetingContext(meeting_id=str(row[0]), title=str(row[1]))

    def _resolve_source(self, *, city_id: str) -> tuple[str | None, str | None, str | None]:
        rows = self._connection.execute(
            """
            SELECT id, source_type, source_url
            FROM city_sources
            WHERE city_id = ?
              AND enabled = 1
            ORDER BY CASE WHEN source_type = 'minutes' THEN 0 ELSE 1 END, id ASC
            """,
            (city_id,),
        ).fetchall()
        if not rows:
            return None, None, None
        first = rows[0]
        return str(first[0]), str(first[1]), str(first[2])

    def _extract_stage(
        self,
        *,
        run_id: str,
        city_id: str,
        meeting: _MeetingContext,
        source_id: str | None,
        source_type: str | None,
        source_url: str | None,
    ) -> tuple[_ExtractedPayload, str]:
        started_at = _now_iso_utc()
        artifact_path = _find_artifact_path(city_id=city_id, meeting_id=meeting.meeting_id)
        if artifact_path is not None and artifact_path.exists():
            artifact_bytes = artifact_path.read_bytes()
            extracted, extract_mode = _extract_text_from_artifact_bytes(artifact_bytes, artifact_path=artifact_path)
            if not extracted:
                extracted = meeting.title
            section_ref = "artifact.pdf" if extract_mode == "pdf_artifact" else "artifact.html"
            payload = _ExtractedPayload(
                text=extracted,
                artifact_id=f"artifact-local:{artifact_path.name}",
                section_ref=section_ref,
                metadata={
                    "source_id": source_id,
                    "source_type": source_type,
                    "artifact_path": str(artifact_path),
                    "extract_mode": extract_mode,
                },
            )
            status: RunLifecycleStatus = "processed"
        else:
            fallback_text = " ".join(part for part in (meeting.title, source_url or "") if part).strip()
            if not fallback_text:
                raise LocalPipelineError(
                    stage="extract",
                    message="Unable to extract meeting text from artifact or metadata fallback.",
                    operator_hint="Run fetch-latest again and ensure artifact storage is writable.",
                )
            payload = _ExtractedPayload(
                text=fallback_text,
                artifact_id=f"artifact-local-meeting:{meeting.meeting_id}",
                section_ref="meeting.metadata",
                metadata={
                    "source_id": source_id,
                    "source_type": source_type,
                    "artifact_path": None,
                    "extract_mode": "metadata_fallback",
                },
            )
            status = "limited_confidence"

        finished_at = _now_iso_utc()
        self._upsert_stage_outcome(
            run_id=run_id,
            city_id=city_id,
            meeting_id=meeting.meeting_id,
            stage_name="extract",
            status=status,
            metadata=payload.metadata,
            started_at=started_at,
            finished_at=finished_at,
        )
        emit_multi_document_stage_event(
            event_name="pipeline_stage_finished",
            stage="extract",
            outcome="success",
            status=status,
            city_id=city_id,
            meeting_id=meeting.meeting_id,
            run_id=run_id,
            source_id=source_id or "source-unknown",
            source_type=source_type,
            artifact_id=payload.artifact_id,
            extra_fields={
                "extract_mode": str(payload.metadata.get("extract_mode") or "unknown"),
            },
        )
        emit_source_stage_outcome(
            self._metric_emitter,
            stage="extract",
            outcome="success",
            city_id=city_id,
            source_type=source_type,
            status=status,
        )
        return payload, status

    def _summarize_stage(
        self,
        *,
        run_id: str,
        city_id: str,
        meeting_id: str,
        source_id: str | None,
        source_type: str | None,
        extracted: _ExtractedPayload,
        material_context: _MeetingMaterialContext,
        rollout_config: QualityGateRolloutConfig,
        llm_config: LlmProviderConfig,
    ) -> tuple[_SummarizePayload, str]:
        started_at = _now_iso_utc()
        provider_used = "deterministic"
        fallback_reason: str | None = None
        compose_input = assemble_summarize_compose_input(
            connection=self._connection,
            meeting_id=meeting_id,
            fallback_source_type=source_type,
            fallback_text=extracted.text,
        )
        emit_multi_document_stage_event(
            event_name="pipeline_stage_finished",
            stage="compose",
            outcome="success",
            status="processed",
            city_id=city_id,
            meeting_id=meeting_id,
            run_id=run_id,
            source_id=source_id or "source-unknown",
            source_type=source_type,
            artifact_id=extracted.artifact_id,
            extra_fields={
                "coverage_ratio": compose_input.source_coverage.coverage_ratio,
                "available_source_types": list(compose_input.source_coverage.available_source_types),
                "missing_source_types": list(compose_input.source_coverage.missing_source_types),
            },
        )
        emit_source_stage_outcome(
            self._metric_emitter,
            stage="compose",
            outcome="success",
            city_id=city_id,
            source_type="bundle",
            status="processed",
        )
        emit_source_coverage_ratio(
            self._metric_emitter,
            city_id=city_id,
            coverage_ratio=compose_input.source_coverage.coverage_ratio,
        )
        authority_policy = _evaluate_authority_policy(compose_input=compose_input)
        summarize_text = authority_policy.summarize_text
        compose_section_ref = "compose.multi_document"

        provider_requested = llm_config.normalized_provider
        common_kwargs = {
            "text": summarize_text,
            "artifact_id": extracted.artifact_id,
            "section_ref": compose_section_ref,
            "compose_input": compose_input,
            "material_context": material_context,
            "authority_policy": authority_policy,
            "topic_hardening_enabled": rollout_config.behavior_flags.topic_hardening_enabled,
            "specificity_retention_enabled": rollout_config.behavior_flags.specificity_retention_enabled,
            "evidence_projection_enabled": rollout_config.behavior_flags.evidence_projection_enabled,
        }

        if provider_requested == "ollama":
            try:
                output = _summarize_with_ollama(
                    **common_kwargs,
                    endpoint=(llm_config.endpoint or _DEFAULT_OLLAMA_ENDPOINT),
                    model=(llm_config.model or _DEFAULT_OLLAMA_MODEL),
                    timeout_seconds=max(1.0, llm_config.timeout_seconds),
                )
                provider_used = "ollama"
                status = "processed"
            except Exception as exc:
                output = _deterministic_summarize(
                    **common_kwargs,
                )
                provider_used = "deterministic_fallback"
                fallback_reason = f"{type(exc).__name__}: {exc}"
                status = "limited_confidence"
        elif provider_requested == "openai":
            try:
                output = _summarize_with_openai_chat_completion(
                    **common_kwargs,
                    endpoint=(llm_config.endpoint or _DEFAULT_OPENAI_ENDPOINT),
                    model=(llm_config.model or _DEFAULT_OPENAI_MODEL),
                    timeout_seconds=max(1.0, llm_config.timeout_seconds),
                    api_key=llm_config.api_key,
                )
                provider_used = "openai"
                status = "processed"
            except Exception as exc:
                output = _deterministic_summarize(
                    **common_kwargs,
                )
                provider_used = "deterministic_fallback"
                fallback_reason = f"{type(exc).__name__}: {exc}"
                status = "limited_confidence"
        elif provider_requested == "none":
            output = _deterministic_summarize(
                **common_kwargs,
            )
            status = "processed"
        else:
            raise LocalPipelineError(
                stage="summarize",
                message=f"Unsupported llm provider: {provider_requested}",
                operator_hint="Use --llm-provider none|ollama|openai.",
            )

        finished_at = _now_iso_utc()
        metadata: dict[str, object] = {
            "source_id": source_id,
            "source_type": source_type,
            "provider_used": provider_used,
            "claim_count": len(output.claims),
            "compose": compose_input.to_stage_metadata_payload(),
            "authority_policy": authority_policy.to_metadata_payload(),
        }
        if output.structured_relevance is not None:
            structured_relevance_payload = output.structured_relevance.to_payload()
            if structured_relevance_payload:
                metadata["structured_relevance"] = structured_relevance_payload
        if fallback_reason is not None:
            metadata["fallback_reason"] = fallback_reason

        self._upsert_stage_outcome(
            run_id=run_id,
            city_id=city_id,
            meeting_id=meeting_id,
            stage_name="summarize",
            status=status,
            metadata=metadata,
            started_at=started_at,
            finished_at=finished_at,
        )
        emit_multi_document_stage_event(
            event_name="pipeline_stage_finished",
            stage="summarize",
            outcome="success",
            status=status,
            city_id=city_id,
            meeting_id=meeting_id,
            run_id=run_id,
            source_id=source_id or "source-unknown",
            source_type=source_type,
            artifact_id=extracted.artifact_id,
            extra_fields={
                "provider_used": provider_used,
                "claim_count": len(output.claims),
            },
        )
        _, citation_precision_ratio = _summarization_pointer_metrics(output=output)
        emit_citation_precision_ratio(
            self._metric_emitter,
            city_id=city_id,
            citation_precision_ratio=citation_precision_ratio,
        )
        return _SummarizePayload(
            output=output,
            provider_requested=provider_requested,
            provider_used=provider_used,
            fallback_reason=fallback_reason,
            authority_policy=authority_policy,
        ), status

    def _publish_stage(
        self,
        *,
        run_id: str,
        city_id: str,
        source_id: str | None,
        source_type: str | None,
        artifact_id: str,
        meeting_id: str,
        output: SummarizationOutput,
        source_text: str,
        material_context: _MeetingMaterialContext,
        authority_policy: _AuthorityPolicyResult,
        extract_status: str,
        summarize_status: str,
        summarize_fallback_used: bool,
        rollout_config: QualityGateRolloutConfig,
    ) -> dict[str, object]:
        started_at = _now_iso_utc()
        publish_outcome_id = f"outcome-publish-{run_id}-{meeting_id}"

        shadow_diagnostics = evaluate_shadow_gates(
            run_id=run_id,
            city_id=city_id,
            meeting_id=meeting_id,
            source_id=source_id,
            source_type=source_type,
            config=rollout_config,
            source_text=source_text,
            output=output,
            summarize_status=summarize_status,
            extract_status=extract_status,
            summarize_fallback_used=summarize_fallback_used,
            document_aware_gate_input=_build_document_aware_gate_input(
                output=output,
                authority_policy=authority_policy,
            ),
        )
        append_shadow_diagnostics_artifact(
            artifact_path=rollout_config.diagnostics_artifact_path,
            diagnostics=shadow_diagnostics,
        )
        promotion_status = compute_promotion_status(
            connection=self._connection,
            environment=rollout_config.environment,
            cohort=rollout_config.cohort,
            required_consecutive_green_runs=2,
            current_run_diagnostics=shadow_diagnostics,
        )
        enforcement_outcome = decide_enforcement_outcome(
            config=rollout_config,
            diagnostics=shadow_diagnostics,
            promotion_status=promotion_status,
        )
        rollout_metadata = build_quality_gate_rollout_metadata(
            config=rollout_config,
            diagnostics=shadow_diagnostics,
            promotion_status=promotion_status,
            enforcement_outcome=enforcement_outcome,
        )
        append_promotion_artifact(
            artifact_path=(rollout_config.promotion_artifact_path if rollout_config.mode == "report_only" else None),
            config=rollout_config,
            evaluated_at_run_id=run_id,
            promotion_status=promotion_status,
        )

        self._upsert_stage_outcome(
            run_id=run_id,
            city_id=city_id,
            meeting_id=meeting_id,
            stage_name="publish",
            status="pending",
            metadata={
                "source_id": source_id,
                "publication_id": None,
                "quality_gate_rollout": rollout_metadata,
            },
            started_at=started_at,
            finished_at=None,
        )

        if enforcement_outcome.decision == "enforce_block":
            finished_at = _now_iso_utc()
            metadata = {
                "source_id": source_id,
                "publication_id": None,
                "quality_gate_reason_codes": [
                    "quality_gate_publish_blocked",
                    *list(enforcement_outcome.reason_codes),
                ],
                "quality_gate_rollout": rollout_metadata,
                "authority_policy": authority_policy.to_metadata_payload(),
            }
            self._upsert_stage_outcome(
                run_id=run_id,
                city_id=city_id,
                meeting_id=meeting_id,
                stage_name="publish",
                status="limited_confidence",
                metadata=metadata,
                started_at=started_at,
                finished_at=finished_at,
            )
            return {
                "stage": "publish",
                "status": "limited_confidence",
                "metadata": metadata,
            }

        try:
            enforcement_override = None
            if enforcement_outcome.decision == "enforce_downgrade":
                enforcement_override = QualityGateEnforcementOverride(
                    publication_status="limited_confidence",
                    confidence_label="limited_confidence",
                    reason_codes=("quality_gate_publish_downgraded", *enforcement_outcome.reason_codes),
                )
            if authority_policy.publication_status == "limited_confidence":
                if enforcement_override is None:
                    enforcement_override = QualityGateEnforcementOverride(
                        publication_status="limited_confidence",
                        confidence_label="limited_confidence",
                        reason_codes=authority_policy.reason_codes,
                    )
                else:
                    enforcement_override = QualityGateEnforcementOverride(
                        publication_status="limited_confidence",
                        confidence_label="limited_confidence",
                        reason_codes=(*enforcement_override.reason_codes, *authority_policy.reason_codes),
                    )

            publication_result = publish_summarization_output(
                repository=MeetingSummaryRepository(self._connection),
                publication_id=f"pub-local-{meeting_id}-{run_id[-8:]}",
                meeting_id=meeting_id,
                processing_run_id=run_id,
                publish_stage_outcome_id=publish_outcome_id,
                version_no=self._next_publication_version(meeting_id=meeting_id),
                base_confidence_label="high",
                output=output,
                published_at=_now_iso_utc(),
                city_id=city_id,
                enforcement_override=enforcement_override,
            )
        except Exception as exc:
            finished_at = _now_iso_utc()
            self._upsert_stage_outcome(
                run_id=run_id,
                city_id=city_id,
                meeting_id=meeting_id,
                stage_name="publish",
                status="failed",
                metadata={
                    "source_id": source_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "quality_gate_rollout": rollout_metadata,
                },
                started_at=started_at,
                finished_at=finished_at,
            )
            emit_multi_document_stage_event(
                event_name="pipeline_stage_error",
                stage="publish",
                outcome="failure",
                status="failed",
                city_id=city_id,
                meeting_id=meeting_id,
                run_id=run_id,
                source_id=source_id or "source-unknown",
                source_type=source_type,
                artifact_id=artifact_id,
                extra_fields={
                    "error_code": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            emit_source_stage_outcome(
                self._metric_emitter,
                stage="publish",
                outcome="failure",
                city_id=city_id,
                source_type="bundle",
                status="failed",
            )
            raise LocalPipelineError(
                stage="publish",
                message=f"Failed to publish summarization output: {exc}",
                operator_hint="Inspect summary publication integrity and rerun process-latest.",
            ) from exc

        finished_at = _now_iso_utc()
        self._upsert_stage_outcome(
            run_id=run_id,
            city_id=city_id,
            meeting_id=meeting_id,
            stage_name="publish",
            status=publication_result.publication.publication_status,
            metadata={
                "source_id": source_id,
                "publication_id": publication_result.publication.id,
                "quality_gate_reason_codes": list(publication_result.quality_gate.reason_codes),
                "quality_gate_rollout": rollout_metadata,
                "authority_policy": authority_policy.to_metadata_payload(),
                **(
                    {"structured_relevance": structured_relevance_payload}
                    if (
                        output.structured_relevance is not None
                        and (structured_relevance_payload := output.structured_relevance.to_payload())
                    )
                    else {}
                ),
            },
            started_at=started_at,
            finished_at=finished_at,
        )
        emit_multi_document_stage_event(
            event_name="pipeline_stage_finished",
            stage="publish",
            outcome="success",
            status=publication_result.publication.publication_status,
            city_id=city_id,
            meeting_id=meeting_id,
            run_id=run_id,
            source_id=source_id or "source-unknown",
            source_type=source_type,
            artifact_id=artifact_id,
            extra_fields={
                "publication_id": publication_result.publication.id,
                "quality_gate_reason_codes": list(publication_result.quality_gate.reason_codes),
            },
        )
        return {
            "stage": "publish",
            "status": publication_result.publication.publication_status,
            "metadata": {
                "source_id": source_id,
                "publication_id": publication_result.publication.id,
                "quality_gate_reason_codes": list(publication_result.quality_gate.reason_codes),
                "quality_gate_rollout": rollout_metadata,
                "authority_policy": authority_policy.to_metadata_payload(),
                **(
                    {"structured_relevance": structured_relevance_payload}
                    if (
                        output.structured_relevance is not None
                        and (structured_relevance_payload := output.structured_relevance.to_payload())
                    )
                    else {}
                ),
            },
        }

    def _upsert_stage_outcome(
        self,
        *,
        run_id: str,
        city_id: str,
        meeting_id: str,
        stage_name: str,
        status: RunLifecycleStatus,
        metadata: dict[str, object],
        started_at: str | None,
        finished_at: str | None,
    ) -> None:
        self._run_repository.upsert_stage_outcome(
            outcome_id=f"outcome-{stage_name}-{run_id}-{meeting_id}",
            run_id=run_id,
            city_id=city_id,
            meeting_id=meeting_id,
            stage_name=stage_name,
            status=status,
            metadata_json=json.dumps(metadata, sort_keys=True, separators=(",", ":")),
            started_at=started_at,
            finished_at=finished_at,
        )

    def _next_publication_version(self, *, meeting_id: str) -> int:
        row = self._connection.execute(
            """
            SELECT COALESCE(MAX(version_no), 0)
            FROM summary_publications
            WHERE meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()
        if row is None:
            return 1
        return int(row[0]) + 1


def _now_iso_utc() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _build_document_aware_gate_input(
    *,
    output: SummarizationOutput,
    authority_policy: _AuthorityPolicyResult,
) -> DocumentAwareGateInput:
    citation_pointer_count, citation_precision_ratio = _summarization_pointer_metrics(output=output)
    return DocumentAwareGateInput(
        authority_outcome=authority_policy.authority_outcome,
        authority_reason_codes=authority_policy.reason_codes,
        authority_conflict_count=len(authority_policy.conflicts),
        source_statuses=dict(authority_policy.source_statuses),
        authoritative_locator_precision=authority_policy.authoritative_locator_precision,
        citation_precision_ratio=citation_precision_ratio,
        citation_pointer_count=citation_pointer_count,
    )


def _summarization_pointer_metrics(*, output: SummarizationOutput) -> tuple[int, float | None]:
    pointers = _list_unique_evidence_pointers(output=output)
    pointer_count = len(pointers)
    if pointer_count == 0:
        return 0, None

    precise_count = sum(1 for pointer in pointers if _pointer_is_precise(pointer))
    return pointer_count, precise_count / float(pointer_count)


def _list_unique_evidence_pointers(*, output: SummarizationOutput) -> tuple[ClaimEvidencePointer, ...]:
    seen: set[tuple[str, str | None, int | None, int | None, str]] = set()
    unique: list[ClaimEvidencePointer] = []
    for claim in output.claims:
        for pointer in claim.evidence:
            key = (pointer.artifact_id, pointer.section_ref, pointer.char_start, pointer.char_end, pointer.excerpt)
            if key in seen:
                continue
            seen.add(key)
            unique.append(pointer)
    return tuple(unique)


def _pointer_is_precise(pointer: ClaimEvidencePointer) -> bool:
    if pointer.precision is not None:
        return pointer.precision in {"offset", "span", "section"}
    if pointer.char_start is not None and pointer.char_end is not None:
        return True
    section_ref = (pointer.section_ref or "").strip().lower()
    return section_ref not in {"", "artifact.html", "artifact.pdf", "meeting.metadata"}


def _extract_text_from_html(html_text: str) -> str:
    parser = _TextCollector()
    parser.feed(html_text)
    return parser.as_text()


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception:
        return ""

    parts: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        normalized = " ".join(page_text.split())
        if normalized:
            parts.append(normalized)
    return " ".join(parts).strip()


def _extract_text_from_artifact_bytes(raw_bytes: bytes, *, artifact_path: Path) -> tuple[str, str]:
    suffix = artifact_path.suffix.lower()
    if suffix == ".pdf" or raw_bytes.startswith(b"%PDF"):
        extracted_pdf = _extract_text_from_pdf_bytes(raw_bytes)
        if extracted_pdf:
            return extracted_pdf, "pdf_artifact"
        return "", "pdf_artifact"

    raw_text = raw_bytes.decode("utf-8", errors="replace")
    return _extract_text_from_artifact_content(raw_text)


def _extract_text_from_artifact_content(raw_text: str) -> tuple[str, str]:
    normalized_raw = raw_text.strip()
    if normalized_raw.startswith("{"):
        try:
            parsed = json.loads(normalized_raw)
        except json.JSONDecodeError:
            return _extract_text_from_html(raw_text), "html_artifact"
        if isinstance(parsed, dict) and parsed.get("source") == "civicclerk_events":
            return _extract_text_from_civicclerk_payload(parsed), "civicclerk_json_artifact"
    return _extract_text_from_html(raw_text), "html_artifact"


def _extract_text_from_civicclerk_payload(payload: dict[str, object]) -> str:
    event_name = str(payload.get("selected_event_name") or "City Council Meeting")
    event_date = str(payload.get("selected_event_date") or "unknown date")
    selected_file = payload.get("selected_file")

    file_type = "document"
    file_name = "published file"
    publish_on = ""
    if isinstance(selected_file, dict):
        file_type = str(selected_file.get("type") or file_type)
        file_name = str(selected_file.get("name") or file_name)
        publish_on = str(selected_file.get("publishOn") or "").strip()

    published_phrase = f" It is published on {publish_on}." if publish_on else ""
    return (
        f"{event_name} on {event_date}. "
        f"The published document is a {file_type} titled {file_name}.{published_phrase}"
    ).strip()


def _find_artifact_path(*, city_id: str, meeting_id: str) -> Path | None:
    artifact_root = Path(os.getenv("COUNCILSENSE_LOCAL_ARTIFACT_ROOT", _DEFAULT_ARTIFACT_ROOT))
    city_dir = artifact_root / city_id
    if not city_dir.exists():
        return None

    meeting_fingerprint_prefix = meeting_id.removeprefix("meeting-").lower()
    if not meeting_fingerprint_prefix:
        return None

    candidates = sorted(path for path in city_dir.glob(f"**/{meeting_fingerprint_prefix}*.*") if path.is_file())
    if not candidates:
        return None
    return candidates[-1]


def _deterministic_summarize(
    *,
    text: str,
    artifact_id: str,
    section_ref: str,
    compose_input: SummarizeComposeInput | None,
    material_context: _MeetingMaterialContext,
    authority_policy: _AuthorityPolicyResult,
    topic_hardening_enabled: bool,
    specificity_retention_enabled: bool,
    evidence_projection_enabled: bool,
) -> SummarizationOutput:
    normalized = _normalize_generated_text(text)
    focused_text = _focus_source_text(normalized)
    summary = _build_grounded_summary(focused_text)
    key_decisions, key_actions, notable_topics = _derive_grounded_sections(
        focused_text,
        topic_hardening_enabled=topic_hardening_enabled,
    )
    if specificity_retention_enabled:
        summary, key_decisions, key_actions = _enforce_anchor_carry_through(
            source_text=focused_text,
            summary=summary,
            key_decisions=key_decisions,
            key_actions=key_actions,
        )
    summary, key_decisions, key_actions, notable_topics = _apply_material_context(
        source_text=focused_text,
        summary=summary,
        key_decisions=key_decisions,
        key_actions=key_actions,
        notable_topics=notable_topics,
        material_context=material_context,
        authority_policy=authority_policy,
    )
    claim_text = (key_decisions[0] if key_decisions else summary)[:180] if summary else "Meeting source text unavailable."
    excerpt_source = focused_text or normalized
    claims = _build_claims_from_findings(
        key_decisions=key_decisions,
        key_actions=key_actions,
        source_text=excerpt_source,
        artifact_id=artifact_id,
        section_ref=section_ref,
        compose_input=compose_input,
        fallback_claim=claim_text,
        evidence_projection_enabled=evidence_projection_enabled,
    )
    structured_relevance = _synthesize_structured_relevance(
        source_text=excerpt_source,
        artifact_id=artifact_id,
        section_ref=section_ref,
        compose_input=compose_input,
        authority_policy=authority_policy,
    )
    summary, key_decisions, key_actions = _apply_structured_relevance_carry_through(
        summary=summary,
        key_decisions=key_decisions,
        key_actions=key_actions,
        structured_relevance=structured_relevance,
        authority_policy=authority_policy,
    )
    notable_topics = _supplement_notable_topics(
        notable_topics=notable_topics,
        summary=summary,
        key_decisions=key_decisions,
        key_actions=key_actions,
        structured_relevance=structured_relevance,
    )

    return SummarizationOutput.from_sections(
        summary=summary,
        key_decisions=key_decisions,
        key_actions=key_actions,
        notable_topics=notable_topics,
        claims=claims,
        structured_relevance=structured_relevance,
    )


def _summarize_with_ollama(
    *,
    text: str,
    artifact_id: str,
    section_ref: str,
    compose_input: SummarizeComposeInput | None,
    material_context: _MeetingMaterialContext,
    authority_policy: _AuthorityPolicyResult,
    topic_hardening_enabled: bool,
    specificity_retention_enabled: bool,
    evidence_projection_enabled: bool,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> SummarizationOutput:
    prompt = _build_llm_summary_prompt(
        text=text,
        material_context=material_context,
        authority_policy=authority_policy,
    )
    return _request_ollama_summary(
        prompt=prompt,
        source_text=text,
        artifact_id=artifact_id,
        section_ref=section_ref,
        compose_input=compose_input,
        material_context=material_context,
        authority_policy=authority_policy,
        topic_hardening_enabled=topic_hardening_enabled,
        specificity_retention_enabled=specificity_retention_enabled,
        evidence_projection_enabled=evidence_projection_enabled,
        endpoint=endpoint,
        model=model,
        timeout_seconds=timeout_seconds,
    )


def _request_ollama_summary(
    *,
    prompt: str,
    source_text: str,
    artifact_id: str,
    section_ref: str,
    compose_input: SummarizeComposeInput | None,
    material_context: _MeetingMaterialContext,
    authority_policy: _AuthorityPolicyResult,
    topic_hardening_enabled: bool,
    specificity_retention_enabled: bool,
    evidence_projection_enabled: bool,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> SummarizationOutput:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    request = Request(
        f"{endpoint.rstrip('/')}/api/generate",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (TimeoutError, URLError, HTTPError) as exc:
        raise RuntimeError(f"ollama request failed: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ollama response payload was not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("ollama response payload was not an object")

    response_text = parsed.get("response")
    if not isinstance(response_text, str) or not response_text.strip():
        raise RuntimeError("ollama response missing non-empty 'response' field")

    return _materialize_llm_summary_output(
        response_text=response_text,
        source_text=source_text,
        artifact_id=artifact_id,
        section_ref=section_ref,
        compose_input=compose_input,
        material_context=material_context,
        authority_policy=authority_policy,
        topic_hardening_enabled=topic_hardening_enabled,
        specificity_retention_enabled=specificity_retention_enabled,
        evidence_projection_enabled=evidence_projection_enabled,
    )


def _summarize_with_openai_chat_completion(
    *,
    text: str,
    artifact_id: str,
    section_ref: str,
    compose_input: SummarizeComposeInput | None,
    material_context: _MeetingMaterialContext,
    authority_policy: _AuthorityPolicyResult,
    topic_hardening_enabled: bool,
    specificity_retention_enabled: bool,
    evidence_projection_enabled: bool,
    endpoint: str,
    model: str,
    timeout_seconds: float,
    api_key: str | None,
) -> SummarizationOutput:
    if api_key is None or not api_key.strip():
        raise RuntimeError("OpenAI API key is not configured")

    prompt = _build_llm_summary_prompt(
        text=text,
        material_context=material_context,
        authority_policy=authority_policy,
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    request = Request(
        f"{endpoint.rstrip('/')}/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (TimeoutError, URLError, HTTPError) as exc:
        raise RuntimeError(f"openai request failed: {exc}") from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("openai response payload was not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("openai response payload was not an object")

    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("openai response missing non-empty 'choices' field")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("openai response choice was not an object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("openai response missing message payload")
    response_text = _extract_chat_message_content(message.get("content"))
    if not response_text:
        raise RuntimeError("openai response missing non-empty message content")

    return _materialize_llm_summary_output(
        response_text=response_text,
        source_text=text,
        artifact_id=artifact_id,
        section_ref=section_ref,
        compose_input=compose_input,
        material_context=material_context,
        authority_policy=authority_policy,
        topic_hardening_enabled=topic_hardening_enabled,
        specificity_retention_enabled=specificity_retention_enabled,
        evidence_projection_enabled=evidence_projection_enabled,
    )


def _build_llm_summary_prompt(
    *,
    text: str,
    material_context: _MeetingMaterialContext,
    authority_policy: _AuthorityPolicyResult,
) -> str:
    cleaned_source = _normalize_generated_text(text)
    focused_source = _focus_source_text(cleaned_source)
    preview_instruction = (
        "This source is agenda-only or packet-only; describe scheduled items and explicitly state that no decisions or completed actions are recorded yet because minutes are unavailable. "
        if authority_policy.preview_only or material_context.is_preview_only
        else ""
    )
    return (
        "You are summarizing local government meeting materials. "
        "Use only facts present in the provided meeting text. "
        "Prioritize what actually happened: decisions made, actions assigned, policy or project impacts. "
        "Avoid procedural meeting operations unless they materially change an outcome (attendance, roll call, call to order, adjournment, schedule mechanics). "
        + preview_instruction
        + "Do not include chain-of-thought, reasoning traces, or meta commentary. "
        + "Return ONLY valid JSON with keys: summary, claim. "
        + "summary must be 2-3 sentences and claim must be one specific sentence grounded in the meeting text.\n\n"
        + f"Meeting text:\n{(focused_source or cleaned_source)[:6000]}"
    )


def _extract_chat_message_content(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts).strip()


def _materialize_llm_summary_output(
    *,
    response_text: str,
    source_text: str,
    artifact_id: str,
    section_ref: str,
    compose_input: SummarizeComposeInput | None,
    material_context: _MeetingMaterialContext,
    authority_policy: _AuthorityPolicyResult,
    topic_hardening_enabled: bool,
    specificity_retention_enabled: bool,
    evidence_projection_enabled: bool,
) -> SummarizationOutput:
    cleaned_source = _normalize_generated_text(source_text)
    focused_source = _focus_source_text(cleaned_source)

    normalized_response = _normalize_generated_text(unescape(response_text))
    parsed_json = _extract_json_object(normalized_response)

    summary_text = _normalize_generated_text(str(parsed_json.get("summary") or ""))
    claim_text = _normalize_generated_text(str(parsed_json.get("claim") or ""))
    if not summary_text:
        summary_text = _build_grounded_summary(focused_source or cleaned_source)
    if not claim_text:
        derived_decisions, _, _ = _derive_grounded_sections(
            focused_source or cleaned_source,
            topic_hardening_enabled=topic_hardening_enabled,
        )
        claim_text = (derived_decisions[0] if derived_decisions else summary_text)[:180]

    excerpt_source = focused_source or cleaned_source
    key_decisions, key_actions, notable_topics = _derive_grounded_sections(
        excerpt_source,
        topic_hardening_enabled=topic_hardening_enabled,
    )
    if specificity_retention_enabled:
        summary_text, key_decisions, key_actions = _enforce_anchor_carry_through(
            source_text=excerpt_source,
            summary=summary_text,
            key_decisions=key_decisions,
            key_actions=key_actions,
        )
    summary_text, key_decisions, key_actions, notable_topics = _apply_material_context(
        source_text=excerpt_source,
        summary=summary_text,
        key_decisions=key_decisions,
        key_actions=key_actions,
        notable_topics=notable_topics,
        material_context=material_context,
        authority_policy=authority_policy,
    )
    claims = _build_claims_from_findings(
        key_decisions=key_decisions,
        key_actions=key_actions,
        source_text=excerpt_source,
        artifact_id=artifact_id,
        section_ref=section_ref,
        compose_input=compose_input,
        fallback_claim=claim_text,
        evidence_projection_enabled=evidence_projection_enabled,
    )
    structured_relevance = _synthesize_structured_relevance(
        source_text=excerpt_source,
        artifact_id=artifact_id,
        section_ref=section_ref,
        compose_input=compose_input,
        authority_policy=authority_policy,
    )
    summary_text, key_decisions, key_actions = _apply_structured_relevance_carry_through(
        summary=summary_text,
        key_decisions=key_decisions,
        key_actions=key_actions,
        structured_relevance=structured_relevance,
        authority_policy=authority_policy,
    )
    notable_topics = _supplement_notable_topics(
        notable_topics=notable_topics,
        summary=summary_text,
        key_decisions=key_decisions,
        key_actions=key_actions,
        structured_relevance=structured_relevance,
    )

    return SummarizationOutput.from_sections(
        summary=summary_text,
        key_decisions=key_decisions,
        key_actions=key_actions,
        notable_topics=notable_topics,
        claims=claims,
        structured_relevance=structured_relevance,
    )


def _strip_think_blocks(value: str) -> str:
    return _THINK_BLOCK_RE.sub(" ", value)


def _normalize_generated_text(value: str) -> str:
    without_think = _strip_think_blocks(value)
    without_code_fences = without_think.replace("```json", " ").replace("```", " ")
    return " ".join(without_code_fences.split())


def _extract_json_object(value: str) -> dict[str, object]:
    match = _JSON_OBJECT_RE.search(value)
    if match is None:
        raise RuntimeError("ollama response did not include a JSON object")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise RuntimeError("ollama JSON payload was invalid") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("ollama JSON payload was not an object")
    return parsed


def _derive_grounded_sections(
    text: str,
    *,
    topic_hardening_enabled: bool = True,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    normalized = _normalize_generated_text(text)
    if not normalized:
        return (("No decision text found in source.",), ("No action text found in source.",), ("meeting",))

    sentences = _split_sentences(normalized)
    if not sentences:
        sentences = [normalized]

    content_sentences = [sentence for sentence in sentences if not _is_low_signal_sentence(sentence)]
    if not content_sentences:
        content_sentences = sentences

    decision_keywords = (
        "approve",
        "approved",
        "adopt",
        "resolution",
        "ordinance",
        "vote",
        "passed",
        "denied",
        "consent agenda",
        "authorized",
        "ratified",
    )
    action_keywords = (
        "direct",
        "directed",
        "schedule",
        "scheduled",
        "submit",
        "prepare",
        "continue",
        "follow up",
        "public hearing",
        "assigned",
        "tabled",
        "determined",
        "moved",
        "seconded",
        "approved",
    )

    decisive_decision_keywords = (
        "approve",
        "approved",
        "adopt",
        "adopted",
        "authorized",
        "ratified",
        "denied",
        "motion carried",
        "moved to",
        "passed",
    )
    primary_action_keywords = (
        "direct",
        "directed",
        "schedule",
        "scheduled",
        "submit",
        "prepare",
        "continue",
        "follow up",
        "public hearing",
        "assigned",
        "tabled",
        "determined",
    )

    decision_candidates = [
        _normalize_decision_sentence(s)
        for s in content_sentences
        if any(keyword in s.lower() for keyword in decisive_decision_keywords)
    ]
    if not decision_candidates:
        decision_candidates = [
            _normalize_decision_sentence(s)
            for s in content_sentences
            if any(keyword in s.lower() for keyword in decision_keywords)
        ]

    action_candidates = [
        _normalize_action_sentence(s)
        for s in content_sentences
        if any(keyword in s.lower() for keyword in primary_action_keywords)
    ]
    if not action_candidates:
        action_candidates = [
            _normalize_action_sentence(s)
            for s in content_sentences
            if any(keyword in s.lower() for keyword in action_keywords)
        ]

    decision_final = [s for s in decision_candidates if s and not _is_low_value_outcome(s)]
    action_final = [s for s in action_candidates if s and not _is_low_value_outcome(s)]

    key_decisions = tuple((decision_final or [_normalize_decision_sentence(s) for s in content_sentences])[:2])
    key_actions = tuple((action_final or [_normalize_action_sentence(s) for s in content_sentences])[:2])

    if topic_hardening_enabled:
        notable_topics = _derive_notable_topics(key_decisions=key_decisions, key_actions=key_actions)
    else:
        notable_topics = _derive_basic_topics(key_decisions=key_decisions, key_actions=key_actions)

    return key_decisions, key_actions, notable_topics


def _evaluate_authority_policy(*, compose_input: SummarizeComposeInput) -> _AuthorityPolicyResult:
    source_by_type = {source.source_type: source for source in compose_input.sources}
    source_statuses = dict(compose_input.source_coverage.statuses)
    minutes_source = _select_available_source(source_by_type.get("minutes"))
    agenda_source = _select_available_source(source_by_type.get("agenda"))
    packet_source = _select_available_source(source_by_type.get("packet"))
    supplemental_sources = tuple(source for source in (agenda_source, packet_source) if source is not None)

    if minutes_source is not None:
        conflicts = _detect_authoritative_conflicts(
            authoritative_source=minutes_source,
            supporting_sources=supplemental_sources,
        )
        reason_codes: list[str] = []
        authority_outcome = "minutes_authoritative"
        publication_status = "processed"

        if not supplemental_sources:
            authority_outcome = "supplemental_coverage_missing"
            publication_status = "limited_confidence"
            reason_codes.append("supplemental_sources_missing")

        if minutes_source.locator_precision == "weak":
            if authority_outcome == "minutes_authoritative":
                authority_outcome = "minutes_authoritative_weak_precision"
            publication_status = "limited_confidence"
            reason_codes.append("weak_evidence_precision")

        return _build_authority_policy_result(
            authority_outcome=authority_outcome,
            publication_status=publication_status,
            reason_codes=tuple(reason_codes),
            summarize_text=minutes_source.text,
            authoritative_source_type="minutes",
            authoritative_locator_precision=minutes_source.locator_precision,
            outcome_source_types=("minutes",),
            source_statuses=source_statuses,
            preview_only=False,
            conflicts=conflicts,
        )

    supplemental_available = tuple(source for source in supplemental_sources if source is not None)
    if supplemental_available:
        conflicts = _detect_supplemental_conflicts(sources=supplemental_available)
        if conflicts:
            return _build_authority_policy_result(
                authority_outcome="unresolved_conflict",
                publication_status="limited_confidence",
                reason_codes=("missing_authoritative_minutes", "unresolved_source_conflict"),
                summarize_text=_compose_authority_text(supplemental_available),
                authoritative_source_type=None,
                authoritative_locator_precision=None,
                outcome_source_types=tuple(source.source_type for source in supplemental_available),
                source_statuses=source_statuses,
                preview_only=True,
                conflicts=conflicts,
            )

        has_agenda_preview = agenda_source is not None
        return _build_authority_policy_result(
            authority_outcome=("agenda_preview_only" if has_agenda_preview else "missing_authoritative_minutes"),
            publication_status="limited_confidence",
            reason_codes=(
                ("agenda_preview_only", "missing_authoritative_minutes")
                if has_agenda_preview
                else ("missing_authoritative_minutes",)
            ),
            summarize_text=_compose_authority_text(supplemental_available),
            authoritative_source_type=None,
            authoritative_locator_precision=None,
            outcome_source_types=tuple(source.source_type for source in supplemental_available),
            source_statuses=source_statuses,
            preview_only=True,
            conflicts=(),
        )

    return _build_authority_policy_result(
        authority_outcome="missing_authoritative_minutes",
        publication_status="limited_confidence",
        reason_codes=("missing_authoritative_minutes",),
        summarize_text=compose_input.composed_text,
        authoritative_source_type=None,
        authoritative_locator_precision=None,
        outcome_source_types=(),
        source_statuses=source_statuses,
        preview_only=False,
        conflicts=(),
    )


def _select_available_source(source: ComposedSourceDocument | None) -> ComposedSourceDocument | None:
    if source is None:
        return None
    if source.coverage_status == "missing":
        return None
    if not source.text.strip():
        return None
    return source


def _compose_authority_text(sources: tuple[ComposedSourceDocument, ...]) -> str:
    chunks = [f"[{source.source_type}] {source.text}" for source in sources if source.text.strip()]
    return "\n\n".join(chunks).strip() or "No source text available."


def _detect_authoritative_conflicts(
    *,
    authoritative_source: ComposedSourceDocument,
    supporting_sources: tuple[ComposedSourceDocument, ...],
) -> tuple[_AuthorityConflictSignal, ...]:
    authoritative_signals = _derive_authority_outcome_signals(source=authoritative_source)
    conflicts: list[_AuthorityConflictSignal] = []
    for supporting_source in supporting_sources:
        supporting_signals = _derive_authority_outcome_signals(source=supporting_source)
        conflict = _find_conflict_signal(
            primary_signals=authoritative_signals,
            secondary_signals=supporting_signals,
            authoritative_source_type=authoritative_source.source_type,
            conflicting_source_type=supporting_source.source_type,
            resolution="authoritative_override",
        )
        if conflict is not None:
            conflicts.append(conflict)
    return tuple(conflicts)


def _detect_supplemental_conflicts(*, sources: tuple[ComposedSourceDocument, ...]) -> tuple[_AuthorityConflictSignal, ...]:
    ordered_sources = sorted(sources, key=lambda item: item.source_type)
    signals_by_source = {source.source_type: _derive_authority_outcome_signals(source=source) for source in ordered_sources}
    conflicts: list[_AuthorityConflictSignal] = []
    for index, left_source in enumerate(ordered_sources):
        for right_source in ordered_sources[index + 1 :]:
            conflict = _find_conflict_signal(
                primary_signals=signals_by_source[left_source.source_type],
                secondary_signals=signals_by_source[right_source.source_type],
                authoritative_source_type=None,
                conflicting_source_type=right_source.source_type,
                resolution="unresolved",
            )
            if conflict is not None:
                conflicts.append(conflict)
    return tuple(conflicts)


def _derive_authority_outcome_signals(*, source: ComposedSourceDocument) -> tuple[_AuthorityOutcomeSignal, ...]:
    focused_text = _focus_source_text(_normalize_generated_text(source.text))
    decisions, actions, _ = _derive_grounded_sections(focused_text, topic_hardening_enabled=False)
    signals: list[_AuthorityOutcomeSignal] = []
    for finding in [*decisions, *actions]:
        normalized = _normalize_generated_text(finding)
        if not normalized:
            continue
        signal = _AuthorityOutcomeSignal(
            source_type=source.source_type,
            finding=normalized,
            subject=_extract_authority_subject(normalized),
            action_class=_classify_authority_action(normalized),
        )
        if signal not in signals:
            signals.append(signal)
        if len(signals) >= 4:
            break
    return tuple(signals)


def _find_conflict_signal(
    *,
    primary_signals: tuple[_AuthorityOutcomeSignal, ...],
    secondary_signals: tuple[_AuthorityOutcomeSignal, ...],
    authoritative_source_type: str | None,
    conflicting_source_type: str,
    resolution: str,
) -> _AuthorityConflictSignal | None:
    for primary in primary_signals:
        for secondary in secondary_signals:
            if not _signals_conflict(primary=primary, secondary=secondary):
                continue
            return _AuthorityConflictSignal(
                authoritative_source_type=authoritative_source_type,
                conflicting_source_type=conflicting_source_type,
                subject=primary.subject or secondary.subject,
                authoritative_action=(primary.action_class if authoritative_source_type is not None else primary.action_class),
                conflicting_action=secondary.action_class,
                authoritative_finding=primary.finding,
                conflicting_finding=secondary.finding,
                resolution=resolution,
            )
    return None


def _signals_conflict(*, primary: _AuthorityOutcomeSignal, secondary: _AuthorityOutcomeSignal) -> bool:
    if primary.subject is None or secondary.subject is None:
        return False
    if primary.subject != secondary.subject:
        return False
    if primary.action_class == secondary.action_class:
        return False
    decisive_actions = {"approve", "continue", "deny"}
    if primary.action_class in decisive_actions and secondary.action_class in decisive_actions:
        return True
    if primary.action_class == "approve" and secondary.action_class in {"hearing", "schedule"}:
        return False
    if secondary.action_class == "approve" and primary.action_class in {"hearing", "schedule"}:
        return False
    return False


def _extract_authority_subject(finding: str) -> str | None:
    lower_finding = finding.lower()
    for pattern in (
        r"\bordinance\s+\d{4}-\d+\b",
        r"\bresolution\s+\d{4}-\d+\b",
        r"\bpurchase agreement\b",
        r"\bpaving contract\b",
        r"\broad closure permit\b",
        r"\bfee schedule\b",
        r"\bbond documents?\b",
    ):
        match = re.search(pattern, lower_finding)
        if match is not None:
            return match.group(0)
    return None


def _classify_authority_action(finding: str) -> str:
    lower_finding = finding.lower()
    if any(
        token in lower_finding
        for token in ("continued", "continue", "continuing", "deferred", "defer", "tabled", "postponed")
    ):
        return "continue"
    if any(token in lower_finding for token in ("denied", "deny", "rejected", "reject")):
        return "deny"
    if any(
        token in lower_finding
        for token in (
            "approved",
            "approve",
            "adopted",
            "adopt",
            "adoption",
            "authorized",
            "authorize",
            "passed",
            "ratified",
            "awarded",
            "awarding",
            "motion carried",
        )
    ):
        return "approve"
    if "public hearing" in lower_finding:
        return "hearing"
    if any(token in lower_finding for token in ("scheduled", "schedule")):
        return "schedule"
    return "other"


def _normalize_document_kind(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == "agenda packet":
        return "packet"
    if normalized in {"minutes", "agenda", "packet"}:
        return normalized
    return None


def _classify_meeting_temporal_status(meeting_date_iso: str | None) -> str | None:
    if not meeting_date_iso:
        return None
    try:
        meeting_date = datetime.fromisoformat(f"{meeting_date_iso}T00:00:00+00:00").date()
    except ValueError:
        return None
    today = datetime.now(tz=UTC).date()
    if meeting_date >= today:
        return "same_day_or_future"
    return "completed"


def _apply_material_context(
    *,
    source_text: str,
    summary: str,
    key_decisions: tuple[str, ...],
    key_actions: tuple[str, ...],
    notable_topics: tuple[str, ...],
    material_context: _MeetingMaterialContext,
    authority_policy: _AuthorityPolicyResult,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if not (material_context.is_preview_only or authority_policy.preview_only):
        return summary, key_decisions, key_actions, notable_topics

    preview_actions = _derive_agenda_preview_actions(source_text)
    preview_summary = _build_agenda_preview_summary(
        preview_actions=preview_actions,
        material_context=material_context,
    )
    preview_topics = _derive_preview_topics(existing=notable_topics)
    return preview_summary, (), (), preview_topics


def _build_agenda_preview_summary(
    *,
    preview_actions: tuple[str, ...],
    material_context: _MeetingMaterialContext,
) -> str:
    lead = (
        "Agenda materials for this meeting preview scheduled items rather than confirmed outcomes. "
        if material_context.is_same_day_or_future
        else "Agenda materials for this meeting list planned items, but published minutes are not available yet. "
    )
    if preview_actions:
        summary = f"{lead}{preview_actions[0]} No decisions or completed actions are recorded yet."
        if len(summary) <= 520:
            return summary
        return summary[:520]
    return f"{lead}No decisions or completed actions are recorded yet because this publication is based on agenda materials."[:520]


def _derive_agenda_preview_actions(source_text: str) -> tuple[str, ...]:
    sentences = _split_sentences(source_text)
    preview_items: list[str] = []
    for sentence in sentences:
        lower_sentence = sentence.lower()
        if lower_sentence.startswith("background:") or " at the february " in lower_sentence:
            continue
        normalized = _normalize_agenda_preview_sentence(sentence)
        if not normalized:
            continue
        lower = normalized.lower()
        if any(
            keyword in lower
            for keyword in ("public hearing", "resolution", "ordinance", "agreement", "site plan", "bond", "appointment")
        ):
            if normalized not in preview_items:
                preview_items.append(normalized)
        if len(preview_items) >= 2:
            break
    return tuple(preview_items[:2])


def _normalize_agenda_preview_sentence(sentence: str) -> str:
    cleaned = _normalize_generated_text(sentence).strip()
    cleaned = re.sub(r"\b[A-Z][A-Z\s/&-]+\s+\d+(?:\.[A-Z])?\.?(?=\s)", "", cleaned)
    cleaned = re.sub(
        r"^(?:BACKGROUND:|RESOLUTIONS\s+\d+(?:\.[A-Z])?\.?|SCHEDULED ITEMS\s+\d+\.?|PUBLIC HEARINGS ONLY\s+\d+(?:\.[A-Z])?\.?)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip(" .:-")
    if not cleaned:
        return ""
    if cleaned.lower().startswith("public hearing/no action taken"):
        cleaned = re.sub(
            r"^public hearing/no action taken\s*-\s*",
            "Agenda includes a public hearing with no action taken regarding ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"^Agenda includes a public hearing with no action taken regarding\s+a public hearing to allow public input regarding\s+",
            "Agenda includes a public hearing with no action taken regarding ",
            cleaned,
            flags=re.IGNORECASE,
        )
    elif re.match(r"^resolution\s*-", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(r"^resolution\s*-\s*", "Agenda includes a resolution on ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"^Agenda includes a resolution on\s+a resolution of [^,]+, [^,]+,\s*",
            "Agenda includes a resolution on ",
            cleaned,
            flags=re.IGNORECASE,
        )
    elif re.match(r"^ordinance(?:/public hearing)?\s*-", cleaned, flags=re.IGNORECASE):
        cleaned = re.sub(
            r"^ordinance(?:/public hearing)?\s*-\s*",
            "Agenda includes an ordinance item on ",
            cleaned,
            flags=re.IGNORECASE,
        )
    elif not cleaned.lower().startswith("agenda includes"):
        cleaned = f"Agenda includes {cleaned[0].lower()}{cleaned[1:]}" if len(cleaned) > 1 else f"Agenda includes {cleaned.lower()}"
    if cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."
    return cleaned


def _derive_preview_topics(*, existing: tuple[str, ...]) -> tuple[str, ...]:
    replacements = {
        "Resolution Approval": "Resolution Agenda Items",
        "Ordinance Adoption": "Ordinance Agenda Items",
        "Public Hearing Scheduling": "Public Hearings",
        "Development Agreement Terms": "Development Agreement Agenda Items",
        "Consent Agenda Changes": "Consent Agenda Items",
    }
    preview_topics: list[str] = []
    for topic in existing:
        mapped = replacements.get(topic, topic)
        if mapped.lower().startswith("the "):
            continue
        if len(mapped.split()) > 6:
            continue
        if mapped not in preview_topics:
            preview_topics.append(mapped)
    sanitized = sanitize_notable_topics(preview_topics, max_items=5)
    return sanitized or ("Agenda items",)


def _derive_basic_topics(*, key_decisions: tuple[str, ...], key_actions: tuple[str, ...]) -> tuple[str, ...]:
    labels: list[str] = []
    for sentence in [*key_decisions, *key_actions]:
        match = re.search(r"\b([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+){0,2})\b", sentence)
        candidate = match.group(1).strip() if match is not None else sentence.split(".", 1)[0].strip()
        if candidate and candidate not in labels:
            labels.append(candidate)
        if len(labels) >= 3:
            break
    if not labels:
        return ("Meeting outcomes",)
    return tuple(labels)


def _split_sentences(text: str) -> list[str]:
    return [sentence for sentence, _, _, _ in _split_sentences_with_offsets(text)]


def _derive_notable_topics(*, key_decisions: tuple[str, ...], key_actions: tuple[str, ...]) -> tuple[str, ...]:
    return _derive_notable_topics_from_findings([*key_decisions, *key_actions])


def _derive_notable_topics_from_findings(findings: Sequence[str]) -> tuple[str, ...]:
    findings = [finding for finding in findings if _normalize_generated_text(finding)]
    if not findings:
        return ("Meeting outcomes",)

    scores: Counter[str] = Counter()
    first_seen: dict[str, int] = {}

    def add_candidate(label: str, *, weight: int) -> None:
        normalized = _normalize_topic_label(label)
        if not normalized:
            return
        if _is_generic_topic_label(normalized):
            return
        if normalized not in first_seen:
            first_seen[normalized] = len(first_seen)
        scores[normalized] += max(weight, 1)

    for finding in findings:
        lower_finding = finding.lower()
        for marker, label in _TOPIC_CONCEPT_RULES:
            if marker in lower_finding:
                add_candidate(label, weight=3)

        phrase_candidate = _extract_phrase_topic_candidate(finding)
        if phrase_candidate:
            add_candidate(phrase_candidate, weight=2)

        civic_ngrams = _extract_civic_ngrams(lower_finding)
        for ngram in civic_ngrams:
            add_candidate(ngram, weight=1)

    ordered = [
        label
        for label, _ in sorted(
            scores.items(),
            key=lambda item: (-item[1], first_seen[item[0]], item[0]),
        )
    ]

    bounded = list(sanitize_notable_topics(ordered[:5], max_items=5))
    if len(bounded) < 3:
        bounded = list(sanitize_notable_topics(_apply_topic_fallbacks(existing=bounded, findings=findings), max_items=5))

    if not bounded:
        return ("Meeting outcomes",)
    return tuple(bounded[:5])


def _supplement_notable_topics(
    *,
    notable_topics: tuple[str, ...],
    summary: str,
    key_decisions: tuple[str, ...],
    key_actions: tuple[str, ...],
    structured_relevance: StructuredRelevance | None,
) -> tuple[str, ...]:
    candidates: list[str] = list(notable_topics)
    supporting_findings: list[str] = [summary, *key_decisions, *key_actions]
    if structured_relevance is not None:
        for field in (
            structured_relevance.subject,
            structured_relevance.location,
            structured_relevance.action,
            structured_relevance.scale,
        ):
            if field is not None:
                supporting_findings.append(field.value)

    supplemental_topics = _derive_notable_topics_from_findings(supporting_findings)
    for topic in supplemental_topics:
        if topic not in candidates:
            candidates.append(topic)

    return tuple(sanitize_notable_topics(candidates, max_items=5))


def _extract_phrase_topic_candidate(sentence: str) -> str | None:
    match = re.search(
        r"\b(?:approve(?:d)?|adopt(?:ed)?|authorize(?:d)?|direct(?:ed)?|schedule(?:d)?|table(?:d)?|ratif(?:ied|y)|denied|accept(?:ed)?|amend(?:ed)?|continue(?:d)?)\b\s+"
        r"(?:the\s+|a\s+|an\s+)?([a-z][a-z0-9\-\s]{6,100})",
        sentence.lower(),
    )
    if match is None:
        return None

    phrase = match.group(1)
    phrase = re.split(r"[,;]|\s+(?:for|to|with|by|on|at|after|before)\s+", phrase, maxsplit=1)[0]
    phrase = re.sub(r"\s+", " ", phrase).strip(" .,-")
    if not phrase:
        return None

    suppression_tokens = _topic_suppression_tokens()
    words = [word for word in phrase.split() if word not in suppression_tokens]
    if len(words) < 2:
        return None
    return " ".join(word.capitalize() for word in words)


def _extract_civic_ngrams(lower_sentence: str) -> tuple[str, ...]:
    suppression_tokens = _topic_suppression_tokens()
    generic_tokens = _topic_generic_tokens()
    tokens = [
        token
        for token in re.findall(r"[a-z][a-z\-]{2,}", lower_sentence)
        if token not in suppression_tokens and token not in generic_tokens
    ]
    if len(tokens) < 2:
        return ()

    ngrams: list[str] = []
    for index in range(len(tokens) - 1):
        pair = (tokens[index], tokens[index + 1])
        if pair[0] == pair[1]:
            continue
        ngrams.append(" ".join(word.capitalize() for word in pair))
    return tuple(ngrams)


def _apply_topic_fallbacks(*, existing: list[str], findings: list[str]) -> list[str]:
    result = list(existing)
    source = " ".join(findings).lower()
    for marker, label in _TOPIC_FALLBACK_LABELS:
        if marker not in source:
            continue
        normalized = _normalize_topic_label(label)
        if not normalized or normalized in result:
            continue
        if _is_generic_topic_label(normalized):
            continue
        result.append(normalized)
        if len(result) >= 3:
            break
    return result


def _normalize_topic_label(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip(" .,-")
    if not normalized:
        return ""
    if normalized.lower() in _GENERIC_TOPIC_TOKENS:
        return ""
    return normalized


def _is_generic_topic_label(label: str) -> bool:
    suppression_tokens = _topic_suppression_tokens()
    generic_tokens = _topic_generic_tokens()
    tokens = [token for token in re.findall(r"[a-z][a-z\-]{2,}", label.lower()) if token not in suppression_tokens]
    if not tokens:
        return True
    return all(token in generic_tokens for token in tokens)


def _is_low_signal_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    low_signal_markers = (
        "elected officials present",
        "city staff present",
        "present electronically",
        "council chambers",
        "page ",
        "city recorder",
        "recording of the discussion can be found",
        "parcel number",
        "is located directly",
    )
    if any(marker in lower for marker in low_signal_markers):
        return True
    if _is_meeting_operations_sentence(sentence):
        return True
    if len(sentence) > 220 and ";" in sentence:
        return True
    return False


def _is_meeting_operations_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    return any(marker in lower for marker in _MEETING_OPERATIONS_MARKERS)


def _focus_source_text(text: str) -> str:
    sentences = _split_sentences(text)
    focused = [sentence for sentence in sentences if not _is_low_signal_sentence(sentence)]
    if not focused:
        focused = sentences
    return " ".join(focused)


def _is_low_value_summary_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    if _is_low_signal_sentence(sentence) or _is_low_value_outcome(sentence):
        return True
    low_value_markers = (
        "recording of the discussion can be found",
        "recording of the motion can be found",
        "seconded the motion",
        "the motion passed with",
    )
    if any(marker in lower for marker in low_value_markers):
        return True
    if lower.count(" yes") >= 2 or lower.count(" no") >= 2:
        return True
    return False


def _is_presenter_only_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    if any(
        marker in lower
        for marker in (
            "approved",
            "adopted",
            "authorized",
            "awarded",
            "directed",
            "provided direction",
            "motion carried",
            "moved to",
            "ordinance",
            "resolution",
        )
    ):
        return False
    return any(
        marker in lower
        for marker in (
            "presented",
            "provided an overview",
            "reviewed",
            "responded to questions",
        )
    )


def _score_summary_sentence(sentence: str) -> int:
    lower = sentence.lower()
    score = 0
    if any(
        marker in lower
        for marker in (
            "approved",
            "adopted",
            "authorized",
            "awarded",
            "denied",
            "motion carried",
            "moved to adopt",
            "moved to approve",
        )
    ):
        score += 6
    if any(marker in lower for marker in ("directed", "provided direction", "scheduled", "public hearing")):
        score += 4
    if any(
        marker in lower
        for marker in (
            "budget",
            "financial report",
            "future land use",
            "land use",
            "map",
            "plan",
            "report",
            "agreement",
            "contract",
            "ordinance",
            "resolution",
            "code",
            "fee",
        )
    ):
        score += 2
    if _is_presenter_only_sentence(sentence):
        score -= 2
    return score


def _normalize_summary_sentence(sentence: str) -> str:
    lower = sentence.lower()
    if any(
        marker in lower
        for marker in (
            "approved",
            "adopted",
            "authorized",
            "awarded",
            "denied",
            "motion carried",
            "moved to",
        )
    ):
        return _normalize_decision_sentence(sentence)
    if any(marker in lower for marker in ("directed", "provided direction", "scheduled", "public hearing")):
        return _normalize_action_sentence(sentence)
    return _normalize_sentence(sentence)


def _build_grounded_summary(text: str) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return "Meeting source text unavailable."
    candidate_sentences = [sentence for sentence in sentences if not _is_low_value_summary_sentence(sentence)]
    if not candidate_sentences:
        candidate_sentences = [sentence for sentence in sentences if not _is_meeting_operations_sentence(sentence)]
    if not candidate_sentences:
        candidate_sentences = sentences

    ranked_candidates: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(candidate_sentences):
        normalized = _normalize_summary_sentence(sentence)
        if not normalized or _is_low_value_summary_sentence(normalized):
            continue
        ranked_candidates.append((_score_summary_sentence(sentence), index, normalized))

    if not ranked_candidates:
        ranked_candidates = [(0, index, _normalize_sentence(sentence)) for index, sentence in enumerate(candidate_sentences)]

    selected: list[str] = []
    seen: set[str] = set()
    for _, _, candidate in sorted(ranked_candidates, key=lambda item: (-item[0], item[1])):
        dedupe_key = candidate.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        selected.append(candidate)
        if len(selected) >= 3:
            break

    summary = " ".join(selected or [_normalize_sentence(candidate_sentences[0])])
    return summary[:520]


def _normalize_decision_sentence(sentence: str) -> str:
    cleaned = _normalize_sentence(sentence)
    if not cleaned:
        return cleaned

    cleaned = re.sub(
        r"\bCouncilmember\s+[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)?\s+seconded the motion\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" .")
    if cleaned and cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."

    motion_match = re.search(
        r"\bmoved to\s+(adopt|approve|authorize|award|deny|continue)\b\s+(?P<subject>.+)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if motion_match is not None:
        verb = motion_match.group(1).lower()
        remainder = motion_match.group("subject").strip().rstrip(".")
        remainder = re.sub(r"\bwith updated revisions made in work session\b", "with work session revisions", remainder, flags=re.IGNORECASE)
        remainder = re.sub(
            r"^an ordinance of [^,]+(?:,\s*[^,]+){0,2},\s*",
            "the ordinance ",
            remainder,
            flags=re.IGNORECASE,
        )
        remainder = re.sub(
            r"^a resolution of [^,]+(?:,\s*[^,]+){0,2},\s*",
            "the resolution ",
            remainder,
            flags=re.IGNORECASE,
        )
        mapping = {
            "adopt": "Adopted",
            "approve": "Approved",
            "authorize": "Authorized",
            "award": "Awarded",
            "deny": "Denied",
            "continue": "Continued",
        }
        return f"{mapping.get(verb, 'Approved')} {remainder.strip()} .".replace(" .", ".")

    resolution_match = re.search(
        r"\bresolution\b\s*[-:]?\s*(?:a\s+resolution\s+of\s+.*?)?"
        r"(approving|consenting|authorizing|adopting|amending|accepting|ratifying)\s+(.+)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if resolution_match:
        verb = resolution_match.group(1).lower()
        remainder = resolution_match.group(2).strip().rstrip(".")
        mapping = {
            "approving": "Approved",
            "consenting": "Consented",
            "authorizing": "Authorized",
            "adopting": "Adopted",
            "amending": "Amended",
            "accepting": "Accepted",
            "ratifying": "Ratified",
        }
        return f"{mapping.get(verb, 'Approved')} {remainder}."

    return cleaned


def _normalize_action_sentence(sentence: str) -> str:
    cleaned = _normalize_sentence(sentence)
    if not cleaned:
        return cleaned

    cleaned = _normalize_decision_sentence(cleaned)

    cleaned = re.sub(r"\bthe council determined to\b", "The Council decided to", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthis item\b", "the agenda item", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwas approved\b", "was approved", cleaned, flags=re.IGNORECASE)
    return cleaned


def _normalize_sentence(sentence: str) -> str:
    normalized = _normalize_generated_text(sentence).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return ""
    if normalized[-1] not in ".!?":
        normalized = f"{normalized}."
    return normalized


def _is_low_value_outcome(sentence: str) -> bool:
    lower = sentence.lower()
    markers = (
        "is located directly",
        "parcel number",
        "recording of the discussion can be found",
        "recording of the motion can be found",
        "joined the meeting",
        "was excused",
        "roll call",
        "call to order",
        "pledge of allegiance",
        "mayor pro tempore",
        "the motion passed with",
    )
    if any(marker in lower for marker in markers):
        return True
    if lower.count(" yes") >= 2 or lower.count(" no") >= 2:
        return True
    return False


def _is_low_value_anchor_text(anchor_text: str) -> bool:
    normalized = _normalize_generated_text(anchor_text).lower()
    if not normalized:
        return True
    if re.fullmatch(r"\d{1,2}(?::\d{2})?\s*(?:am|pm)", normalized):
        return True
    if any(
        marker in normalized
        for marker in (
            "mayor",
            "councilmember",
            "pro tempore",
            "roll call",
            "call to order",
            "pledge of allegiance",
        )
    ):
        return True
    return False


def _build_claims_from_findings(
    *,
    key_decisions: tuple[str, ...],
    key_actions: tuple[str, ...],
    source_text: str,
    artifact_id: str,
    section_ref: str,
    compose_input: SummarizeComposeInput | None,
    fallback_claim: str,
    evidence_projection_enabled: bool = True,
) -> tuple[SummaryClaim, ...]:
    findings: list[str] = []
    for finding in [*key_decisions, *key_actions]:
        normalized = _normalize_sentence(finding)
        if normalized and normalized not in findings:
            findings.append(normalized)

    if not findings and fallback_claim:
        findings.append(_normalize_sentence(fallback_claim))

    claims: list[SummaryClaim] = []
    for finding in findings[:4]:
        evidence_match = _build_evidence_match_for_finding(
            source_text=source_text,
            finding=finding,
            artifact_id=artifact_id,
            default_section_ref=section_ref,
            compose_input=compose_input,
            evidence_projection_enabled=evidence_projection_enabled,
        )
        claims.append(
            SummaryClaim(
                claim_text=finding,
                evidence=(
                    ClaimEvidencePointer(
                        artifact_id=evidence_match.artifact_id,
                        section_ref=evidence_match.section_ref,
                        char_start=evidence_match.char_start,
                        char_end=evidence_match.char_end,
                        excerpt=evidence_match.excerpt,
                        document_id=evidence_match.document_id,
                        span_id=evidence_match.span_id,
                        document_kind=evidence_match.document_kind,
                        section_path=evidence_match.section_path,
                        precision=evidence_match.precision,
                        confidence=evidence_match.confidence,
                    ),
                ),
                evidence_gap=False,
            )
        )
    return tuple(claims)


def _synthesize_structured_relevance(
    *,
    source_text: str,
    artifact_id: str,
    section_ref: str,
    compose_input: SummarizeComposeInput | None,
    authority_policy: _AuthorityPolicyResult,
) -> StructuredRelevance | None:
    snippets = _collect_relevance_snippets(
        source_text=source_text,
        compose_input=compose_input,
        authority_policy=authority_policy,
    )
    candidates: list[_StructuredRelevanceCandidate] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    for snippet_index, snippet in enumerate(snippets):
        candidate = _build_structured_relevance_candidate(
            snippet=snippet,
            artifact_id=artifact_id,
            section_ref=section_ref,
            source_rank=snippet_index,
            preview_only=authority_policy.preview_only,
        )
        if candidate is None:
            continue
        dedupe_key = (
            _normalize_generated_text(candidate.subject or "").lower(),
            _normalize_generated_text(candidate.location or "").lower(),
            _normalize_generated_text(candidate.action or "").lower(),
            _normalize_generated_text(candidate.scale or "").lower(),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        candidates.append(candidate)

    candidates = sorted(candidates, key=lambda item: item.rank)[:3]

    if authority_policy.authority_outcome == "unresolved_conflict":
        candidates = [
            _StructuredRelevanceCandidate(
                subject=item.subject,
                location=item.location,
                action=None,
                scale=item.scale,
                evidence=item.evidence,
                source_type=item.source_type,
                rank=item.rank,
            )
            for item in candidates
        ]

    items: list[StructuredRelevanceItem] = []
    for index, candidate in enumerate(candidates, start=1):
        subject_field = _build_structured_relevance_field(candidate.subject, candidate.evidence, authority_policy.preview_only)
        location_field = _build_structured_relevance_field(candidate.location, candidate.evidence, authority_policy.preview_only)
        action_field = _build_structured_relevance_field(candidate.action, candidate.evidence, authority_policy.preview_only)
        scale_field = _build_structured_relevance_field(candidate.scale, candidate.evidence, authority_policy.preview_only)
        impact_tags = _classify_structured_impact_tags(candidate, preview_only=authority_policy.preview_only)
        if all(field is None for field in (subject_field, location_field, action_field, scale_field)) and not impact_tags:
            continue
        items.append(
            StructuredRelevanceItem(
                item_id=f"outcome-{index}",
                subject=subject_field,
                location=location_field,
                action=action_field,
                scale=scale_field,
                impact_tags=impact_tags,
            )
        )

    if not items:
        return None

    primary = items[0]
    relevance = StructuredRelevance(
        subject=primary.subject,
        location=primary.location,
        action=primary.action,
        scale=primary.scale,
        impact_tags=_merge_structured_impact_tags(items),
        items=tuple(items),
    )
    if relevance.is_empty:
        return None
    return relevance


def _apply_structured_relevance_carry_through(
    *,
    summary: str,
    key_decisions: tuple[str, ...],
    key_actions: tuple[str, ...],
    structured_relevance: StructuredRelevance | None,
    authority_policy: _AuthorityPolicyResult,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    if structured_relevance is None:
        return summary, key_decisions, key_actions

    carry_sentence = _build_structured_relevance_carry_sentence(
        structured_relevance=structured_relevance,
        authority_policy=authority_policy,
    )
    if carry_sentence is None:
        return summary, key_decisions, key_actions

    projection = " ".join((summary, *key_decisions, *key_actions))
    if not _text_needs_structured_carry_through(projection, structured_relevance=structured_relevance):
        return summary, key_decisions, key_actions

    updated_summary = summary
    if _text_needs_structured_carry_through(summary, structured_relevance=structured_relevance):
        updated_summary = carry_sentence[:520]

    updated_decisions = key_decisions
    if key_decisions and _text_needs_structured_carry_through(key_decisions[0], structured_relevance=structured_relevance):
        updated_decisions = (carry_sentence, *key_decisions[1:])

    updated_actions = key_actions
    if not updated_decisions and key_actions and _text_needs_structured_carry_through(
        key_actions[0], structured_relevance=structured_relevance
    ):
        updated_actions = (carry_sentence, *key_actions[1:])

    return updated_summary, updated_decisions, updated_actions


def _build_structured_relevance_carry_sentence(
    *,
    structured_relevance: StructuredRelevance,
    authority_policy: _AuthorityPolicyResult,
) -> str | None:
    focus = _build_structured_focus_phrase(structured_relevance=structured_relevance)
    if focus is None:
        return None

    action = None
    if structured_relevance.action is not None:
        normalized_action = _normalize_generated_text(structured_relevance.action.value).lower()
        if normalized_action in {"approved", "continued", "denied", "reviewed", "scheduled"}:
            action = normalized_action

    if authority_policy.authority_outcome == "unresolved_conflict":
        return (
            f"Available materials describe {focus}, but the final action remains uncertain because published minutes are unavailable and sources conflict. "
            "No decisions or completed actions are recorded yet."
        )[:520]

    if authority_policy.preview_only:
        return (
            f"Agenda materials preview scheduled consideration of {focus}. "
            "No decisions or completed actions are recorded yet because published minutes are not available."
        )[:520]

    if "weak_evidence_precision" in authority_policy.reason_codes:
        if action is not None:
            return f"Minutes indicate the Council {action} {focus}, but the evidence locators remain weak."[:520]
        return f"Minutes describe {focus}, but the evidence locators remain weak."[:520]

    if "supplemental_sources_missing" in authority_policy.reason_codes:
        if action is not None:
            return (
                f"Minutes show the Council {action} {focus}, though supporting agenda or packet materials are missing."
            )[:520]
        return f"Minutes describe {focus}, though supporting agenda or packet materials are missing."[:520]

    if action is not None:
        return f"The Council {action} {focus}."[:520]
    return f"The meeting focused on {focus}."[:520]


def _build_structured_focus_phrase(*, structured_relevance: StructuredRelevance) -> str | None:
    subject = _normalize_generated_text(structured_relevance.subject.value) if structured_relevance.subject is not None else ""
    location = _normalize_generated_text(structured_relevance.location.value) if structured_relevance.location is not None else ""
    scale = _normalize_generated_text(structured_relevance.scale.value) if structured_relevance.scale is not None else ""

    if subject:
        if re.match(r"^(?:the|a|an)\s+", subject, flags=re.IGNORECASE):
            focus = subject
        else:
            focus = f"the {subject}"
    elif location:
        focus = location
    elif scale:
        focus = scale
    else:
        return None

    if location and location.lower() not in focus.lower():
        focus = f"{focus} in {location}"
    if scale and scale.lower() not in focus.lower():
        connector = " for " if "$" in scale else " covering "
        focus = f"{focus}{connector}{scale}"
    return focus


def _text_needs_structured_carry_through(text: str, *, structured_relevance: StructuredRelevance) -> bool:
    normalized = _normalize_generated_text(text)
    if not normalized:
        return True

    lower_text = normalized.lower()
    subject = _normalize_generated_text(structured_relevance.subject.value).lower() if structured_relevance.subject is not None else ""
    location = _normalize_generated_text(structured_relevance.location.value).lower() if structured_relevance.location is not None else ""
    scale = _normalize_generated_text(structured_relevance.scale.value).lower() if structured_relevance.scale is not None else ""

    if subject and subject in lower_text:
        return False
    if location and location in lower_text and not subject:
        return False
    if scale and scale in lower_text and not subject and not location:
        return False
    if _GENERIC_CARRY_THROUGH_PATTERN.search(normalized):
        return True
    if any(re.search(rf"\b{re.escape(candidate)}\b", lower_text) for candidate in _STRUCTURED_GENERIC_SUBJECTS):
        return True
    return bool(subject or location or scale)


def _collect_relevance_snippets(
    *,
    source_text: str,
    compose_input: SummarizeComposeInput | None,
    authority_policy: _AuthorityPolicyResult,
) -> tuple[_RelevanceSnippet, ...]:
    snippets: list[_RelevanceSnippet] = []
    if compose_input is None:
        for sentence, sentence_index, char_start, char_end in _split_sentences_with_offsets(source_text):
            if _is_low_signal_sentence(sentence):
                continue
            snippets.append(
                _RelevanceSnippet(
                    text=sentence,
                    source=None,
                    span=None,
                    sentence_index=sentence_index,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
        return tuple(snippets)

    source_rank = {source_type: index for index, source_type in enumerate(compose_input.source_order)}
    ordered_sources = sorted(
        (source for source in compose_input.sources if source.text.strip()),
        key=lambda source: (
            0 if authority_policy.authoritative_source_type == source.source_type else 1,
            source_rank.get(source.source_type, 10**9),
            source.source_type,
        ),
    )
    for source in ordered_sources:
        if source.spans:
            for span in source.spans:
                sentence_spans = _split_sentences_with_offsets(span.span_text)
                use_sentence_level = (
                    len(sentence_spans) > 1
                    or span.start_char_offset is None
                    or span.end_char_offset is None
                    or (span.end_char_offset - span.start_char_offset > 400)
                )
                if use_sentence_level and sentence_spans:
                    for sentence, sentence_index, char_start, char_end in sentence_spans:
                        if _is_low_signal_sentence(sentence):
                            continue
                        snippets.append(
                            _RelevanceSnippet(
                                text=sentence,
                                source=source,
                                span=span,
                                sentence_index=sentence_index,
                                char_start=(span.start_char_offset + char_start if span.start_char_offset is not None else char_start),
                                char_end=(span.start_char_offset + char_end if span.start_char_offset is not None else char_end),
                            )
                        )
                    continue

                normalized = _normalize_generated_text(span.span_text)
                if not normalized or _is_low_signal_sentence(normalized):
                    continue
                snippets.append(
                    _RelevanceSnippet(
                        text=normalized,
                        source=source,
                        span=span,
                        sentence_index=None,
                        char_start=span.start_char_offset,
                        char_end=span.end_char_offset,
                    )
                )
            continue

        for sentence, sentence_index, char_start, char_end in _split_sentences_with_offsets(source.text):
            if _is_low_signal_sentence(sentence):
                continue
            snippets.append(
                _RelevanceSnippet(
                    text=sentence,
                    source=source,
                    span=None,
                    sentence_index=sentence_index,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
    return tuple(snippets)


def _build_structured_relevance_candidate(
    *,
    snippet: _RelevanceSnippet,
    artifact_id: str,
    section_ref: str,
    source_rank: int,
    preview_only: bool,
) -> _StructuredRelevanceCandidate | None:
    anchors = harvest_relevance_anchors(snippet.text)
    subject = _extract_structured_subject(snippet.text, anchors=anchors)
    location = _extract_structured_location(anchors=anchors)
    action = _extract_structured_action(snippet.text)
    scale = _extract_structured_scale(snippet.text, anchors=anchors)

    if subject is None and location is None and scale is None:
        return None

    evidence = _build_relevance_evidence_pointer(
        snippet=snippet,
        artifact_id=artifact_id,
        section_ref=section_ref,
    )
    richness = sum(value is not None for value in (subject, location, action, scale))
    decisive_action = 0 if action in {"approved", "directed", "continued", "denied"} else 1
    source_priority = 0 if snippet.source is not None and snippet.source.source_type == "minutes" else 1
    if preview_only and action == "approved":
        action = None
    return _StructuredRelevanceCandidate(
        subject=subject,
        location=location,
        action=action,
        scale=scale,
        evidence=evidence,
        source_type=(snippet.source.source_type if snippet.source is not None else None),
        rank=(source_priority, decisive_action, -richness, source_rank, (subject or location or scale or "")),
    )


def _build_relevance_evidence_pointer(
    *,
    snippet: _RelevanceSnippet,
    artifact_id: str,
    section_ref: str,
) -> ClaimEvidencePointer:
    if snippet.source is not None:
        evidence_match = _compose_evidence_match(
            source=snippet.source,
            span=snippet.span,
            fallback_artifact_id=artifact_id,
            fallback_section_ref=section_ref,
            include_offsets=True,
        )
        sentence_section_ref = evidence_match.section_ref
        if snippet.sentence_index is not None and snippet.source.source_type:
            sentence_section_ref = f"{snippet.source.source_type}.sentence.{snippet.sentence_index + 1}"
        char_start = evidence_match.char_start
        char_end = evidence_match.char_end
        excerpt = evidence_match.excerpt
        if snippet.sentence_index is not None:
            excerpt = _normalize_generated_text(snippet.text)[:280]
            if snippet.char_start is not None and snippet.char_end is not None and snippet.char_end > snippet.char_start:
                char_start = snippet.char_start
                char_end = snippet.char_end
        return ClaimEvidencePointer(
            artifact_id=evidence_match.artifact_id,
            section_ref=sentence_section_ref,
            char_start=char_start,
            char_end=char_end,
            excerpt=excerpt,
            document_id=evidence_match.document_id,
            span_id=evidence_match.span_id,
            document_kind=evidence_match.document_kind,
            section_path=evidence_match.section_path,
            precision=evidence_match.precision,
            confidence=evidence_match.confidence,
        )

    sentence_section_ref = section_ref
    if snippet.sentence_index is not None:
        sentence_section_ref = f"{section_ref}.sentence.{snippet.sentence_index + 1}"
    return ClaimEvidencePointer(
        artifact_id=artifact_id,
        section_ref=sentence_section_ref,
        char_start=snippet.char_start,
        char_end=snippet.char_end,
        excerpt=_normalize_generated_text(snippet.text)[:280],
    )


def _build_structured_relevance_field(
    value: str | None,
    evidence: ClaimEvidencePointer,
    preview_only: bool,
) -> StructuredRelevanceField | None:
    normalized = _normalize_generated_text(value or "")
    if not normalized:
        return None
    confidence = evidence.confidence or ("low" if preview_only else "medium")
    if preview_only and confidence == "high":
        confidence = "medium"
    return StructuredRelevanceField(value=normalized, evidence=(evidence,), confidence=confidence)


def _classify_structured_impact_tags(
    candidate: _StructuredRelevanceCandidate,
    *,
    preview_only: bool,
) -> tuple[StructuredImpactTag, ...]:
    support_text = _normalize_generated_text(
        " ".join(
            value
            for value in (
                candidate.subject,
                candidate.action,
                candidate.scale,
                candidate.evidence.excerpt,
            )
            if value
        )
    ).lower()
    if not support_text:
        return ()

    confidence = candidate.evidence.confidence or ("low" if preview_only else "medium")
    if preview_only and confidence == "high":
        confidence = "medium"

    tags: list[StructuredImpactTag] = []
    for tag in _APPROVED_IMPACT_TAGS:
        if _impact_tag_supported(tag=tag, support_text=support_text):
            tags.append(
                StructuredImpactTag(
                    tag=tag,
                    evidence=(candidate.evidence,),
                    confidence=confidence,
                )
            )
    return tuple(tags)


def _impact_tag_supported(*, tag: str, support_text: str) -> bool:
    if tag == "housing":
        return bool(
            _HOUSING_TERMS_PATTERN.search(support_text)
            or (
                _HOUSING_UNITS_PATTERN.search(support_text)
                and (_HOUSING_PROJECT_PATTERN.search(support_text) or _LAND_USE_TERMS_PATTERN.search(support_text))
            )
        )
    if tag == "traffic":
        return bool(_TRAFFIC_TERMS_PATTERN.search(support_text))
    if tag == "utilities":
        return bool(_UTILITIES_TERMS_PATTERN.search(support_text))
    if tag == "parks":
        return bool(_PARKS_TERMS_PATTERN.search(support_text))
    if tag == "fees":
        return bool(_FEES_TERMS_PATTERN.search(support_text))
    if tag == "land_use":
        return bool(_LAND_USE_TERMS_PATTERN.search(support_text))
    return False


def _merge_structured_impact_tags(items: Sequence[StructuredRelevanceItem]) -> tuple[StructuredImpactTag, ...]:
    merged: dict[str, StructuredImpactTag] = {}
    for item in items:
        for impact_tag in item.impact_tags:
            if impact_tag.tag not in merged:
                merged[impact_tag.tag] = impact_tag
    return tuple(merged[tag] for tag in _APPROVED_IMPACT_TAGS if tag in merged)


def _extract_structured_action(text: str) -> str | None:
    normalized = _normalize_generated_text(text)
    for pattern, label in _STRUCTURED_ACTION_PATTERNS:
        if pattern.search(normalized):
            return label
    return None


def _extract_structured_location(*, anchors: tuple[Any, ...]) -> str | None:
    for anchor in anchors:
        if anchor.kind != "location":
            continue
        normalized = _normalize_generated_text(anchor.text)
        if normalized:
            return normalized
    return None


def _extract_structured_scale(text: str, *, anchors: tuple[Any, ...]) -> str | None:
    scale_anchors = [anchor for anchor in anchors if anchor.kind in {"scale", "date"}]
    if not scale_anchors:
        return None
    first = scale_anchors[0]
    if len(scale_anchors) >= 2:
        second = scale_anchors[1]
        gap = second.position - (first.position + len(first.text))
        if 0 <= gap <= 24:
            combined = _normalize_generated_text(text[first.position : second.position + len(second.text)])
            if combined:
                return combined
    return _normalize_generated_text(first.text)


def _extract_structured_subject(text: str, *, anchors: tuple[Any, ...]) -> str | None:
    normalized = _normalize_generated_text(text)
    subject_reference = next((anchor.text for anchor in anchors if anchor.kind == "subject"), None)
    action_match = re.search(
        r"\b(?:approve(?:d)?|adopt(?:ed)?|authorize(?:d)?|award(?:ed)?|direct(?:ed)?|schedule(?:d)?|continue(?:d)?|deny|denied|reject(?:ed)?|review(?:ed)?|consider(?:ed)?|"
        r"motion carried to authorize)\b\s+(?:the\s+|a\s+|an\s+)?(?P<subject>[^;]+)",
        normalized,
        flags=re.IGNORECASE,
    )
    candidates: list[str] = []
    proper_phrase_match = _STRUCTURED_SUBJECT_PATTERN.search(normalized)
    if proper_phrase_match is not None:
        candidates.append(proper_phrase_match.group(0))
    if subject_reference is not None:
        candidates.append(subject_reference)
    if action_match is not None:
        candidates.append(action_match.group("subject"))

    for candidate in candidates:
        cleaned = _trim_structured_subject(candidate)
        if cleaned:
            return cleaned
    return None


def _trim_structured_subject(value: str) -> str | None:
    cleaned = _normalize_generated_text(value)
    regarding_match = re.search(
        r"regarding\s+([A-Z][A-Za-z0-9'&./-]+(?:\s+[A-Z][A-Za-z0-9'&./-]+){0,4})",
        cleaned,
    )
    if regarding_match is not None and any(marker in cleaned.lower() for marker in ("ordinance", "code section", "municipal code")):
        return f"{regarding_match.group(1).strip()} ordinance"

    cleaned = re.sub(
        r"^(?:an\s+|the\s+)?ordinance of [^,]+(?:,\s*[^,]+){0,2},\s*",
        "ordinance ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:a\s+|the\s+)?resolution of [^,]+(?:,\s*[^,]+){0,2},\s*",
        "resolution ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:of|for|regarding)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\s+for\s+[A-Z][A-Za-z0-9'&./-]+(?:\s+[A-Z][A-Za-z0-9'&./-]+){0,4}\s+(?:Street|Road|Avenue|Boulevard|Drive|Lane|Way|Trail|Highway|Corridor|District|Neighborhood|Subdivision|Zone|Overlay|Parcel).*$",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+covering\s+.+$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\s+(?:on|at|in|within|near|along|before|after|by)\s+(?:\$|\d|january|february|march|april|may|june|july|august|september|october|november|december).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s+(?:at|in|within|near|along)\s+[A-Z][A-Za-z0-9'&./-]+(?:\s+[A-Z][A-Za-z0-9'&./-]+){0,4}\s+(?:Street|Road|Avenue|Boulevard|Drive|Lane|Way|Trail|Highway|Corridor|District|Neighborhood|Subdivision|Zone|Overlay|Parcel).*$",
        "",
        cleaned,
    )
    cleaned = cleaned.strip(" .,:;-")
    if not cleaned:
        return None
    if cleaned.lower() in _STRUCTURED_GENERIC_SUBJECTS:
        return None
    return cleaned


@dataclass(frozen=True)
class _EvidenceMatch:
    artifact_id: str
    excerpt: str
    section_ref: str
    char_start: int | None
    char_end: int | None
    document_id: str | None = None
    span_id: str | None = None
    document_kind: str | None = None
    section_path: str | None = None
    precision: str | None = None
    confidence: str | None = None


def _build_evidence_match_for_finding(
    *,
    source_text: str,
    finding: str,
    artifact_id: str,
    default_section_ref: str,
    compose_input: SummarizeComposeInput | None,
    evidence_projection_enabled: bool,
) -> _EvidenceMatch:
    if compose_input is not None:
        composed_match = _best_composed_evidence_match_for_finding(
            finding=finding,
            fallback_artifact_id=artifact_id,
            fallback_section_ref=default_section_ref,
            compose_input=compose_input,
            include_offsets=evidence_projection_enabled,
        )
        if composed_match is not None:
            return composed_match

    if evidence_projection_enabled:
        return _best_evidence_match_for_finding(
            source_text=source_text,
            finding=finding,
            fallback_artifact=artifact_id,
            default_section_ref=default_section_ref,
        )

    return _EvidenceMatch(
        artifact_id=artifact_id,
        excerpt=_normalize_generated_text(finding)[:280],
        section_ref=default_section_ref,
        char_start=None,
        char_end=None,
    )


def _best_composed_evidence_match_for_finding(
    *,
    finding: str,
    fallback_artifact_id: str,
    fallback_section_ref: str,
    compose_input: SummarizeComposeInput,
    include_offsets: bool,
) -> _EvidenceMatch | None:
    source_rank = {source_type: index for index, source_type in enumerate(compose_input.source_order)}
    available_sources = tuple(source for source in compose_input.sources if source.text.strip())
    if not available_sources:
        return None

    best_source: ComposedSourceDocument | None = None
    best_span: ComposedSourceSpan | None = None
    best_score = -1
    best_source_rank = 10**9
    best_span_rank = 10**9

    for source in available_sources:
        current_source_rank = source_rank.get(source.source_type, 10**9)
        candidate_spans = source.spans or ()
        if candidate_spans:
            for span_index, span in enumerate(candidate_spans):
                score = _score_finding_match(finding=finding, candidate_text=span.span_text)
                if (
                    score > best_score
                    or (score == best_score and current_source_rank < best_source_rank)
                    or (
                        score == best_score
                        and current_source_rank == best_source_rank
                        and span_index < best_span_rank
                    )
                ):
                    best_source = source
                    best_span = span
                    best_score = score
                    best_source_rank = current_source_rank
                    best_span_rank = span_index
            continue

        score = _score_finding_match(finding=finding, candidate_text=source.text)
        if score > best_score or (score == best_score and current_source_rank < best_source_rank):
            best_source = source
            best_span = None
            best_score = score
            best_source_rank = current_source_rank
            best_span_rank = 10**9

    if best_source is None:
        return None

    return _compose_evidence_match(
        source=best_source,
        span=best_span,
        fallback_artifact_id=fallback_artifact_id,
        fallback_section_ref=fallback_section_ref,
        include_offsets=include_offsets,
    )


def _compose_evidence_match(
    *,
    source: ComposedSourceDocument,
    span: ComposedSourceSpan | None,
    fallback_artifact_id: str,
    fallback_section_ref: str,
    include_offsets: bool,
) -> _EvidenceMatch:
    artifact_id = fallback_artifact_id
    excerpt = _normalize_generated_text(source.text)[:280]
    section_ref = fallback_section_ref
    char_start: int | None = None
    char_end: int | None = None
    section_path: str | None = None
    span_id: str | None = None

    if span is not None:
        artifact_id = span.artifact_id or artifact_id
        excerpt = _normalize_generated_text(span.span_text)[:280]
        section_path = span.stable_section_path
        section_ref = _section_ref_from_section_path(section_path) or fallback_section_ref
        span_id = span.span_id
        if (
            include_offsets
            and span.start_char_offset is not None
            and span.end_char_offset is not None
            and span.end_char_offset > span.start_char_offset
        ):
            char_start = span.start_char_offset
            char_end = span.end_char_offset
    else:
        artifact_id = fallback_artifact_id
        section_path = source.source_type
        section_ref = fallback_section_ref

    precision = _classify_linkage_precision(
        source_type=source.source_type,
        span=span,
        include_offsets=include_offsets,
    )
    confidence = _classify_linkage_confidence(source=source, precision=precision)

    return _EvidenceMatch(
        artifact_id=artifact_id,
        excerpt=excerpt,
        section_ref=section_ref,
        char_start=char_start,
        char_end=char_end,
        document_id=source.canonical_document_id,
        span_id=span_id,
        document_kind=source.source_type,
        section_path=section_path,
        precision=precision,
        confidence=confidence,
    )


def _score_finding_match(*, finding: str, candidate_text: str) -> int:
    finding_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", finding.lower()))
    candidate_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", candidate_text.lower()))
    score = len(finding_tokens.intersection(candidate_tokens))
    normalized_finding = _normalize_generated_text(finding).lower()
    normalized_candidate = _normalize_generated_text(candidate_text).lower()
    if normalized_finding and normalized_finding in normalized_candidate:
        score += 2
    return score


def _section_ref_from_section_path(section_path: str | None) -> str | None:
    if section_path is None:
        return None
    normalized = ".".join(segment for segment in section_path.strip().replace("\\", "/").split("/") if segment)
    return normalized or None


def _classify_linkage_precision(
    *,
    source_type: str,
    span: ComposedSourceSpan | None,
    include_offsets: bool,
) -> str:
    if span is None:
        return "file"
    if (
        include_offsets
        and span.start_char_offset is not None
        and span.end_char_offset is not None
        and span.end_char_offset > span.start_char_offset
    ):
        return "offset"
    if span.page_number is not None or span.line_index is not None:
        return "span"
    if _has_precise_section_path(source_type=source_type, section_path=span.stable_section_path):
        return "section"
    return "file"


def _has_precise_section_path(*, source_type: str, section_path: str | None) -> bool:
    normalized = (section_path or "").strip().lower()
    if not normalized or normalized == source_type:
        return False
    segments = tuple(segment for segment in normalized.split("/") if segment)
    if not segments:
        return False
    return not any("unknown" in segment for segment in segments)


def _classify_linkage_confidence(*, source: ComposedSourceDocument, precision: str) -> str:
    if source.source_origin != "canonical":
        base = "low" if precision == "file" else "medium"
    elif precision == "file":
        base = "low"
    elif source.source_type == "minutes":
        base = "high"
    else:
        base = "medium"

    if source.locator_precision == "weak":
        return {"high": "medium", "medium": "low", "low": "low"}[base]
    if source.locator_precision == "unknown" and base == "high":
        return "medium"
    return base


def _best_evidence_match_for_finding(
    *,
    source_text: str,
    finding: str,
    fallback_artifact: str,
    default_section_ref: str,
) -> _EvidenceMatch:
    sentence_spans = _split_sentences_with_offsets(source_text)
    if not sentence_spans:
        fallback_excerpt = (source_text or finding)[:280]
        return _EvidenceMatch(
            artifact_id=fallback_artifact,
            excerpt=fallback_excerpt,
            section_ref=default_section_ref,
            char_start=None,
            char_end=None,
        )

    finding_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", finding.lower()))
    best_sentence, best_index, best_start, best_end = sentence_spans[0]
    best_score = -1
    for sentence, sentence_index, sentence_start, sentence_end in sentence_spans:
        sentence_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", sentence.lower()))
        score = len(finding_tokens.intersection(sentence_tokens))
        if score > best_score:
            best_score = score
            best_sentence = sentence
            best_index = sentence_index
            best_start = sentence_start
            best_end = sentence_end

    precise_section = f"{default_section_ref}.sentence.{best_index + 1}"
    return _EvidenceMatch(
        artifact_id=fallback_artifact,
        excerpt=_normalize_generated_text(best_sentence)[:280],
        section_ref=precise_section,
        char_start=best_start,
        char_end=best_end,
    )


def _split_sentences_with_offsets(text: str) -> list[tuple[str, int, int, int]]:
    spans: list[tuple[str, int, int, int]] = []
    sentence_index = 0
    start = 0
    for index, char in enumerate(text):
        is_newline = char == "\n"
        is_sentence_punctuation = char in ".!?"
        is_decimal_point = (
            char == "."
            and index > 0
            and index + 1 < len(text)
            and text[index - 1].isdigit()
            and text[index + 1].isdigit()
        )
        if not is_newline and (not is_sentence_punctuation or is_decimal_point):
            continue

        end = index if is_newline else index + 1
        sentence = _normalize_generated_text(text[start:end]).strip()
        if not sentence:
            start = index + 1
            continue
        spans.append((sentence, sentence_index, start, end))
        sentence_index += 1
        start = index + 1

    if start < len(text):
        sentence = _normalize_generated_text(text[start:]).strip()
        if sentence:
            spans.append((sentence, sentence_index, start, len(text)))
    return spans


def _evidence_spans_from_output(output: SummarizationOutput) -> tuple[EvidenceSpanInput, ...]:
    spans: list[EvidenceSpanInput] = []
    for claim_index, claim in enumerate(output.claims, start=1):
        for evidence_index, pointer in enumerate(claim.evidence, start=1):
            spans.append(
                EvidenceSpanInput(
                    stable_section_path=pointer.section_ref,
                    line_index=claim_index - 1,
                    start_char_offset=pointer.char_start,
                    end_char_offset=pointer.char_end,
                    source_chunk_id=f"claim-{claim_index}-evidence-{evidence_index}",
                    span_text=pointer.excerpt,
                )
            )
    return tuple(spans)


def _enforce_anchor_carry_through(
    *,
    source_text: str,
    summary: str,
    key_decisions: tuple[str, ...],
    key_actions: tuple[str, ...],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    anchors = tuple(anchor for anchor in harvest_specificity_anchors(source_text) if not _is_low_value_anchor_text(anchor.text))
    if not anchors:
        return summary, key_decisions, key_actions

    projection_text = " ".join((summary, *key_decisions, *key_actions))
    missing_anchor = next(
        (anchor for anchor in anchors if not anchor_present_in_projection(anchor, projection_text)),
        None,
    )
    if missing_anchor is None:
        return summary, key_decisions, key_actions

    anchor_text = missing_anchor.text
    updated_summary = summary.strip()
    if updated_summary:
        if len(updated_summary) + len(anchor_text) + 20 <= 520:
            updated_summary = f"{updated_summary.rstrip('.')} including {anchor_text}."
            return updated_summary, key_decisions, key_actions
    else:
        updated_summary = f"Included detail: {anchor_text}."
        return updated_summary, key_decisions, key_actions

    if key_decisions:
        revised = list(key_decisions)
        revised[0] = f"{revised[0].rstrip('.')} ({anchor_text})."
        return summary, tuple(revised), key_actions

    if key_actions:
        revised = list(key_actions)
        revised[0] = f"{revised[0].rstrip('.')} ({anchor_text})."
        return summary, key_decisions, tuple(revised)

    return summary, key_decisions, key_actions