from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote


ST022_IDEMPOTENCY_KEY_VERSION = "st022-idem-v1"

StageName = Literal["ingest", "extract", "summarize", "publish"]


def _normalize_component(*, name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must be non-empty")
    return quote(normalized, safe="-_.~")


def _join_key_parts(*, stage: StageName, parts: list[tuple[str, str]]) -> str:
    ordered_parts = [
        f"{name}={_normalize_component(name=name, value=value)}"
        for name, value in parts
    ]
    return ":".join([ST022_IDEMPOTENCY_KEY_VERSION, stage, *ordered_parts])


def build_ingest_idempotency_key(
    *,
    city_id: str,
    meeting_id: str,
    source_type: str,
    source_revision: str,
    source_checksum: str,
) -> str:
    return _join_key_parts(
        stage="ingest",
        parts=[
            ("city", city_id),
            ("meeting", meeting_id),
            ("source", source_type),
            ("revision", source_revision),
            ("checksum", source_checksum),
        ],
    )


def build_extract_idempotency_key(
    *,
    city_id: str,
    meeting_id: str,
    source_type: str,
    source_revision: str,
    artifact_checksum: str,
) -> str:
    return _join_key_parts(
        stage="extract",
        parts=[
            ("city", city_id),
            ("meeting", meeting_id),
            ("source", source_type),
            ("revision", source_revision),
            ("checksum", artifact_checksum),
        ],
    )


def build_summarize_idempotency_key(
    *,
    city_id: str,
    meeting_id: str,
    bundle_revision: str,
    source_coverage_checksum: str,
) -> str:
    return _join_key_parts(
        stage="summarize",
        parts=[
            ("city", city_id),
            ("meeting", meeting_id),
            ("bundle_revision", bundle_revision),
            ("coverage_checksum", source_coverage_checksum),
        ],
    )


def build_publish_idempotency_key(
    *,
    city_id: str,
    meeting_id: str,
    publication_revision: str,
    summary_checksum: str,
) -> str:
    return _join_key_parts(
        stage="publish",
        parts=[
            ("city", city_id),
            ("meeting", meeting_id),
            ("publication_revision", publication_revision),
            ("summary_checksum", summary_checksum),
        ],
    )


@dataclass(frozen=True)
class StageOwnership:
    stage: StageName
    producer: str
    consumer: str
    persisted_handoff_state: str
    boundary: str


ST022_STAGE_OWNERSHIP_TABLE: tuple[StageOwnership, ...] = (
    StageOwnership(
        stage="ingest",
        producer="bundle planner + source adapter",
        consumer="extract stage worker",
        persisted_handoff_state="raw artifact persisted and extract queue payload recorded",
        boundary="ingest owns external source retrieval and canonical raw artifact write; extract owns parsing",
    ),
    StageOwnership(
        stage="extract",
        producer="extract stage worker",
        consumer="summarize stage worker",
        persisted_handoff_state="normalized extracted text artifact persisted and summarize queue payload recorded",
        boundary="extract owns parser selection and normalized extraction output; summarize owns synthesis",
    ),
    StageOwnership(
        stage="summarize",
        producer="summarize stage worker",
        consumer="publish stage worker",
        persisted_handoff_state="summary payload persisted and publish queue payload recorded",
        boundary="summarize owns claim synthesis and evidence packaging; publish owns publication state transition",
    ),
    StageOwnership(
        stage="publish",
        producer="publish stage worker",
        consumer="meeting detail reader API",
        persisted_handoff_state="publication record committed with final status and source coverage diagnostics",
        boundary="publish owns durable meeting publication write; reader API owns projection and response formatting",
    ),
)


def stage_ownership_for(stage: StageName) -> StageOwnership:
    for ownership in ST022_STAGE_OWNERSHIP_TABLE:
        if ownership.stage == stage:
            return ownership
    raise ValueError(f"Unknown stage: {stage}")
