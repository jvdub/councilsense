from __future__ import annotations

import json
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
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from councilsense.app.quality_gate_rollout import (
    QualityGateRolloutConfig,
    append_shadow_diagnostics_artifact,
    build_quality_gate_rollout_metadata,
    compute_promotion_status,
    decide_enforcement_outcome,
    evaluate_shadow_gates,
    resolve_rollout_config,
)
from councilsense.app.canonical_persistence import EvidenceSpanInput, persist_pipeline_canonical_records
from councilsense.app.multi_document_compose import ComposedSourceDocument, SummarizeComposeInput, assemble_summarize_compose_input
from councilsense.app.summarization import (
    ClaimEvidencePointer,
    QualityGateEnforcementOverride,
    SummaryClaim,
    SummarizationOutput,
    publish_summarization_output,
)
from councilsense.app.specificity import anchor_present_in_projection, harvest_specificity_anchors
from councilsense.db import MeetingSummaryRepository, ProcessingLifecycleService, ProcessingRunRepository, RunLifecycleStatus


_DEFAULT_ARTIFACT_ROOT = "/tmp/councilsense-local-latest-artifacts"
_DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
_DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
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
    ("purchase agreement", "Purchase Agreement Approval"),
    ("right-of-way", "Right-of-Way Acquisition"),
    ("consent agenda", "Consent Agenda Changes"),
    ("public hearing", "Public Hearing Scheduling"),
    ("zoning", "Zoning and Land Use"),
    ("ordinance", "Ordinance Adoption"),
    ("resolution", "Resolution Approval"),
    ("budget", "Budget and Fiscal Planning"),
    ("fiscal", "Budget and Fiscal Planning"),
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
    ("budget", "Budget and Fiscal Planning"),
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
    outcome_source_types: tuple[str, ...]
    preview_only: bool
    conflicts: tuple[_AuthorityConflictSignal, ...]

    def to_metadata_payload(self) -> dict[str, object]:
        return {
            "authority_outcome": self.authority_outcome,
            "publication_status": self.publication_status,
            "reason_codes": list(self.reason_codes),
            "authoritative_source_type": self.authoritative_source_type,
            "outcome_source_types": list(self.outcome_source_types),
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
    outcome_source_types: tuple[str, ...],
    preview_only: bool,
    conflicts: tuple[_AuthorityConflictSignal, ...],
) -> _AuthorityPolicyResult:
    return _AuthorityPolicyResult(
        authority_outcome=authority_outcome,
        publication_status=publication_status,
        reason_codes=_ordered_unique_codes(*reason_codes),
        summarize_text=summarize_text,
        authoritative_source_type=authoritative_source_type,
        outcome_source_types=tuple(dict.fromkeys(outcome_source_types)),
        preview_only=preview_only,
        conflicts=conflicts,
    )


@dataclass(frozen=True)
class _AuthorityOutcomeSignal:
    source_type: str
    finding: str
    subject: str | None
    action_class: str


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
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._run_repository = ProcessingRunRepository(connection)
        self._lifecycle_service = ProcessingLifecycleService(self._run_repository)

    def process_latest(
        self,
        *,
        run_id: str,
        city_id: str,
        meeting_id: str | None,
        ingest_stage_metadata: dict[str, object] | None,
        llm_provider: str,
        ollama_endpoint: str | None,
        ollama_model: str | None,
        ollama_timeout_seconds: float,
    ) -> ProcessLatestResult:
        stage_outcomes: list[dict[str, object]] = []
        warnings: list[str] = []
        resolved_meeting_id: str | None = None
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
                llm_provider=llm_provider,
                ollama_endpoint=ollama_endpoint,
                ollama_model=ollama_model,
                ollama_timeout_seconds=ollama_timeout_seconds,
            )
            summarize_metadata: dict[str, object] = {
                "provider_used": summarize_payload.provider_used,
                "claim_count": len(summarize_payload.output.claims),
                "authority_policy": summarize_payload.authority_policy.to_metadata_payload(),
            }
            if summarize_payload.fallback_reason is not None:
                fallback_used = True
                summarize_metadata["fallback_reason"] = summarize_payload.fallback_reason
                warnings.append("ollama_fallback_to_deterministic")

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
        llm_provider: str,
        ollama_endpoint: str | None,
        ollama_model: str | None,
        ollama_timeout_seconds: float,
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
        authority_policy = _evaluate_authority_policy(compose_input=compose_input)
        summarize_text = authority_policy.summarize_text
        compose_section_ref = "compose.multi_document"

        if llm_provider == "ollama":
            try:
                output = _summarize_with_ollama(
                    text=summarize_text,
                    artifact_id=extracted.artifact_id,
                    section_ref=compose_section_ref,
                    material_context=material_context,
                    authority_policy=authority_policy,
                    topic_hardening_enabled=rollout_config.behavior_flags.topic_hardening_enabled,
                    specificity_retention_enabled=rollout_config.behavior_flags.specificity_retention_enabled,
                    evidence_projection_enabled=rollout_config.behavior_flags.evidence_projection_enabled,
                    endpoint=(ollama_endpoint or _DEFAULT_OLLAMA_ENDPOINT),
                    model=(ollama_model or _DEFAULT_OLLAMA_MODEL),
                    timeout_seconds=max(1.0, ollama_timeout_seconds),
                )
                provider_used = "ollama"
                status = "processed"
            except Exception as exc:
                output = _deterministic_summarize(
                    text=summarize_text,
                    artifact_id=extracted.artifact_id,
                    section_ref=compose_section_ref,
                    material_context=material_context,
                    authority_policy=authority_policy,
                    topic_hardening_enabled=rollout_config.behavior_flags.topic_hardening_enabled,
                    specificity_retention_enabled=rollout_config.behavior_flags.specificity_retention_enabled,
                    evidence_projection_enabled=rollout_config.behavior_flags.evidence_projection_enabled,
                )
                provider_used = "deterministic_fallback"
                fallback_reason = f"{type(exc).__name__}: {exc}"
                status = "limited_confidence"
        elif llm_provider == "none":
            output = _deterministic_summarize(
                text=summarize_text,
                artifact_id=extracted.artifact_id,
                section_ref=compose_section_ref,
                material_context=material_context,
                authority_policy=authority_policy,
                topic_hardening_enabled=rollout_config.behavior_flags.topic_hardening_enabled,
                specificity_retention_enabled=rollout_config.behavior_flags.specificity_retention_enabled,
                evidence_projection_enabled=rollout_config.behavior_flags.evidence_projection_enabled,
            )
            status = "processed"
        else:
            raise LocalPipelineError(
                stage="summarize",
                message=f"Unsupported llm provider: {llm_provider}",
                operator_hint="Use --llm-provider none|ollama.",
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
        return _SummarizePayload(
            output=output,
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
            config=rollout_config,
            source_text=source_text,
            output=output,
            summarize_status=summarize_status,
            extract_status=extract_status,
            summarize_fallback_used=summarize_fallback_used,
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
            },
            started_at=started_at,
            finished_at=finished_at,
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
        fallback_claim=claim_text,
        evidence_projection_enabled=evidence_projection_enabled,
    )

    return SummarizationOutput.from_sections(
        summary=summary,
        key_decisions=key_decisions,
        key_actions=key_actions,
        notable_topics=notable_topics,
        claims=claims,
    )


def _summarize_with_ollama(
    *,
    text: str,
    artifact_id: str,
    section_ref: str,
    material_context: _MeetingMaterialContext,
    authority_policy: _AuthorityPolicyResult,
    topic_hardening_enabled: bool,
    specificity_retention_enabled: bool,
    evidence_projection_enabled: bool,
    endpoint: str,
    model: str,
    timeout_seconds: float,
) -> SummarizationOutput:
    cleaned_source = _normalize_generated_text(text)
    focused_source = _focus_source_text(cleaned_source)
    preview_instruction = (
        "This source is agenda-only or packet-only; describe scheduled items and explicitly state that no decisions or completed actions are recorded yet because minutes are unavailable. "
        if authority_policy.preview_only or material_context.is_preview_only
        else ""
    )
    prompt = (
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
        fallback_claim=claim_text,
        evidence_projection_enabled=evidence_projection_enabled,
    )

    return SummarizationOutput.from_sections(
        summary=summary_text,
        key_decisions=key_decisions,
        key_actions=key_actions,
        notable_topics=notable_topics,
        claims=claims,
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

    decision_candidates = [
        _normalize_decision_sentence(s)
        for s in content_sentences
        if any(keyword in s.lower() for keyword in decision_keywords)
    ]
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
            outcome_source_types=("minutes",),
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
                outcome_source_types=tuple(source.source_type for source in supplemental_available),
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
            outcome_source_types=tuple(source.source_type for source in supplemental_available),
            preview_only=True,
            conflicts=(),
        )

    return _build_authority_policy_result(
        authority_outcome="missing_authoritative_minutes",
        publication_status="limited_confidence",
        reason_codes=("missing_authoritative_minutes",),
        summarize_text=compose_input.composed_text,
        authoritative_source_type=None,
        outcome_source_types=(),
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
    return tuple(preview_topics[:5])


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
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _derive_notable_topics(*, key_decisions: tuple[str, ...], key_actions: tuple[str, ...]) -> tuple[str, ...]:
    findings = [*key_decisions, *key_actions]
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

    bounded = list(ordered[:5])
    if len(bounded) < 3:
        bounded = _apply_topic_fallbacks(existing=bounded, findings=findings)

    if not bounded:
        return ("Meeting outcomes",)
    return tuple(bounded[:5])


def _extract_phrase_topic_candidate(sentence: str) -> str | None:
    match = re.search(
        r"\b(?:approved?|adopted?|authorized?|directed?|scheduled?|tabled?|ratified?|denied|accepted|amended|continued?)\b\s+"
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


def _build_grounded_summary(text: str) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return "Meeting source text unavailable."
    substantive_sentences = [
        sentence
        for sentence in sentences
        if not _is_low_value_outcome(sentence) and not _is_meeting_operations_sentence(sentence)
    ]
    if substantive_sentences:
        sentences = substantive_sentences
    prioritized = [
        sentence
        for sentence in sentences
        if any(
            keyword in sentence.lower()
            for keyword in (
                "motion",
                "resolution",
                "approved",
                "adopt",
                "directed",
                "hearing",
                "agreement",
                "contract",
                "ordinance",
                "budget",
                "zoning",
            )
        )
    ]
    selected = (prioritized or sentences)[:3]
    summary = " ".join(selected)
    return summary[:520]


def _normalize_decision_sentence(sentence: str) -> str:
    cleaned = _normalize_sentence(sentence)
    if not cleaned:
        return cleaned

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
        "joined the meeting",
        "was excused",
        "roll call",
        "call to order",
        "pledge of allegiance",
        "mayor pro tempore",
    )
    return any(marker in lower for marker in markers)


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
        if evidence_projection_enabled:
            evidence_match = _best_evidence_match_for_finding(
                source_text=source_text,
                finding=finding,
                default_section_ref=section_ref,
            )
        else:
            evidence_match = _EvidenceMatch(
                excerpt=_normalize_generated_text(finding)[:280],
                section_ref=section_ref,
                char_start=None,
                char_end=None,
            )
        claims.append(
            SummaryClaim(
                claim_text=finding,
                evidence=(
                    ClaimEvidencePointer(
                        artifact_id=artifact_id,
                        section_ref=evidence_match.section_ref,
                        char_start=evidence_match.char_start,
                        char_end=evidence_match.char_end,
                        excerpt=evidence_match.excerpt,
                    ),
                ),
                evidence_gap=False,
            )
        )
    return tuple(claims)


@dataclass(frozen=True)
class _EvidenceMatch:
    excerpt: str
    section_ref: str
    char_start: int | None
    char_end: int | None


def _best_evidence_match_for_finding(*, source_text: str, finding: str, default_section_ref: str) -> _EvidenceMatch:
    sentence_spans = _split_sentences_with_offsets(source_text)
    if not sentence_spans:
        fallback_excerpt = (source_text or finding)[:280]
        return _EvidenceMatch(
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
        excerpt=_normalize_generated_text(best_sentence)[:280],
        section_ref=precise_section,
        char_start=best_start,
        char_end=best_end,
    )


def _split_sentences_with_offsets(text: str) -> list[tuple[str, int, int, int]]:
    spans: list[tuple[str, int, int, int]] = []
    sentence_index = 0
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]|$)", text):
        sentence = _normalize_generated_text(match.group(0)).strip()
        if not sentence:
            continue
        spans.append((sentence, sentence_index, match.start(), match.end()))
        sentence_index += 1
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