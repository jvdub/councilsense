from __future__ import annotations

import logging
from pathlib import Path
from typing import Mapping


logger = logging.getLogger(__name__)

MULTI_DOCUMENT_PIPELINE_STAGES: tuple[str, ...] = (
    "ingest",
    "extract",
    "compose",
    "summarize",
    "publish",
)
MULTI_DOCUMENT_BUNDLE_STAGES = frozenset({"compose", "summarize", "publish"})
MULTI_DOCUMENT_REQUIRED_LOG_FIELDS: tuple[str, ...] = (
    "city_id",
    "meeting_id",
    "run_id",
    "stage",
    "source_id",
    "source_type",
    "artifact_id",
    "bundle_id",
    "dedupe_key",
    "outcome",
)
MULTI_DOCUMENT_LOG_FIELD_COVERAGE: dict[str, tuple[str, ...]] = {
    stage: MULTI_DOCUMENT_REQUIRED_LOG_FIELDS for stage in MULTI_DOCUMENT_PIPELINE_STAGES
}


class MultiDocumentLogContractError(RuntimeError):
    def __init__(
        self,
        *,
        stage: str,
        missing_fields: tuple[str, ...] = (),
        invalid_fields: tuple[str, ...] = (),
    ) -> None:
        self.stage = stage
        self.missing_fields = missing_fields
        self.invalid_fields = invalid_fields
        self.operator_hint = (
            "Populate the required multi-document structured log correlation fields before rerunning the pipeline."
        )

        detail_parts: list[str] = []
        if missing_fields:
            detail_parts.append(f"missing={','.join(missing_fields)}")
        if invalid_fields:
            detail_parts.append(f"invalid={','.join(invalid_fields)}")
        detail = "; ".join(detail_parts) if detail_parts else "unknown contract violation"
        super().__init__(f"Invalid multi-document structured log contract for stage '{stage}': {detail}")


def resolve_stage_source_type(*, stage: str, source_type: str | None) -> str:
    if stage in MULTI_DOCUMENT_BUNDLE_STAGES:
        return "bundle"
    normalized = _normalize_string(source_type)
    return normalized or "unknown"


def build_bundle_id(*, meeting_id: str) -> str:
    normalized_meeting_id = _required_string(field="meeting_id", value=meeting_id)
    return f"bundle:{normalized_meeting_id}"


def derive_artifact_id(*, artifact_path: str | None, meeting_id: str | None = None) -> str:
    normalized_path = _normalize_string(artifact_path)
    if normalized_path is not None:
        return f"artifact-local:{Path(normalized_path).name}"

    normalized_meeting_id = _normalize_string(meeting_id)
    if normalized_meeting_id is not None:
        return f"artifact-local-meeting:{normalized_meeting_id}"

    return "artifact-unknown"


def build_stage_dedupe_key(
    *,
    run_id: str,
    meeting_id: str,
    stage: str,
    source_id: str,
    artifact_id: str,
    bundle_id: str,
) -> str:
    normalized_stage = _required_string(field="stage", value=stage)
    normalized_run_id = _required_string(field="run_id", value=run_id)
    normalized_meeting_id = _required_string(field="meeting_id", value=meeting_id)
    normalized_source_id = _required_string(field="source_id", value=source_id)
    normalized_artifact_id = _required_string(field="artifact_id", value=artifact_id)
    normalized_bundle_id = _required_string(field="bundle_id", value=bundle_id)

    scope_id = normalized_bundle_id if normalized_stage in MULTI_DOCUMENT_BUNDLE_STAGES else normalized_artifact_id
    return f"pipeline-multidoc:{normalized_run_id}:{normalized_meeting_id}:{normalized_stage}:{normalized_source_id}:{scope_id}"


def validate_multi_document_log_event(*, stage: str, event: Mapping[str, object]) -> None:
    if stage not in MULTI_DOCUMENT_LOG_FIELD_COVERAGE:
        raise MultiDocumentLogContractError(stage=stage, invalid_fields=("stage",))

    missing_fields = tuple(
        field
        for field in MULTI_DOCUMENT_LOG_FIELD_COVERAGE[stage]
        if _normalize_string(event.get(field)) is None
    )

    invalid_fields: list[str] = []
    if _normalize_string(event.get("stage")) != stage:
        invalid_fields.append("stage")

    if not missing_fields:
        expected_bundle_id = build_bundle_id(meeting_id=str(event["meeting_id"]))
        if str(event["bundle_id"]) != expected_bundle_id:
            invalid_fields.append("bundle_id")

        expected_source_type = resolve_stage_source_type(stage=stage, source_type=_normalize_string(event.get("source_type")))
        if str(event["source_type"]) != expected_source_type:
            invalid_fields.append("source_type")

        expected_dedupe_key = build_stage_dedupe_key(
            run_id=str(event["run_id"]),
            meeting_id=str(event["meeting_id"]),
            stage=stage,
            source_id=str(event["source_id"]),
            artifact_id=str(event["artifact_id"]),
            bundle_id=str(event["bundle_id"]),
        )
        if str(event["dedupe_key"]) != expected_dedupe_key:
            invalid_fields.append("dedupe_key")

    if missing_fields or invalid_fields:
        raise MultiDocumentLogContractError(
            stage=stage,
            missing_fields=missing_fields,
            invalid_fields=tuple(invalid_fields),
        )


def emit_multi_document_stage_event(
    *,
    event_name: str,
    stage: str,
    outcome: str,
    status: str,
    city_id: str,
    meeting_id: str,
    run_id: str,
    source_id: str,
    source_type: str | None,
    artifact_id: str,
    extra_fields: Mapping[str, object] | None = None,
) -> dict[str, object]:
    normalized_stage = _required_string(field="stage", value=stage)
    normalized_meeting_id = _required_string(field="meeting_id", value=meeting_id)
    normalized_source_id = _required_string(field="source_id", value=source_id)
    normalized_artifact_id = _required_string(field="artifact_id", value=artifact_id)
    bundle_id = build_bundle_id(meeting_id=normalized_meeting_id)

    event: dict[str, object] = {
        "event_name": _required_string(field="event_name", value=event_name),
        "city_id": _required_string(field="city_id", value=city_id),
        "meeting_id": normalized_meeting_id,
        "run_id": _required_string(field="run_id", value=run_id),
        "stage": normalized_stage,
        "source_id": normalized_source_id,
        "source_type": resolve_stage_source_type(stage=normalized_stage, source_type=source_type),
        "artifact_id": normalized_artifact_id,
        "bundle_id": bundle_id,
        "dedupe_key": build_stage_dedupe_key(
            run_id=run_id,
            meeting_id=normalized_meeting_id,
            stage=normalized_stage,
            source_id=normalized_source_id,
            artifact_id=normalized_artifact_id,
            bundle_id=bundle_id,
        ),
        "outcome": _required_string(field="outcome", value=outcome),
        "status": _required_string(field="status", value=status),
    }
    if extra_fields:
        event.update(dict(extra_fields))

    validate_multi_document_log_event(stage=normalized_stage, event=event)
    logger.info(event_name, extra={"event": event})
    return event


def _normalize_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _required_string(*, field: str, value: object) -> str:
    normalized = _normalize_string(value)
    if normalized is None:
        raise ValueError(f"{field} must be a non-empty string")
    return normalized